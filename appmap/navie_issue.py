#!/usr/bin/env python
import argparse
import os
from pathlib import Path
from tempfile import gettempdir, mkdtemp
from typing import Optional, Union

from datasets import DatasetDict, load_dataset, load_from_disk

from swebench.harness.utils import clone_to
from swebench.metrics.getters import get_eval_refs
from subprocess import PIPE, Popen
import json
from filelock import FileLock


# path to project root
root_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
workdir = os.path.join(gettempdir())
keep = False
appmap_bin = None


def repo_version(task):
    return f"{task['repo'].split('/')[-1]}-{task['version']}"


def rewrite_issues(tasks, archive):
    # get repo and version from first task
    repo, version = tasks[0]["repo"].split("/")[-1], tasks[0]["version"]

    # make a temporary work directory
    work = mkdtemp(dir=workdir, prefix=f"swe-navie-{repo}-{version}-")
    print(f"Working in {work}")

    # clone base repository
    print("Cloning repository")
    clone_to(tasks[0]["repo"], work)
    # extract archive
    if os.path.exists(archive):
        print(f"Extracting {archive}")
        os.system(f"tar -xf {archive} -C {work}")
    else:
        archive = None
        print("Working without appmaps")

    os.chdir(work)
    for task in tasks:
        # checkout base commit
        print(f"Checking out {task['base_commit']}")
        os.system(f"git checkout --quiet {task['base_commit']}")
        cmdline = [
            os.path.expanduser(appmap_bin),
            "navie",
            "--agent-mode",
            "issue",
            "-d",
            work,
            "-",
        ]
        print(f"Running {' '.join(cmdline)} on {task['instance_id']}")
        process = Popen(
            cmdline,
            stdin=PIPE,
            stdout=PIPE,
            stderr=PIPE,
            text=True,
        )
        task["original_issue"] = task["problem_statement"]
        stdout, stderr = process.communicate(input=task["problem_statement"])
        if process.returncode != 0:
            print(stdout)
            print(stderr)
            continue
        task["problem_statement"] = stdout
        task["has_appmaps"] = archive is not None
        task["appmap_archive"] = os.path.basename(archive)
        yield task

    # cleanup work directory
    os.chdir(workdir)
    if not keep:
        os.system(f"rm -rf {work}")


def context_to_hits(context: list[dict[str, Union[str, float]]]):
    scores = {}
    for i, item in enumerate(context):
        if item["type"] == "code-snippet":
            path, lineno = item["location"].split(":")
            # use rank as the default score
            score = item.get("score", (len(context) - i) / len(context))
            scores[path] = scores.get(path, 0) + score

    paths = sorted(scores, key=lambda p: scores[p], reverse=True)
    return [{"docid": path} for path in paths]


def load_existing(output_path):
    existing = []
    if os.path.isfile(output_path):
        with open(output_path, "r") as f:
            for line in f:
                existing.append(json.loads(line))
    return existing


def load_data(dataset_name_or_path) -> tuple[DatasetDict, str]:
    if Path(dataset_name_or_path).exists():
        dataset = load_from_disk(dataset_name_or_path)
        dataset_name = os.path.basename(dataset_name_or_path)
    else:
        dataset = load_dataset(dataset_name_or_path)
        dataset_name = dataset_name_or_path.replace("/", "__")

    return dataset, dataset_name


def flatten_dataset(data: DatasetDict):
    for dataset in data.values():
        for example in dataset:
            yield example


def main(
    *,
    instances: str,
    appmaps: str,
    output: str,
    filter: Optional[str],
    all: Optional[bool],
    overwrite: Optional[bool],
):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    dataset, dataset_name = load_data(instances)
    output_path = output / (dataset_name + ".navie.jsonl")

    with FileLock(output_path.as_posix() + ".lock"):
        processed = load_existing(output_path)
        existing_ids = [i["instance_id"] for i in processed]

        print(f"Output: {output_path}, #processed: {len(processed)}")

        # group tasks per repo and version
        task_groups = {}
        for task in flatten_dataset(dataset):
            instance_id = task["instance_id"]
            if filter and filter not in instance_id:
                continue
            if not overwrite and instance_id in existing_ids:
                continue
            rv = repo_version(task)
            if rv not in task_groups:
                task_groups[rv] = []
            task_groups[rv].append(task)

        archives = {}
        for rv in list(task_groups.keys()):
            archive = next(Path(appmaps).glob(f"{rv}*.tar.xz"), None)
            if archive is None:
                if not all:
                    del task_groups[rv]
            else:
                print(f"Found archive for {rv}: {archive}")
                archives[rv] = archive.as_posix()

        # print statistics
        print(f"Found {len(task_groups)} task groups")
        for k, v in task_groups.items():
            print(f"{k}: {len(v)} instances")

        try:
            with open(output_path, "a") as f:
                for rv, tasks in task_groups.items():
                    for instance in rewrite_issues(tasks, archives.get(rv, None)):
                        processed.append(instance)
                        print(json.dumps(instance), file=f, flush=True)
                        print(f"Wrote {instance['instance_id']} to {output_path}")
        except KeyboardInterrupt:
            print("Interrupted, writing partial dataset")

        processed_by_id = {i["instance_id"]: i for i in processed}

        processed_dataset = dataset.filter(
            lambda i: i["instance_id"] in processed_by_id
        ).map(lambda i: processed_by_id[i["instance_id"]])

        output_ds_path = output / (dataset_name + ".navie")
        processed_dataset.save_to_disk(output_ds_path.as_posix())
        print(
            f"Saved processed dataset to {output_ds_path} ({sum([len(d) for d in processed_dataset.values()])} total examples)"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--instances",
        type=str,
        help="path or huggingface name of task instances dataset",
        default="princeton-nlp/SWE-bench_Lite",
    )
    parser.add_argument(
        "--appmaps",
        type=str,
        help="path to appmap archives",
        default=os.path.join(root_path, "appmaps"),
    )
    parser.add_argument(
        "--output",
        type=str,
        help="path to output directory",
        default=os.path.join(root_path, "navied-tasks"),
    )
    parser.add_argument(
        "--appmap-bin",
        type=str,
        help="path to appmap binary",
        default="~/.appmap/bin/appmap",
    )
    parser.add_argument(
        "--filter", type=str, help="filter to apply to the instance list"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="process all instances (not only those with appmaps)",
    )
    parser.add_argument(
        "--overwrite", action="store_true", help="overwrite existing files"
    )
    # parser.add_argument(
    #     "--verbose", action="store_true", help="(Optional) Verbose mode"
    # )
    # parser.add_argument(
    #     "--num_workers", type=int, default=None, help="(Optional) Number of workers"
    # )

    parser.add_argument("--keep", action="store_true", help="keep temporary files")
    parser.add_argument("--workdir", type=str, default=workdir)
    args = parser.parse_args()
    workdir = args.workdir
    keep = args.keep
    appmap_bin = args.appmap_bin
    main(
        appmaps=args.appmaps,
        instances=args.instances,
        output=args.output,
        filter=args.filter,
        all=args.all,
        overwrite=args.overwrite,
    )
