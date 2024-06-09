import argparse
import json
import os
import re
from pathlib import Path
from multiprocessing import Pool, cpu_count
from swebench.harness.context_manager import (
    TestbedContextManager,
    TaskEnvContextManager,
)
from swebench.harness.utils import DotDict, split_instances
from subprocess import run
from os.path import abspath
from filelock import FileLock
from data import load_data

def output_results(instance, output_file, patch):
    instance["model_patch"] = patch
    instance["model_name_or_path"] = "navie"
    with FileLock(f"{output_file}.lock"):
        with open(output_file, "a+") as f:
            f.write(json.dumps(instance) + "\n")


def solve_instance(
    instances_path,
    instance,
    log_dir,
    testbed,
    path_conda,
    appmap_command,
    lint_command,
    iteration,
    steps=None,
):
    issue_dir = Path(log_dir) / "solve" / instance["instance_id"] / str(iteration + 1)
    issue_dir.mkdir(parents=True, exist_ok=True)
    issue_file = issue_dir / "issue.txt"
    with open(issue_file, "w") as f:
        f.write(instance["problem_statement"])

    solver_path = Path(__file__).parent / "solve" / "solver.py"
    solve_args = [
        "python",
        str(solver_path),
        str(issue_file),
        "--instances-path",
        instances_path,
        "--instance-id",
        instance["instance_id"],
        "--path-conda",
        path_conda,
        "--log-dir",
        log_dir,
        "--appmap-command",
        appmap_command,
    ]

    if lint_command is not None:
        solve_args.extend(["--lint-command", lint_command])
    if steps is not None:
        solve_args.extend(["--steps", steps])

    # Run this as a separate process so that it can change the working directory.
    solve_result = run(solve_args, cwd=testbed)
    if solve_result.returncode != 0:
        print(f"Solver did not succeed for {instance['instance_id']}/{iteration + 1}.")
        return

    patch_result = run(
        ["git", "--no-pager", "diff"],
        check=True,
        cwd=testbed,
        capture_output=True,
        text=True,
    )
    return patch_result.stdout


def worker_init(data: dict):
    """
    Args:
        tasks (list): List of tasks
    """
    args = DotDict(data)

    assert args.output is not None
    assert args.appmap_command is not None
    assert args.path_conda is not None
    assert args.retries is not None

    output_file = abspath(args.output)
    for env_data in args.task_instances:
        env = DotDict(env_data)
        for instance in env.task_instances:
            with TaskEnvContextManager(
                        instance,
                        env.testbed,
                        env.venv,
                        env.log_dir,
                        env.conda_path,
                        timeout=env.timeout,
                        verbose=env.verbose,
                    ) as task_manager:
                try:
                    repo_prefix = instance["repo"].replace("/", "__")
                    env_name = f"{repo_prefix}__{instance['version']}"
                    testbed = Path(env.testbed)
                    log_dir = abspath(env.log_dir)
                    instance_id = instance["instance_id"]
                    retries = args.retries
                    issue_name = env_name

                    print(
                        f"[solve] ({instance_id}) Solver will make {retries} attempts to solve issue {issue_name}"
                    )
                    attempt_number = 0
                    while attempt_number < retries:
                        print(
                            f"[solve] ({instance_id}) Beginning solve attempt number {attempt_number + 1} of {retries}"
                        )

                        if not task_manager.reset_task_env(instance):
                            print(
                                f"[solve] ({instance_id}) Error resetting task environment"
                            )
                            return
                        
                        print(f"[solve] ({instance_id}) Installing environment for {instance_id}")
                        task_manager.run_install_task(instance)

                        extract_appmaps(instance, testbed)

                        patch = solve_instance(
                            args.instances_path,
                            instance,
                            log_dir,
                            testbed,
                            env.conda_path,
                            args.appmap_command,
                            args.lint_command,
                            attempt_number,
                            steps=args.steps,
                        )
                        if patch:
                            print(
                                f"[solve] ({instance_id}) Patch generated on iteration {attempt_number +1}"
                            )
                            print(patch)
                            output_results(instance, output_file, patch)
                            break
                        else:
                            print(
                                f"[solve] ({instance_id}) No patch generated"
                            )
                            attempt_number += 1
                            if attempt_number >= retries:
                                print(f"[solve] ({instance_id}) Giving up after {attempt_number} attempts")
                                output_results(instance, output_file, None)

                except Exception:
                    print(f"[solve] ({instance_id}) Error:")
                    import traceback

                    traceback.print_exc()


def extract_appmaps(instance, testbed):
    if not appmap_finder:
        return
    appmap_archive = appmap_finder.find_archive(
        instance["repo"].split("/")[-1] + "-" + instance["version"]
    )
    if appmap_archive is not None:
        print(f"AppMap archive: {appmap_archive}", flush=True)
        appmap_archive.extract(testbed)

def split_runner_instances(instances: list, num_runners: int, runner_index: int) -> list:
    """
    Split a list of instances into multiple groups based on the number of runners and the index of the runner.

    Args:
        instances (list): List of instances
        num_runners (int): Number of runners
        runner_index (int): Index of the runner
    Returns:
        list: List of instances for the given runner index
    """
    instances_per_runner = len(instances) // num_runners
    remainder = len(instances) % num_runners
    if runner_index == 0:
        # Lucky index 0 gets all the remainder instances
        return instances[:instances_per_runner + remainder]
    else:
        start_index = instances_per_runner * runner_index + remainder
        end_index = start_index + instances_per_runner
        return instances[start_index:end_index]


def solve_instances(task_instances, args):
    task_instances = split_instances(task_instances, args.num_workers)
    data_groups = [
        {
            "task_instances": g,
            "func": solve_instance,
            **vars(args),
        }
        for g in task_instances
    ]

    if args.num_workers == 1:
        worker_init(data_groups[0])
        return

    pool = Pool(processes=args.num_workers)
    pool.map(worker_init, data_groups)
    pool.close()
    pool.join()

def filter_instances(task_instances, filter):
    instances = None

    if filter:
        print(f"Filtering instances by regex: {args.filter}")
        pattern = re.compile(args.filter)
        instances = [
            instance
            for instance in task_instances
            if pattern.search(instance["instance_id"])
        ]

    # Sorting by instance ID allows us to easily split the workload across multiple runners with
    # minimal overlap between repositories and versions.
    instances = sorted(instances, key=lambda x: x['instance_id'], reverse=False)

    if args.num_runners > 1:
        print(f"Splitting {len(instances)} instances across {args.num_runners} runners")
        instances = split_runner_instances(instances, args.num_runners, args.runner_index)
        print(f"{len(instances)} instances scheduled for this runner:") 
        for instance in instances:
            print(f"- {instance['instance_id']}")

    return instances

def validate_args(args):
    """
    Validation for command line arguments
    """
    if not args.instances_path:
        raise ValueError("Must provide path to task instances")
    if not args.split:
        raise ValueError("Must provide split to use")
    if not args.log_dir:
        raise ValueError("Must provide log directory")
    if args.num_workers and args.num_workers < 1:
        raise ValueError("Number of workers must be a positive integer")
    if args.temp_dir and not os.path.exists(args.temp_dir):
        raise ValueError(f"Could not find temporary directory at {args.temp_dir}")
    if args.testbed and not os.path.exists(args.testbed):
        raise ValueError(f"Could not find testbed at {args.testbed}")
    if args.conda_link and not os.path.exists(args.conda_link):
        raise ValueError(f"Could not find conda installation at {args.conda_link}")
    if args.appmap_command and not os.path.exists(args.appmap_command):
        raise ValueError(f"Could not find appmap binary at {args.appmap_command}")
    if args.path_conda and not os.path.exists(args.path_conda):
        raise ValueError(f"Could not find conda installation at {args.path_conda}")
    if not args.retries:
        raise ValueError("Must provide number of retries")

def main(args):
    validate_args(args)

    dataset = load_data(args.instances_path, args.split)
    dataset = filter_instances(dataset, args.filter)

    with TestbedContextManager(
        dataset,
        args.log_dir,
        conda_link=args.conda_link,
        path_conda=args.path_conda,
        testbed=args.testbed,
        temp_dir=args.temp_dir,
        timeout=args.timeout,
        verbose=args.verbose,
        keep=args.keep,
    ) as tcm:
        distributed_task_list = tcm.get_distributed_tasks()
        solve_instances(distributed_task_list, args)


appmap_finder = None

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
    parser.add_argument(
        "--appmaps",
        type=str,
        nargs="?",
        const=True,
        help="Use AppMaps (with optional path to local AppMap archive directory)",
    )
    parser.add_argument(
        "--steps",
        type=str,
        help="Comma-separated list of solve steps to execute",
    )
    parser.add_argument(
        "--num_runners",
        type=int,
        default=1,
        help="Number of runners to split the workload across",
    )
    parser.add_argument(
        "--runner_index",
        type=int,
        default=0,
        help="Index of the runner to use",
    )
    args = parser.parse_args()
    if args.appmaps:
        if type(args.appmaps) is bool:
            appmap_path = None
            print(f"Using only online AppMap data archives")
        else:
            appmap_path = os.path.abspath(args.appmaps)
            print(f"Using AppMap data archives from {appmap_path} (and online)")

        # Don't load the ArchiveFinder unless appmap support is activated, because the 
        # 'github' dependency is hard to install on some systems.
        from appmap.archive import ArchiveFinder

        appmap_finder = ArchiveFinder(appmap_path)
    else:
        print("Not using AppMap data archives")
    main(args)
