import argparse
import json
from pathlib import Path
from multiprocessing import Pool, current_process, cpu_count, get_start_method
from swebench.harness.engine_validation import setup_testbed
from datasets import DatasetDict, load_dataset, load_from_disk
from swebench.harness.utils import split_instances
from subprocess import run
from tempfile import NamedTemporaryFile
from os.path import abspath
from filelock import FileLock

datasets_dir = Path(__file__).parent / "datasets"
output_file = None


def load_data(dataset_name, split) -> tuple[DatasetDict, str]:
    dataset_dir = datasets_dir / dataset_name.replace("/", "__")
    dataset = None
    if Path(dataset_dir).exists():
        dataset = load_from_disk(str(dataset_dir))
    else:
        dataset = load_dataset(dataset_name)
        Path.mkdir(dataset_dir, parents=True)
        dataset.save_to_disk(str(dataset_dir))

    return dataset[split]


def solve_instance(data):
    for instance in data["task_instances"]:
        try:
            with NamedTemporaryFile(
                mode="w", dir=data["testbed"], prefix="issue_", suffix=".txt"
            ) as f:
                f.write(instance["problem_statement"])
                f.flush()
                run(
                    [
                        "python",
                        abspath(args.solver_path),
                        data["testbed"],
                        f.name,
                        "--appmap-command",
                        args.appmap_command,
                    ],
                    check=True,
                    cwd=data["testbed"],
                    start_new_session=True,
                )
            output = run(
                ["git", "--no-pager", "diff"],
                check=True,
                cwd=data["testbed"],
                capture_output=True,
                text=True,
                start_new_session=True,
            )
            if output.stdout:
                instance["model_patch"] = output.stdout
                instance["model_name_or_path"] = "navie"
                with FileLock(f"{output_file}.lock"):
                    with open(output_file, "a+") as f:
                        f.write(json.dumps(instance) + "\n")
        except Exception as e:
            print(f"Error: {e}")

def init_solve_worker():
    current_process().daemon = False

def solve_instances(instances, args):
    if args.filter is not None:
        instances = [
            instance for instance in instances if args.filter in instance["instance_id"]
        ]

    instance_groups = split_instances(list(instances), args.num_workers)
    data_groups = [
        {
            "task_instances": g,
            "func": solve_instance,
            **vars(args),
        }
        for g in instance_groups
    ]

    if args.num_workers == 1:
        setup_testbed(data_groups[0])
        return

    pool = Pool(processes=args.num_workers, initializer=init_solve_worker)
    pool.map(setup_testbed, data_groups)
    pool.close()
    pool.join()


def main(args):
    print(f"The current start method is: {get_start_method()}")
    dataset = load_data(args.instances, args.split)
    global output_file
    output_file = args.output
    solve_instances(dataset, args)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--instances",
        type=str,
        help="path or huggingface name of task instances dataset",
        default="princeton-nlp/SWE-bench_Lite",
    )
    parser.add_argument(
        "--split", type=str, default="test", help="Dataset split to use"
    )
    parser.add_argument(
        "--log_dir", type=str, help="Path to log directory", default="logs"
    )
    parser.add_argument(
        "--conda_link",
        type=str,
        default=None,
        help="(Optional) URL to conda installation to use",
    )
    parser.add_argument(
        "--log_suffix",
        type=str,
        default=None,
        help="(Optional) Suffix to append to log file names",
    )
    parser.add_argument(
        "--path_conda",
        type=str,
        help="(Optional) Path to miniconda3 or anaconda installation",
    )
    parser.add_argument(
        "--testbed", type=str, help="(Optional) Path to testbed directory"
    )
    parser.add_argument(
        "--temp_dir",
        type=str,
        help="(Optional) Path to temporary directory for storing virtual envs",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="(Optional) Timeout (seconds) for testing script execution",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="(Optional) Verbose mode"
    )
    parser.add_argument(
        "--num_workers",
        type=int,
        default=cpu_count(),
        help="(Optional) Number of workers",
    )
    parser.add_argument(
        "--filter",
        type=str,
        default=None,
        help="(Optional) Filter to apply to task instances",
    )
    parser.add_argument(
        "--solver_path", type=str, default=None, help="Path to solver", required=True
    )
    parser.add_argument(
        "--appmap_command", type=str, default="appmap", help="Path to appmap command"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="predictions.jsonl",
        help="Path to output predictions",
    )
    args = parser.parse_args()
    main(args)
