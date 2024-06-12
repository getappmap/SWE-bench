import os
import subprocess

from swebench.harness.constants import MAP_REPO_TO_TEST_FRAMEWORK

from ..format_instructions import format_instructions
from ..run_navie_command import run_navie_command
from ..run_command import run_command

from .erase_test_changes import erase_test_changes_from_file
from .step_pretest import build_task_manager


def step_posttest(
    work_dir,
    instances_path,
    instance_id,
    conda_path,
    conda_env,
    appmap_command,
    plan,
    file_content,
    test_files,
):
    test_files_str = ", ".join(test_files)
    print(
        f"[posttest] ({instance_id}) Running posttest for {instance_id}: {test_files_str}"
    )

    posttest_dir = os.path.join(work_dir, "posttest")
    posttest_log_dir = os.path.join(posttest_dir, "logs")
    os.makedirs(posttest_dir, exist_ok=True)
    os.makedirs(posttest_log_dir, exist_ok=True)

    # Run the diff command
    diff_command = f"git diff"
    file_diff = run_command(posttest_log_dir, diff_command, fail_on_error=True)
    print(f"[posttest] ({instance_id}) Current project diff:")
    print(file_diff)
    diff_file = os.path.join(posttest_log_dir, "solve.patch")
    with open(diff_file, "w") as f:
        f.write(file_diff)

    task_manager = build_task_manager(
        instances_path,
        instance_id,
        work_dir,
        conda_env,
        posttest_log_dir,
        conda_path,
        timeout=30,
        verbose=True,
    )

    instance = task_manager.instance
    test_cmd = MAP_REPO_TO_TEST_FRAMEWORK[instance["repo"]]
    print(
        f"[posttest] ({instance_id}) Test command for {instance['repo']} is {test_cmd}"
    )

    test_command = f"{task_manager.cmd_activate} && printenv && {test_cmd} "
    test_files_str = " ".join(test_files)

    print(
        f"[posttest] ({instance_id}) Running test command: {test_command} {test_files_str}"
    )
    timeout = False
    try:
        test_response = task_manager.exec(
            ["bash", "-c", f"{test_command} {test_files_str}"],
            timeout=task_manager.timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        timeout = True
        print(
            f"[posttest] ({instance_id}) Test command timed out: {test_command} {test_files_str}"
        )
        print(
            f"[posttest] ({instance_id}) Review {task_manager.log_file} for more information"
        )
        return True

    if test_response.returncode == 0:
        print(f"[posttest] ({instance_id}) Test command succeeded")
        return True

    print(
        f"[posttest] ({instance_id}) Test command failed: {test_command} {test_files_str}"
    )
    print(
        f"[posttest] ({instance_id}) Review {task_manager.log_file} for more information"
    )

    test_output = test_response.stdout

    repair_dir = os.path.join(work_dir, "test_repair")
    os.makedirs(repair_dir, exist_ok=True)

    repair_prompt, repair_output, repair_log = [
        os.path.join(repair_dir, f"generate.{ext}") for ext in ["txt", "md", "log"]
    ]
    repair_apply_prompt, repair_apply_output, repair_apply_log = [
        os.path.join(repair_dir, f"apply.{ext}") for ext in ["txt", "md", "log"]
    ]

    with open(repair_prompt, "w") as f:
        f.write(
            f"""@generate /noformat

A code base has been updated according to the instructions provided in the <plan> tag.
Test cases have been run, and there are some test errors. The test errors are indicated in the <test-errors> tag.

Fix the test errors indicated by the <test-errors> tag, while confirming to the intention of the
<plan> and without changing the code that is not indicated in the <test-errors> tag.

## Output format

{format_instructions()}

In the <original> and <modified> tags, do not emit line numbers. The line numbers are
only present in the file/content to help you identify which line has the lint error.

## Plan

<plan>
"""
        )
        f.write(plan)
        f.write(
            """
</plan>

## Error report

<test-errors>
"""
        )
        f.write(test_output)
        f.write(
            """
</test-errors>
"""
        )
        # Store each file name and text from file_content
        for file_name, file_text in file_content.items():
            file_lines = file_text.split("\n")
            file_text_with_line_numbers = "\n".join(
                [f"{i+1}: {line}" for i, line in enumerate(file_lines)]
            )
            f.write(
                f"""
<file>
<path>{file_name}</path>
<content>
{file_text_with_line_numbers}
</content>
</file>
"""
            )

    # Plan the repair
    print(f"[posttest] ({instance_id}) Generating code to fix test errors")
    run_navie_command(
        posttest_log_dir,
        command=appmap_command,
        input_path=repair_prompt,
        output_path=repair_output,
        log_path=repair_log,
    )

    print(
        f"[posttest] ({instance_id}) Code generated to repair source file in {repair_output}"
    )

    erase_test_changes_from_file(instance_id, repair_output)

    with open(repair_apply_prompt, "w") as f:
        f.write("@apply /all\n\n")
        with open(repair_output, "r") as plan_fp:
            f.write(plan_fp.read())

    print(f"[posttest] ({instance_id}) Applying changes to source files")
    run_navie_command(
        posttest_log_dir,
        command=appmap_command,
        input_path=repair_apply_prompt,
        output_path=repair_apply_output,
        log_path=repair_apply_log,
    )

    print(f"[posttest] ({instance_id}) Changes applied:")

    file_diff = run_command(posttest_log_dir, diff_command, fail_on_error=True)
    print(file_diff)
    repair_diff_file = os.path.join(posttest_log_dir, "solve_repair.patch")
    with open(repair_diff_file, "w") as f:
        f.write(file_diff)

    print(f"[posttest] ({instance_id}) Retesting.")

    print(
        f"[posttest] ({instance_id}) RETEST Running test command: {test_command} {test_files_str}"
    )
    timeout = False
    try:
        test_response = task_manager.exec(
            ["bash", "-c", f"{test_command} {test_files_str}"],
            timeout=task_manager.timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        print(
            f"[posttest] ({instance_id}) RETEST Test command timed out: {test_command} {test_files_str}"
        )
        print(
            f"[posttest] ({instance_id}) Review {task_manager.log_file} for more information"
        )
        # It didn't timeout initially, but now it's timed out after repair. That's a failure.
        return False

    if test_response.returncode != 0:
        print(
            f"[posttest] ({instance_id}) RETEST Test command failed: {test_command} {test_files_str}"
        )
        print(
            f"[posttest] ({instance_id}) RETEST Review {task_manager.log_file} for more information"
        )

        return False

    print(f"[posttest] ({instance_id}) RETEST Test command succeeded")
    return True
