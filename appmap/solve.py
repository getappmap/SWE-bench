import argparse
import json
import re
from pathlib import Path
from multiprocessing import Pool, current_process, cpu_count
from swebench.harness.context_manager import (
    TestbedContextManager,
    TaskEnvContextManager,
)
from swebench.harness.utils import split_instances, DotDict
from subprocess import run
from os.path import abspath
from filelock import FileLock
from data import load_data


def output_results(instance, output_file, patch):
    if patch is None:
        return
    instance["model_patch"] = patch
    instance["model_name_or_path"] = "navie"
    with FileLock(f"{output_file}.lock"):
        with open(output_file, "a+") as f:
            f.write(json.dumps(instance) + "\n")


def solve_instance(instance, log_dir, testbed, appmap_command, lint_command, retries):
    issue_dir = Path(log_dir) / "solve" / instance["instance_id"]
    issue_dir.mkdir(parents=True, exist_ok=True)
    issue_file = issue_dir / "issue.txt"
    with open(issue_file, "w") as f:
        f.write(instance["problem_statement"])

    solver_path = Path(__file__).parent / "solve" / "solver.py"
    run_args = [
        "python",
        str(solver_path),
        str(issue_file),
        "--retries",
        str(retries),
        "--log-dir",
        log_dir,
        "--appmap-command",
        appmap_command,
    ]
    if lint_command is not None:
        run_args.extend(["--lint-command", lint_command])

    try:
        # Run this as a separate process so that it can change the working directory.
        run(run_args, check=True, cwd=testbed)
        output = run(
            ["git", "--no-pager", "diff"],
            check=True,
            cwd=testbed,
            capture_output=True,
            text=True,
        )
        return output.stdout
    except Exception:
        print(f"Error processing {instance['instance_id']}")
        import traceback

        traceback.print_exc()


def worker_init(data: dict):
    """
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
        output_file: Path to output file
    """
    data_dict = DotDict(data)

    assert data_dict.output is not None
    assert data_dict.appmap_command is not None
    assert data_dict.path_conda is not None
    assert data_dict.retries is not None

    output_file = abspath(data_dict.output)

    try:
        with TestbedContextManager(
            data_dict.task_instances,
            data_dict.log_dir,
            conda_link=data_dict.conda_link,
            path_conda=data_dict.path_conda,
            testbed=data_dict.testbed,
            temp_dir=data_dict.temp_dir,
            timeout=data_dict.timeout,
            verbose=data_dict.verbose,
            keep=data_dict.keep,
        ) as tcm:
            for instance in data_dict.task_instances:
                repo_prefix = instance["repo"].replace("/", "__")
                env_name = f"{repo_prefix}__{instance['version']}"
                testbed = Path(tcm.testbed) / env_name
                log_dir = abspath(data_dict.log_dir)
                try:
                    with TaskEnvContextManager(
                        instance,
                        testbed.as_posix(),
                        env_name,
                        log_dir,
                        data_dict.path_conda,
                        timeout=data_dict.timeout,
                        verbose=data_dict.verbose,
                        log_suffix=data_dict.log_suffix,
                    ) as task_manager:
                        if not task_manager.reset_task_env(instance):
                            return
                        patch = solve_instance(
                            instance,
                            log_dir,
                            testbed,
                            data_dict.appmap_command,
                            data_dict.lint_command,
                            data_dict.retries,
                        )
                        output_results(instance, output_file, patch)
                except Exception:
                    print(f"Error processing {instance['instance_id']}")
                    import traceback

                    traceback.print_exc()
    except Exception:
        print("Error instantiating testbed")
        import traceback

        traceback.print_exc()


def solve_instances(instances, args):
    if args.filter:
        pattern = re.compile(args.filter)
        instances = [
            instance for instance in instances if pattern.search(instance["instance_id"])
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
        worker_init(data_groups[0])
        return

    pool = Pool(processes=args.num_workers)
    pool.map(worker_init, data_groups)
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
        "--retries",
        type=int,
        default=3,
        help="Number of times to try and create a code update for each test instance",
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
        "--appmap_command", type=str, default="appmap", help="Path to appmap command"
    )
    parser.add_argument(
        "--lint_command",
        type=str,
        help="Path to lint command. Example: flake8 --extend-ignore=BLK100,W293,E501,E302,D",
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
