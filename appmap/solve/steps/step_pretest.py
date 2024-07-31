import os
import subprocess

import yaml

from appmap.solve.steps.count_appmaps import count_appmaps
from appmap.solve.steps.index_appmaps import index_appmaps
from appmap.solve.steps.read_test_directives import read_test_directives
from appmap.solve.steps.run_test import run_test
from swebench.harness.constants import MAP_REPO_TO_TEST_FRAMEWORK
from swebench.harness.context_manager import TaskEnvContextManager

from ...data import load_data
from ..log import log_command

from ..run_command import run_command


def build_task_manager(
    instances_path,
    instance_id,
    testbed,
    conda_env,
    log_dir,
    conda_path,
    timeout,
    verbose,
):
    testbed = os.path.abspath(os.path.join(os.getcwd(), os.pardir))
    dev_dataset = load_data(instances_path, "dev")
    test_dataset = load_data(instances_path, "test")

    instance = next(
        (inst for inst in test_dataset if inst["instance_id"] == instance_id), None
    )
    if not instance:
        instance = next(
            (inst for inst in dev_dataset if inst["instance_id"] == instance_id), None
        )

    if not instance:
        raise ValueError(
            f"Could not find instance {instance_id} in dev or test datasets of {instances_path}"
        )

    return TaskEnvContextManager(
        instance,
        testbed,
        conda_env,
        log_dir,
        conda_path=conda_path,
        timeout=timeout,
        verbose=verbose,
    )


def step_pretest(
    log_dir,
    work_dir,
    instances_path,
    instance_id,
    conda_path,
    conda_env,
    appmap_command,
):
    print(
        f"[pretest] ({instance_id}) Running tests for {instance_id} using {conda_env} in {conda_path}"
    )

    tcm = build_task_manager(
        instances_path,
        instance_id,
        work_dir,
        conda_env,
        log_dir,
        conda_path,
        timeout=30,
        verbose=True,
    )

    appmap_available = False
    try:
        tcm.exec(["bash", "-c", f"{tcm.cmd_activate} && pip install appmap"])
        print(f"[pretest] ({instance_id}) appmap package installed to {conda_env}")
        appmap_available = True
    except RuntimeError:
        print(
            f"[pretest] ({instance_id}) appmap package installation to {conda_env} failed"
        )
        appmap_available = False

    test_files = read_test_directives(tcm.instance)

    test_file_str = ", ".join(test_files)
    print(f"[pretest] ({instance_id}) Running test files: {test_file_str}")

    # Run three of the files using conda activate and the test command (e.g. pytest)
    test_succeeded_files = []
    test_failed_files = []
    for test_file in test_files:
        (succeeded,) = run_test(tcm, test_file, appmap_available)

        if succeeded:
            test_succeeded_files.append(test_file)
        else:
            test_failed_files.append(test_file)

        if len(test_succeeded_files) + len(test_failed_files) >= 3:
            print(f"[pretest] ({instance_id}) Ran 3 test files, stopping")
            break

    appmap_count = count_appmaps()
    if appmap_count > 0:
        index_appmaps(instance_id, log_dir, appmap_command)

    if len(test_succeeded_files) == 0:
        print(f"[pretest] ({instance_id}) WARN: No tests succeeded in pretest.")
    else:
        test_succeeded_files_str = ", ".join(test_succeeded_files)
        print(
            f"[pretest] ({instance_id}) {len(test_succeeded_files)} tests succeeded in pretest: {test_succeeded_files_str}"
        )

    return test_succeeded_files
