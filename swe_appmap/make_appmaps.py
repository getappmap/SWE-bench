import argparse
import faulthandler
import fnmatch
import glob
import itertools
import json
import os
import re
import signal
import subprocess
import sys
import tarfile
from multiprocessing import Pool, cpu_count
from swebench.harness.constants import (
    MAP_REPO_TO_TEST_FRAMEWORK,
    MAP_VERSION_TO_INSTALL,
)
from swebench.harness.context_manager import (
    TaskEnvContextManager,
    TestbedContextManager,
)
from swebench.harness.utils import DotDict, split_instances
from swebench.metrics.getters import get_eval_refs

faulthandler.register(signal.SIGUSR1)

SKIP_INSTANCES = {"pytest-dev/pytest": ["6387", "7956", "3805"]}


appmap_bin = None


def validate_args(args):
    """
    Validation for command line arguments
    """
    if not os.path.exists(args.log_dir):
        raise ValueError(f"Could not find log directory at {args.log_dir}")
    if not os.path.exists(args.appmap_archive_dir):
        raise ValueError(f"Could not find log directory at {args.appmap_archive_dir}")
    args.appmap_archive_dir = os.path.abspath(args.appmap_archive_dir)

    # If value is provided, check that the paths exist
    if args.path_conda is not None and not os.path.exists(args.path_conda):
        raise ValueError(f"Could not find conda installation at {args.path_conda}")
    if args.testbed is not None and not os.path.exists(args.testbed):
        raise ValueError(f"Could not find testbed at {args.testbed}")
    if args.temp_dir is not None and not os.path.exists(args.temp_dir):
        raise ValueError(f"Could not find temporary directory at {args.temp_dir}")

    # If value is provided, check that it is valid
    if args.timeout is not None and args.timeout < 0:
        raise ValueError("Timeout must be a positive integer")
    if args.num_workers is not None and args.num_workers < 1:
        raise ValueError("Number of workers must be a positive integer")

    if not os.path.exists(appmap_bin):
        raise ValueError(f"Could not find appmap binary at {args.appmap_bin}")


def make_appmaps(data: dict):
    """
    Sets up task environment context manager.
    Then appmap python package is installed and tests are ran
    (taken from the context of first task instance).
    If successful, the appmaps are archived.

    Args:
        data: Dict containing task instances and other data
            task_instances: List of task instances
            appmap_archive_dir: Path to archive appmaps to
            + setup_testbed args
    """
    data_dict = DotDict(data)
    task_instance = data_dict.task_instances[0]
    archive_name = os.path.join(
        data_dict.appmap_archive_dir,
        f"{task_instance['repo'].split('/')[-1]}-{task_instance['version']}.tar.xz",
    )
    if os.path.isfile(archive_name):
        print(f"{archive_name} already exists, skipping")
        return
    with TaskEnvContextManager(
        task_instance,
        data_dict.testbed,
        data_dict.venv,
        data_dict.log_dir,
        data_dict.conda_path,
        verbose=data_dict.verbose,
        timeout=data_dict.timeout,
        log_suffix=data_dict.log_suffix,
    ) as tcm:
        tcm.reset_task_env(
            task_instance, "to prepare to make AppMap data using appmap-python"
        )
        tcm.run_install_task(
            task_instance, "to prepare to make AppMap data using appmap-python"
        )
        tcm.log.write("Installing appmap")
        tcm.exec(["bash", "-c", f"{tcm.cmd_activate} && pip install appmap"])
        spec = MAP_VERSION_TO_INSTALL[task_instance["repo"]][task_instance["version"]]
        if "appmap" in spec:
            with open("appmap.yml", "w") as f:
                f.write(spec["appmap"])
        task_instance["test_cmd"] = MAP_REPO_TO_TEST_FRAMEWORK[
            task_instance["repo"]
        ]  # run all tests

        envvars = {k: v for k, v in os.environ.items() if k.startswith("APPMAP_")}
        envvars = {
            "APPMAP_DISPLAY_PARAMS": "false",
            "PYTHONUNBUFFERED": "1",
            **envvars,
        }
        envvars = " ".join([f"{k}={v}" for k, v in envvars.items()])
        tcm.exec(
            ["bash", "-c", f"{tcm.cmd_activate} && conda env config vars set {envvars}"]
        )
        tcm.log.write(f"Running tests with appmap with {envvars}")
        test_cmd = f"appmap-python {task_instance['test_cmd']}"
        if spec.get("use_pytest", True):
            tcm.run_pytest_tests(task_instance, test_cmd)
        else:
            tcm.run_tests_task(task_instance, test_cmd)
        tcm.log.write("Uninstalling appmap")
        tcm.exec(["bash", "-c", f"{tcm.cmd_activate} && pip uninstall -y appmap"])
        # count .appmap.json files in testbed/tmp/appmap (recursively)
        appmaps = glob.glob(
            os.path.join(data_dict.testbed, "tmp", "appmap", "**", "*.appmap.json"),
            recursive=True,
        )
        if len(appmaps) == 0:
            tcm.log.write("No appmaps created")
            return
        # index appmaps
        tcm.log.write(f"Indexing {len(appmaps)} appmaps")
        subprocess.run([appmap_bin, "index", "-d", data_dict.testbed], check=True)
        # archive appmaps
        tcm.log.write(f"Archiving {len(appmaps)} appmaps to {archive_name}")
        with tarfile.open(archive_name, "w:xz") as tar:
            tar.add(os.path.join(data_dict.testbed, "tmp", "appmap"), "tmp/appmap")
            tar.add(os.path.join(data_dict.testbed, "appmap.yml"), "appmap.yml")


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
        keep=data_dict.keep,
        suffix=data_dict.suffix,
    ) as tcm:
        distributed_task_list = tcm.get_distributed_tasks()
        for task_list in distributed_task_list:
            print(
                f"{task_list['testbed']}: {len(task_list['task_instances'])} instances"
            )
            task_list["appmap_archive_dir"] = data_dict.appmap_archive_dir

        if len(distributed_task_list) == 1:
            data_dict.func(distributed_task_list[0])
            return

        pool = Pool(processes=len(distributed_task_list))
        pool.map(data_dict.func, distributed_task_list)
        pool.close()
        pool.join()


def main(args):
    """
    Splits task instances into multiple groups if num_workers > 1
    """
    if args.num_workers is None:
        args.num_workers = cpu_count()

    task_instances = list(get_eval_refs(args.instances_path).values())

    # filter by optional filter
    if args.filter and args.filter != "*":
        task_instances = [
            task_instance
            for task_instance in task_instances
            if args.filter in task_instance["instance_id"]
        ]
        if args.show_instances:

            def filter_keys(dicts):
                keys_to_keep = ["instance_id", "version", "environment_setup_commit"]
                ret = filter(
                    lambda d: fnmatch.fnmatchcase(d["version"], args.show_instances),
                    [{k: v for k, v in d.items() if k in keys_to_keep} for d in dicts],
                )
                return sorted(ret, key=lambda d: d["instance_id"])

            json.dump(filter_keys(task_instances), indent=2, fp=sys.stdout)
            print()
            sys.exit(0)

    # group by repo-version
    rv_groups = itertools.groupby(task_instances, lambda x: (x["repo"], x["version"]))

    # pick first instance from each group
    task_instances = [next(g) for _, g in rv_groups]

    task_instances_groups = split_instances(task_instances, args.num_workers)

    data_groups = [
        {
            "suffix": "" if args.reuse_env else f"-{i}",
            "task_instances": g,
            "func": make_appmaps,
            **vars(args),
        }
        for i, g in enumerate(task_instances_groups)
    ]

    for group in data_groups:
        del group["instances_path"]

    if args.num_workers == 1:
        setup_testbed(data_groups[0])
        return

    pool = Pool(processes=args.num_workers)
    pool.map(setup_testbed, data_groups)
    pool.close()
    pool.join()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--instances_path",
        type=str,
        help="Path to candidate task instances file",
        required=True,
    )
    parser.add_argument(
        "--log_dir", type=str, help="Path to log directory", required=True
    )
    parser.add_argument(
        "--appmap_archive_dir",
        type=str,
        help="Path to archive appmaps to",
        required=True,
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
        "--verbose",
        action="count",
        default=0,
        help="(Optional)Verbose mode, specify multiple times for more verbose output",
    )
    parser.add_argument(
        "--num_workers", type=int, default=None, help="(Optional) Number of workers"
    )
    parser.add_argument(
        "--appmap_bin",
        type=str,
        help="path to appmap binary",
        default="~/.appmap/bin/appmap",
    )
    parser.add_argument(
        "--filter",
        type=str,
        help="(Optional) Filter to apply to task instances",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="(Optional) Keep temporary directories after running",
    )
    parser.add_argument(
        "--show_instances",
        nargs="?",
        const="*",
        help="(Optional) Show instances that match version",
    )
    parser.add_argument(
        "--reuse_env",
        help="Reuse environments instead of creating a new one per-instance (can lead to clobbering in CI!)",
        action="store_true",
    )

    args = parser.parse_args()
    appmap_bin = os.path.expanduser(args.appmap_bin)
    validate_args(args)
    main(args)
