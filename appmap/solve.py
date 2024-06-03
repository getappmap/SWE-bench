import argparse
import json
from pathlib import Path
from multiprocessing import Pool, current_process, cpu_count
from swebench.harness.context_manager import TestbedContextManager
from swebench.harness.engine_validation import setup_testbed
from datasets import DatasetDict, load_dataset, load_from_disk
from swebench.harness.utils import split_instances, DotDict
from subprocess import run
from os.path import abspath
from filelock import FileLock

datasets_dir = Path(__file__).parent / "datasets"


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
    # Check that this is defined
    output_file = data["output_file"]

    for instance in data["task_instances"]:
        issue_dir = Path(data["log_dir"]) / "solve" / instance["instance_id"]
        issue_dir.mkdir(parents=True, exist_ok=True)
        issue_file = issue_dir / "issue.txt"
        with open(issue_file, "w") as f:
            f.write(instance["problem_statement"])

        try:
            run(
                ["git", "checkout", instance["base_commit"]],
                cwd=data["testbed"],
                check=True,
            )
            run(
                [
                    "python",
                    abspath(data["solver_path"]),
                    data["testbed"],
                    str(issue_file),
                    "--appmap-command",
                    data["appmap_command"],
                ],
                check=True,
                cwd=data["testbed"],
            )
            output = run(
                ["git", "--no-pager", "diff"],
                check=True,
                cwd=data["testbed"],
                capture_output=True,
                text=True,
            )
            if output.stdout:
                instance["model_patch"] = output.stdout
                instance["model_name_or_path"] = "navie"
                with FileLock(f"{output_file}.lock"):
                    with open(output_file, "a+") as f:
                        f.write(json.dumps(instance) + "\n")
        except Exception:
            import traceback
            print(f"Error processing {instance['instance_id']}")
            traceback.print_exc()


def setup_testbed(data: dict):
    """
    Creates testbed context manager and runs verify_task_instances in parallel

    Args:
        data: Dict containing task instances and other data
        conda_link: URL to conda installation to use
        task_instances: List of task instances
        log_dir: Path to log directory
        path_conda: Path to miniconda3 or anaconda installation
        testbed: Path to testbed directory
        temp_dir: Path to temporary directory for storing virtual envs
        timeout: Timeout (seconds) for testing script execution
        verbose: Verbose mode
        appmap_command: Path to appmap command
        solver_path: Path to solver
        output_file: Path to output file
    """
    data_dict = DotDict(data)
    with TestbedContextManager(
        data_dict.task_instances,
        data_dict.log_dir,
        conda_link=data_dict.conda_link,
        path_conda=data_dict.path_conda,
        testbed=data_dict.testbed,
        temp_dir=data_dict.temp_dir,
        timeout=data_dict.timeout,
        verbose=data_dict.verbose,
        appmap_command=data_dict.appmap_command,
        solver_path=data_dict.solver_path,
        output_file=data_dict.output_file,
        keep=data_dict.keep,
    ) as tcm:
        distributed_task_list = tcm.get_distributed_tasks()
        for task_list in distributed_task_list:
            print(
                f"{task_list['testbed']}: {len(task_list['task_instances'])} instances"
            )

        if len(distributed_task_list) == 1:
            data_dict.func(distributed_task_list[0])
            return

        pool = Pool(processes=len(distributed_task_list))
        pool.map(data_dict.func, distributed_task_list)
        pool.close()
        pool.join()


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
            "output_file": args.output,
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
    dataset = load_data(args.instances_path, args.split)
    solve_instances(dataset, args)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--instances_path",
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
    parser.add_argument(
        "--keep",
        action="store_true",
        help="(Optional) Keep temporary directories after running",
    )
    args = parser.parse_args()
    main(args)
