import argparse
from copy import copy
import json
import os
import random
import re
import shutil
import sys
from multiprocessing import Pool, cpu_count
from pathlib import Path
from os.path import abspath
from subprocess import run
from textwrap import dedent
from typing import Optional

from datasets import Dataset

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(SCRIPT_DIR, ".."))

from solver.solve.solver import DEFAULT_STEPS, SolutionResponse

from solver.solve.data import load_data
from filelock import FileLock
from swebench.harness.context_manager import (
    TaskEnvContextManager,
    TestbedContextManager,
)
from swebench.harness.utils import DotDict, split_instances


def output_results(
    instance,
    output_file,
    solution: Optional[SolutionResponse],
    iteration: Optional[int],
):
    instance["model_name_or_path"] = "navie"
    if iteration is not None:
        instance["model_iteration"] = iteration

    if solution:
        solution_data = solution.to_dict()

        if "patch" in solution_data:
            instance["model_patch"] = solution_data.pop("patch")
            instance["model_patch_name"] = solution_data.pop("patch_name")

        for k, v in solution_data.items():
            instance_key = f"model_{k}"
            instance[instance_key] = v
    else:
        instance["model_patch"] = None

    with FileLock(f"{output_file}.lock"):
        with open(output_file, "a+") as f:
            f.write(json.dumps(instance) + "\n")

    print(f"[solve] Output written to {output_file}")


def solve_instance(
    instances_path,
    instance,
    log_dir,
    testbed,
    path_conda,
    appmap_command,
    lint_command,
    iteration,
    steps,
    temperature,
    maketest_retries,
) -> Optional[SolutionResponse]:
    print_disk_spaces(testbed)
    issue_dir = Path(log_dir) / "solve" / instance["instance_id"] / str(iteration + 1)
    issue_dir.mkdir(parents=True, exist_ok=True)
    issue_file = issue_dir / "issue.txt"
    with open(issue_file, "w") as f:
        f.write(instance["problem_statement"])

    output_file = issue_dir / "solution.json"

    solver_path = Path(__file__).parent / "solve" / "solver.py"
    appmap_config_file = Path(__file__).parent / ".." / "appmap.yml"

    print(f"Using appmap config file: {appmap_config_file.resolve()}")
    if not appmap_config_file.exists():
        raise FileNotFoundError(f"AppMap config file not found: {appmap_config_file}")

    solve_args = [
        # "env",
        # f"APPMAP_CONFIG={appmap_config_file.resolve()}",
        # "appmap-python",
        # "--record",
        # "process",
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
        "--temperature",
        str(temperature),
        "--maketest-retries",
        str(maketest_retries),
        "--output-file",
        output_file,
    ]

    if appmap_command is not None:
        solve_args.extend(["--appmap-command", appmap_command])
    if lint_command is not None:
        solve_args.extend(["--lint-command", lint_command])
    if steps is not None:
        solve_args.extend(["--steps", steps])

    # Run this as a separate process so that it can change the working directory.
    solve_result = run(solve_args, cwd=testbed)
    if solve_result.returncode != 0:
        print(
            f"Solver reported exit code {solve_result.returncode} for {instance['instance_id']}/{iteration + 1}."
        )

    if not output_file.exists():
        print(f"Solver did not produce output file {output_file}")
        return None

    return SolutionResponse.from_json(output_file.read_text())


def print_disk_space(path, description):
    total, used, free = shutil.disk_usage(path)
    print(
        f"{description} Disk Space - Total: {total // (2**30)} GB, Used: {used // (2**30)} GB, Free: {free // (2**30)} GB"
    )


def print_disk_spaces(testbed):
    # Check and print disk space for testbed
    testbed_fs_stat = os.statvfs(testbed)
    tmp_fs_stat = os.statvfs("/tmp")

    print_disk_space(testbed, "Testbed")

    # Check if testbed and /tmp are on the same filesystem
    if testbed_fs_stat.f_fsid != tmp_fs_stat.f_fsid:
        print_disk_space("/tmp", "/tmp")


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
    assert data_dict.maketest_retries is not None

    output_file = abspath(data_dict.output)
    appmap_command = data_dict.appmap_command

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
            suffix=data_dict.suffix,
        ) as tcm:
            for instance in data_dict.task_instances:
                repo_prefix = instance["repo"].replace("/", "__")
                env_name = f"{repo_prefix}__{instance['version']}{data_dict.suffix}"
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

                    retries = data_dict.retries
                    maketest_retries = data_dict.maketest_retries
                    issue_name = env_name

                    print(
                        f"[solve] ({instance_id}) Solver will make {retries} attempts to solve issue {issue_name}, with {maketest_retries} attempts to generate a test case"
                    )
                    attempt_number = 0

                    # “Quality” levels of the solution proposal, in increasing order.
                    # - `apply` applying the suggested patch(es) worked, and there are file changes resulting.
                    # - `lint_repair` the patch(es) have been linted, and any resulting problems (if any) have been fixed
                    # - `verify_failed` the patch(es) have been run against the test cases, but there are test failures that couldn’t be fixed
                    # - `verify` the patch(es) have been run against the test cases, and there are no test failures
                    # Not all “quality levels” may be available for a given run. For example, there may be no lint command,
                    # and verify may be disabled. In that case `apply` is the highest possible quality.
                    # The "highest possibly quality" is the first one in the list, since the list is reversed.

                    step_args = (
                        [k for k, v in DEFAULT_STEPS.items() if v]
                        if data_dict.steps is None
                        else data_dict.steps.split(",")
                    )
                    result_priority = []
                    if "apply" in step_args:
                        result_priority.append("apply")
                    if data_dict.lint_command is not None:
                        result_priority.append("lint_repair")
                    if "verify" in step_args:
                        result_priority.append("verify_failed")
                        result_priority.append("verify")
                    result_priority.reverse()

                    print(f"[solve] ({instance_id}) Result priority: {result_priority}")

                    solutions = []
                    solution_iterations = {}
                    temperature = data_dict.temperature
                    temperature_increase = data_dict.temperature_increase

                    try:
                        while attempt_number < retries:
                            print(
                                f"[solve] ({instance_id}) Beginning solve attempt number {attempt_number + 1} of {retries}"
                            )

                            if not task_manager.reset_task_env(
                                instance,
                                f"to prepare {instance_id} for solve attempt {attempt_number + 1}",
                            ):
                                print(
                                    f"[solve] ({instance_id}) Error resetting task environment"
                                )
                                return

                            print(
                                f"[solve] ({instance_id}) Installing environment for {instance_id}"
                            )
                            if not task_manager.run_install_task(
                                instance,
                                f"to prepare {instance_id} for solve attempt {attempt_number + 1}",
                            ):
                                print(
                                    f"[solve] ({instance_id}) Error installing environment"
                                )
                                return

                            solution = solve_instance(
                                data_dict.instances_path,
                                instance,
                                log_dir,
                                testbed,
                                data_dict.path_conda,
                                appmap_command,
                                data_dict.lint_command,
                                attempt_number,
                                data_dict.steps,
                                temperature,
                                maketest_retries,
                            )

                            if solution and solution.patch_name:
                                print(
                                    f"[solve] ({instance_id}) Solution generated with quality '{solution.patch_name}' on iteration {attempt_number + 1}"
                                )
                                solutions.append(solution)
                                solution_iterations[solution] = attempt_number
                                if solution.patch_name == SolutionResponse.BEST_PATCH:
                                    print(
                                        f"[solve] ({instance_id}) This is the highest solution quality level attainable. Exiting solve loop."
                                    )
                                    break
                            else:
                                print(
                                    f"[solve] ({instance_id}) No solution generated on iteration {attempt_number + 1}"
                                )

                            # No optimal solution generated, so try again; or give up if we've reached the maximum number of attempts.
                            attempt_number += 1
                            temperature += temperature_increase
                            if attempt_number >= retries:
                                print(
                                    f"[solve] ({instance_id}) Halting after {attempt_number} attempts"
                                )

                        if len(solutions) > 0:
                            solutions_sorted = copy(solutions)
                            solutions_sorted.sort()
                            solution = solutions_sorted[-1]
                            iteration = solution_iterations[solution]
                            output_results(
                                instance, output_file, solution, iteration + 1
                            )
                        else:
                            print(f"[solve] ({instance_id}) No patch generated")
                            output_results(instance, output_file, None, None)

                    except Exception:
                        print(f"[solve] ({instance_id}) Error:")
                        import traceback

                        traceback.print_exc()

    except Exception:
        print("Error instantiating testbed")
        import traceback

        traceback.print_exc()


def split_runner_instances(
    instances: list, num_runners: int, runner_index: int
) -> list:
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
        return instances[: instances_per_runner + remainder]
    else:
        start_index = instances_per_runner * runner_index + remainder
        end_index = start_index + instances_per_runner
        return instances[start_index:end_index]


def solve_instances(instances: Dataset, args):
    instance_set_path = None
    if args.instance_set:
        instance_set_path = (
            Path(__file__).parent / "instance_sets" / f"{args.instance_set}.txt"
        )
        with open(instance_set_path) as f:
            print(f"Using instance set: {instance_set_path}")
            instance_set = list(map(str.strip, f))
            instances = [
                instance
                for instance in instances
                if instance["instance_id"] in instance_set
            ]
    if args.filter:
        print(f"Filtering instances by regex: {args.filter}")
        pattern = re.compile(args.filter)
        instances = [
            instance
            for instance in instances
            if pattern.search(instance["instance_id"])
        ]
    if args.random_count:
        if isinstance(instances, Dataset):
            instances = instances.shuffle()
            instances = instances.take(args.random_count)
        else:
            instances = random.sample(instances, k=args.random_count)
    if len(instances) == 0:
        print(
            f"No instances selected (instance set: {instance_set_path}, filter: {args.filter})"
        )
        sys.exit(1)

    if args.num_runners > 1:
        # Shuffle the instances to ensure one worker doesn't get stuck with all the
        # long-running projects
        random.Random(args.seed).shuffle(instances)
        print(f"Splitting {len(instances)} instances across {args.num_runners} runners")
        instances = split_runner_instances(
            instances, args.num_runners, args.runner_index
        )
        print(f"{len(instances)} instances scheduled for this runner:")
        for instance in instances:
            print(f"- {instance['instance_id']}")

    instance_groups = split_instances(list(instances), args.num_workers)
    data_groups = [
        {
            "suffix": "" if args.reuse_env else f"-{i}",
            "task_instances": g,
            "func": solve_instance,
            **vars(args),
        }
        for i, g in enumerate(instance_groups)
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
    parser = argparse.ArgumentParser(
        epilog=dedent(
            """
                      The full set of instances is specified by --instances. A subset can be
                      selected by
                        --instance_set. That subset will be filtered further by --filter.
                       """
        )
    )

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
    parser.add_argument("--appmap_command", type=str, help="Path to appmap command")
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
    parser.add_argument(
        "--instance_set", type=str, help="(Optional) Name of instance set"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="(Optional) Random seed for shuffling instances",
    )
    parser.add_argument(
        "--random",
        help="Pick n (default=1) random instances from the dataset",
        type=int,
        const=1,
        nargs="?",
        dest="random_count",
    )
    parser.add_argument(
        "--reuse-env",
        help="Reuse environments instead of creating a new one per-instance (can lead to clobbering in CI!)",
        action="store_true",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="(Optional) The temperature to use when running the model",
    )
    parser.add_argument(
        "--temperature_increase",
        type=float,
        default=0.1,
        help="(Optional) The amount to increase the temperature by on each iteration",
    )
    parser.add_argument(
        "--maketest_retries",
        type=int,
        default=1,
        help="(Optional) Number of times to try and generate a test case for the issue",
    )
    args = parser.parse_args()
    main(args)
