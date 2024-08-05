import os
import subprocess

from solve.run_command import run_command
from solve.steps.test_files_to_modules import test_files_to_modules
from swebench.harness.constants import MAP_REPO_TO_TEST_FRAMEWORK


def run_test(tcm, test_file, appmap=False, files_to_directives=True):
    print(f"[run_test] Running test {test_file}")

    instance = tcm.instance
    if files_to_directives and instance["repo"] == "django/django":
        test_files = test_files_to_modules([test_file])
        test_files_str = ", ".join(test_files)
        print(f"[run_test] Converted django test file to module: {test_files_str}")
        test_file = test_files[0]

    instance_id = instance["instance_id"]

    test_cmd = MAP_REPO_TO_TEST_FRAMEWORK[instance["repo"]]

    env = None
    test_command = f"{tcm.cmd_activate} && "
    if appmap:
        test_command += "appmap-python "
        env = {
            "APPMAP_DISPLAY_PARAMS": "false",
            "APPMAP_MAX_EVENTS": "10000",
            "APPMAP_MAX_TIME": "10",
            "PYTHONUNBUFFERED": "1",
        }
    test_command += f"{test_cmd} "

    print(
        f"[runtest] ({instance_id}) ({instance_id}) Running test command: {test_command} {test_file}"
    )

    with open(tcm.log_file, "r") as f:
        base_log_content = f.read()
        base_log_line_count = len(base_log_content.split("\n"))

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
            f"[runtest] ({instance_id}) Test command timed out: {test_command} {test_file}"
        )
        timeout = True

    succeeded = False
    test_error = None
    if test_output and test_output.returncode == 0:
        print(f"[runtest] ({instance_id}) Test passed")
        succeeded = True
    else:
        if not timeout:
            print(
                f"[runtest] ({instance_id}) Test command failed: {test_command} {test_file}"
            )
            print(
                f"[runtest] ({instance_id}) Review {tcm.log_file} for more information"
            )

            with open(tcm.log_file, "r") as f:
                log_content = f.read()
                log_lines = log_content.split("\n")
                # Select log_lines after base_log_line_count
                test_error = "\n".join(log_lines[base_log_line_count:])

    return (succeeded, test_error)
