import argparse
import json
import os
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
                    instance_id = instance["instance_id"]

                    try:
                        retries = data_dict.retries
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
                                data_dict.instances_path,
                                instance,
                                log_dir,
                                testbed,
                                data_dict.path_conda,
                                data_dict.appmap_command,
                                data_dict.lint_command,
                                attempt_number,
                                steps=data_dict.steps,
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
    except Exception:
        print("Error instantiating testbed")
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


def solve_instances(instances, args):
    if args.filter:
        print(f"Filtering instances by regex: {args.filter}")
        pattern = re.compile(args.filter)
        instances = [
            instance
            for instance in instances
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
