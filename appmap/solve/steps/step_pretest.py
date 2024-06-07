import os
import subprocess

import yaml

from swebench.harness.constants import MAP_REPO_TO_TEST_FRAMEWORK
from swebench.harness.context_manager import TaskEnvContextManager

from ...data import load_data
from ..log import log_command

from ..run_command import run_command
from ..run_navie_command import run_navie_command


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
    issue_file,
):
    print(
        f"[pretest] ({instance_id}) Running tests for {instance_id} using {conda_env}"
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
    # TODO: Think about re-enabling this.``
    # try:
    #     tcm.exec(["bash", "-c", f"{tcm.cmd_activate} && pip install appmap"])
    #     appmap_available = True
    # except RuntimeError:
    #     appmap_available = False

    try:
        tcm.exec(
            ["bash", "-c", f"{tcm.cmd_activate} && pip install pytest-test-groups"]
        )
    except RuntimeError:
        print("Failed to install pytest-test-groups, continuing without it")

    include_pattern = "^(.*[\\/])?(tests?/.*|.*_test\\.py|.*_spec\\.py|test_.*\\.py)$"

    input_path = os.path.join(work_dir, "pretest.txt")
    output_path = os.path.join(work_dir, "pretest_context.yml")
    log_path = os.path.join(work_dir, "pretest.log")

    with open(input_path, "w") as pretest_f:
        # TODO: 5/6/24 There's no server-side support for /includepattern yet, actually.
        pretest_f.write(
            f"""@context /format=yaml /nofence /includepattern={include_pattern}
            
Search exclusively for test cases.
"""
        )

    run_navie_command(
        log_dir,
        command=appmap_command,
        context_path=issue_file,
        input_path=input_path,
        output_path=output_path,
        log_path=log_path,
    )

    print(f"[pretest] ({instance_id}) Context stored in {output_path}")

    # Load pretest context as YAML
    test_files = []
    with open(output_path, "r") as f:
        pretest_context = yaml.safe_load(f)

    # Each context item consists of directory, type, content, and location
    for item in pretest_context:
        if item["type"] != "code-snippet":
            continue

        location = item["location"]
        path = location.split(":")[0]
        if not path.endswith(".py"):
            continue
        if not "test" in path:  # TODO: Make this more robust
            continue

        directory = item["directory"]
        full_path = os.path.join(directory, path)
        relative_path = os.path.relpath(full_path, os.getcwd())
        if os.path.exists(relative_path) and relative_path not in test_files:
            test_files.append(relative_path)

    if len(test_files) == 0:
        print(f"[pretest] ({instance_id}) WARN: No relevant test files detected")
        return []

    test_file_str = ", ".join(test_files)
    print(f"[pretest] ({instance_id}) Selected test files: {test_file_str}")

    if "django" in instance_id:
        print(
            f"[pretest] ({instance_id}) Converting Django test files to module format"
        )
        # The test file path will be something like: tests/template_tests/syntax_tests/test_autoescape.py
        # The Django test runner wanst to see it as: template_tests.syntax_tests.test_autoescape
        test_files = [
            test_file.replace("/", ".").replace(".py", "") for test_file in test_files
        ]
        # Strip the leading 'tests.' from the path
        test_files = [test_file.replace("tests.", "", 1) for test_file in test_files]
        print(
            f"[pretest] ({instance_id}) Converted test files to modules: {test_files}"
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
        print(f"[pretest] ({instance_id}) No tests succeeded in pretest.")
    else:
        test_succeeded_files_str = ", ".join(test_succeeded_files)
        print(
            f"[pretest] ({instance_id}) {len(test_succeeded_files)} tests succeeded in pretest: {test_succeeded_files_str}"
        )

    return test_succeeded_files
