import os
import subprocess

import yaml

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
    datasets = load_data(instances_path)

    instance = None
    for _, split in datasets.items():
        g = (i for i in split if i["instance_id"] == instance_id)
        instance = next(g, None)
        if instance is not None:
            break

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
    test_files,
):
    print(
        f"[pretest] ({instance_id}) Running tests for {instance_id} using {conda_env}"
    )

    appmap_available = False
    # TODO: Think about re-enabling this.``
    # try:
    #     tcm.exec(["bash", "-c", f"{tcm.cmd_activate} && pip install appmap"])
    #     appmap_available = True
    # except RuntimeError:
    #     appmap_available = False

    test_file_str = ", ".join(test_files)
    print(f"[pretest] ({instance_id}) Running test files: {test_file_str}")

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

    instance = tcm.instance
    test_cmd = MAP_REPO_TO_TEST_FRAMEWORK[instance["repo"]]

    env = None
    test_command = f"{tcm.cmd_activate} && "
    if appmap_available:
        test_command += f"appmap-python "
        env = {
            "APPMAP_DISPLAY_PARAMS": "false",
            "APPMAP_MAX_EVENTS": "10000",
            "APPMAP_MAX_TIME": "10",
            "PYTHONUNBUFFERED": "1",
        }
    test_command += f"{test_cmd} "

    def count_appmaps():
        count = 0
        for root, _, files in os.walk("tmp/appmap"):
            for file in files:
                if file.endswith(".appmap.json"):
                    file_path = os.path.join(root, file)
                    file_size = os.path.getsize(file_path)
                    if 10 * 1024 <= file_size < 40 * 1024 * 1024:
                        count += 1
        return count

    # Run three of the files using conda activate and the test command (e.g. pytest)
    test_succeeded_files = []
    test_failed_files = []
    appmap_count = 0
    for test_file in test_files:
        print(
            f"[pretest] ({instance_id}) ({instance_id}) Running test command: {test_command} {test_file}"
        )
        test_output = None
        timeout = False
        try:
            test_output = tcm.exec(
                ["bash", "-c", f"{test_command} {test_file}"],
                timeout=tcm.timeout,
                check=False,
                env=env,
            )
        except subprocess.TimeoutExpired:
            print(
                f"[pretest] ({instance_id}) Test command timed out: {test_command} {test_file}"
            )
            timeout = True

        if test_output and test_output.returncode == 0:
            test_succeeded_files.append(test_file)
            print(f"[pretest] ({instance_id}) Tests passed")
        else:
            test_failed_files.append(test_file)
            if not timeout:
                print(
                    f"[pretest] ({instance_id}) Test command failed: {test_command} {test_file}"
                )
            print(
                f"[pretest] ({instance_id}) Review {tcm.log_file} for more information"
            )

        if appmap_available:
            new_appmap_count = count_appmaps()
            print(
                f"[pretest] ({instance_id}) Generated {new_appmap_count - appmap_count} good AppMap data files"
            )
            appmap_count = new_appmap_count

        if appmap_count >= 100:
            print(
                f"[pretest] ({instance_id}) Generated 100 good AppMap data files, stopping"
            )
            break
        if len(test_succeeded_files) + len(test_failed_files) >= 3:
            print(f"[pretest] ({instance_id}) Ran 3 test files, stopping")
            break

    if appmap_count > 0:
        print(f"[pretest] ({instance_id}) Indexing AppMap data")
        try:
            run_command(log_dir, command=f"{appmap_command} index", fail_on_error=True)
        except RuntimeError as e:
            print(
                f"[pretest] ({instance_id}) AppMap data indexing failed: {e} {e.output}"
            )
        else:
            print(f"[pretest] ({instance_id}) Index complete")

    if len(test_succeeded_files) == 0:
        print(f"[pretest] ({instance_id}) WARN: No tests succeeded in pretest.")
    else:
        test_succeeded_files_str = ", ".join(test_succeeded_files)
        print(
            f"[pretest] ({instance_id}) {len(test_succeeded_files)} tests succeeded in pretest: {test_succeeded_files_str}"
        )

    return test_succeeded_files
