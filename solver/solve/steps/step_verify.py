import os

from navie.editor import Editor
from navie.extract_changes import extract_changes
from solve.steps.run_test import run_test
from swebench.harness.constants import MAP_REPO_TO_TEST_FRAMEWORK

from navie.format_instructions import xml_format_instructions
from ..run_navie_command import run_navie_command
from ..run_command import run_command

from .erase_test_changes import erase_test_changes_from_file


def repair_test(
    task_manager,
    log_dir,
    work_dir,
    instance_id,
    test_directive,
    diff_command,
    test_output,
    file_content,
):
    # Sanitize the test directive (a filename-ish) to be suitable as a slug or pathname component.
    # Replace all non-alphanumeric characters with underscores.
    test_directive_slug = "".join(
        c if c.isalnum() else "_" for c in test_directive
    ).strip("_")

    repair_dir = os.path.join(work_dir, "test_repair", test_directive_slug)
    os.makedirs(repair_dir, exist_ok=True)

    repair_question, repair_prompt, repair_output, repair_log = [
        os.path.join(repair_dir, f"generate.{ext}")
        for ext in ["txt", "prompt.md", "md", "log"]
    ]

    with open(repair_question, "w") as f:
        f.write(
            """@generate /noformat

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

    with open(repair_prompt, "w") as f:
        f.write(
            f"""# Repair Plan

A test case has failed. The errors emitted by the test case are provided in the <test-errors> tag.

Fix the test errors in any of the provided <file>, without changing the intended behavior of the code.

## Output format

{xml_format_instructions()}

In the <original> and <modified> tags, do not emit line numbers. The line numbers are
only present in the file/content to help you identify which line has the lint error.

"""
        )

    # TODO: test_output can be large, and cause an LLM overflow. We should limit the size of test_output,
    # and/or prune it to only include the relevant parts.

    # Plan the repair
    print(f"[verify/repair] ({instance_id}) Generating code to fix test errors")
    run_navie_command(
        log_dir,
        input_path=repair_question,
        output_path=repair_output,
        prompt_path=repair_prompt,
        log_path=repair_log,
    )

    print(
        f"[verify/repair] ({instance_id}) Code generated to repair source file in {repair_output}"
    )

    erase_test_changes_from_file(instance_id, repair_output)
    with open(repair_output, "r") as f:
        repair_output_content = f.read()

    changes = extract_changes(repair_output_content)
    for change in changes:
        print(f"[verify/repair] ({instance_id}) Change: {change}")
        Editor(os.path.join(repair_dir, "repair.log")).apply(
            change.file,
            change.modified,
            search=change.original,
        )

    print(f"[verify/repair] ({instance_id}) Changes applied:")

    file_diff = run_command(log_dir, diff_command, fail_on_error=True)
    print(file_diff)
    repair_diff_file = os.path.join(log_dir, "solve_repair.patch")
    with open(repair_diff_file, "w") as f:
        f.write(file_diff)

    print(f"[verify/repair] ({instance_id}) Retesting: {test_directive}")

    (succeeded, test_output) = run_test(
        task_manager, test_directive, files_to_directives=False
    )

    if not succeeded:
        print(f"[verify/repair] ({instance_id}) Test failed: {test_directive}")
        print(
            f"[verify/repair] ({instance_id}) Review {task_manager.log_file} for more information"
        )

        return False

    print(f"[verify/repair] ({instance_id}) Test succeeded")
    return True


def step_verify(
    task_manager,
    work_dir,
    instance_id,
    file_content,
    test_directives,
):
    test_files_str = ", ".join(test_directives)
    print(
        f"[verify] ({instance_id}) Running verify for {instance_id}: {test_files_str}"
    )

    verify_dir = os.path.join(work_dir, "verify")
    verify_log_dir = os.path.join(verify_dir, "logs")
    os.makedirs(verify_dir, exist_ok=True)
    os.makedirs(verify_log_dir, exist_ok=True)

    # Run the diff command
    diff_command = "git diff"
    file_diff = run_command(verify_log_dir, diff_command, fail_on_error=True)
    print(f"[verify] ({instance_id}) Current project diff:")
    print(file_diff)
    diff_file = os.path.join(verify_log_dir, "solve.patch")
    with open(diff_file, "w") as f:
        f.write(file_diff)

    test_directives_succeeded = []
    for test_directive in test_directives:
        print(f"[verify] ({instance_id}) Running test: {test_directive}")
        succeeded, test_output = run_test(
            task_manager, test_directive, files_to_directives=False
        )

        if not succeeded:
            repaired = repair_test(
                task_manager,
                verify_dir,
                work_dir,
                instance_id,
                test_directive,
                diff_command,
                test_output,
                file_content,
            )
            if repaired:
                succeeded = True

        if succeeded:
            test_directives_succeeded.append(test_directive)

    return test_directives_succeeded
