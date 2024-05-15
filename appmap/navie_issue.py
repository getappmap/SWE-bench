#!/usr/bin/env python
import argparse
import os
from pathlib import Path
from tempfile import gettempdir, mkdtemp

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


def archive_name(task):
    return f"{task['repo'].split('/')[-1]}-{task['version']}.tar.xz"


def rewrite_issues(tasks, archive):
    # get repo and version from first task
    repo, version = tasks[0]["repo"].split("/")[-1], tasks[0]["version"]

    # make a temporary work directory
    work = mkdtemp(dir=workdir, prefix=f"swe-navie-{repo}-{version}-")
    print(f"Working in {work}")

    # clone base repository
    clone_to(tasks[0]["repo"], work)
    # extract archive
    os.system(f"tar -xf {archive} -C {work}")

    for task in tasks:
        # checkout base commit
        os.chdir(work)
        print(f"Checking out {task['base_commit']}")
        os.system(f"git checkout --quiet {task['base_commit']}")
        print(f"Running appmap on {task['instance_id']}")
        source_list_file = os.path.join(work, "navie-files.list")
        process = Popen(
            [
                os.path.expanduser(appmap_bin),
                "navie",
                "--agent-mode",
                "issue",
                "-d",
                work,
                "--sources-output",
                source_list_file,
                "-",
            ],
            stdin=PIPE,
            stdout=PIPE,
            stderr=PIPE,
            text=True,
        )
        task["original_issue"] = task["problem_statement"]
        task["problem_statement"], stderr = process.communicate(
            input=task["problem_statement"]
        )
        task["hits"] = [{"docid": name} for name in read_file_list(source_list_file)]
        yield task

    # cleanup work directory
    if not keep:
        os.system(f"rm -rf {work}")


def read_file_list(path: str) -> list[str]:
    with open(path, "r") as f:
        return f.read().splitlines()


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


def main(*, instances: str, appmaps: str, output: str):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    dataset, dataset_name = load_data(instances)
    output_path = output / (dataset_name + ".navie.jsonl")

    with FileLock(output_path.as_posix() + ".lock"):
        processed = load_existing(output_path)
        existing_ids = [i["instance_id"] for i in processed]

        print(f"Output: {output_path}, #processed: {len(processed)}")

        # enumerate available appmap archives
        archives = [f for f in os.listdir(appmaps) if f.endswith(".tar.xz")]

        # group tasks per archive name
        task_groups = {}
        for task in flatten_dataset(dataset):
            if task["instance_id"] in existing_ids:
                continue
            archive = archive_name(task)
            if archive not in task_groups:
                task_groups[archive] = []
            task_groups[archive].append(task)

        # filter task groups by available archives
        task_groups = {k: v for k, v in task_groups.items() if k in archives}

        # print statistics
        print(
            f"Found {len(task_groups)} task groups for {len(archives)} available archives"
        )
        for k, v in task_groups.items():
            print(f"{k}: {len(v)} instances")

        with open(output_path, "a") as f:
            for archive, tasks in task_groups.items():
                for instance in rewrite_issues(
                    tasks, os.path.abspath(os.path.join(appmaps, archive))
                ):
                    processed.append(instance)
                    print(json.dumps(instance), file=f, flush=True)
                    print(f"Wrote {instance['instance_id']} to {output_path}")

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
    # parser.add_argument(
    #     "--overwrite", action="store_true", help="overwrite existing files"
    # )
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
    main(appmaps=args.appmaps, instances=args.instances, output=args.output)
