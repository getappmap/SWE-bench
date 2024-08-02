import os

import yaml
from appmap.navie.editor import Editor
from appmap.navie.fences import extract_fenced_content
from appmap.solve.steps.run_test import run_test


def maketest(
    tcm,
    issue_file,
    work_dir,
    test_number,
):
    print(f"[maketest] Generating a test case to verify the solution to {issue_file}")

    with open(issue_file, "r") as f:
        issue_content = f.read()

    work_dir = os.path.join(work_dir, "maketest", str(test_number))

    test_to_modify_str = Editor(os.path.join(work_dir, "choose")).search(
        f"""Identify a single test case that is most related to the following issue:

{issue_content}
""",
        format="""## Format instructions
        
Output the result as the file path, and nothing else. Example:

project/tests/model_test.py
""",
        extension="txt",
    )

    tests_to_modify_lines = "\n".join(extract_fenced_content(test_to_modify_str))
    tests_to_modify = tests_to_modify_lines.split("\n")

    # Expect exactly one file
    if len(tests_to_modify) != 1:
        print(f"Expected exactly one file, got {test_to_modify_str}")
        return {"succeeded": False, "test_error": "Expected exactly one file"}

    test_to_modify = tests_to_modify[0]
    test_to_modify = os.path.relpath(test_to_modify, os.getcwd())

    print(f"[maketest] Modifying test case {test_to_modify}")

    with open(test_to_modify, "r") as f:
        test_content = f.read()

    navie = Editor(os.path.join(work_dir, "generate"))
    navie.context(issue_content, exclude_pattern="test")

    test_prompt = f"""## Task

Modify this test case to verify the solution to the described issue:

<test>
{test_content}
</test>

## Output instructions

The output should contain only a single test case. 

Remove all test cases from the original file, except the one that you
are modifying or creating.

The test case MUST FAIL if the issue is NOT FIXED.

Be sure to emit all needed imports.

Output only the code, and nothing else.
"""

    raw_code = navie.test(issue_content, prompt=test_prompt)

    codes = extract_fenced_content(raw_code)
    if not codes or len(codes) != 1:
        print(f"Expected exactly one code block, got {len(codes)}")
        return {succeeded: False, test_error: "Expected exactly one code block"}

    raw_code = codes[0]

    # Append a suffix to the test_to_modify file name.
    # Example: test_to_modify = "test.py", modified_file_name = "test_modified.py"
    test_file = test_to_modify.replace(".py", f"_maketest_{test_number}.py")

    print(f"[maketest] Writing test case to {test_file}")

    with open(test_file, "w") as f:
        f.write(raw_code)

    # TODO: Don't record appmap data of the test yet
    # succeeded, test_error = run_test(tcm, test_file, appmap=True)
    # appmap_count = count_appmaps()
    # if appmap_count:
    #     instance_id = tcm.instance["instance_id"]
    #     index_appmaps(instance_id, log_dir, appmap_command)

    succeeded, test_error = run_test(tcm, test_file)

    # Verify that the test_error indicates that the issue is being reproduced
    fails_for_expected_reason = False
    if succeeded:
        print(f"[maketest] Test case {test_file} succeeded. This is unexpected!")
    else:
        print(
            f"[maketest] Test case {test_file} failed. This is expected. Let's see if it failed for the right reason."
        )

        if "ERROR" in test_error:
            error_lines = test_error.split("\n")
            # Find everything after the first line that includes "ERROR", "FAIL", or "activate successful"
            first_line_index_with_error = next(
                i
                for i, line in enumerate(error_lines)
                if "ERROR" in line or "FAIL" in line or "activate successful" in line
            )
            test_error = "\n".join(error_lines[first_line_index_with_error:])

        whyfailed = Editor(os.path.join(work_dir, "check")).ask(
            f"""A test case has been created that is currently expected to fail due to a known issue.

Examine the error message below to determine if the test case is failing for the expected reason.

<error>
{test_error}
</error>

<issue>
{issue_content}
</issue>
""",
            context=[],
            prompt="""## Output format
            
Emit a single word that indicates whether the test error is consistent with the described issue.

- Emit "yes" if the test error is consistent with the described issue.
- Emit "no" if the test error is NOT consistent with the described issue.
""",
        )

        if whyfailed != "yes":
            print(
                f"[maketest] Test case {test_file} failed for an unexpected reason: {whyfailed}"
            )
        else:
            fails_for_expected_reason = True
            print(
                f"[maketest] Test case {test_file} failed for the expected reason: {whyfailed}"
            )

    return {
        "test_file": test_file,
        "succeeded": succeeded,
        "test_error": test_error,
        "fails_for_expected_reason": fails_for_expected_reason,
    }


def step_maketest(
    tcm,
    issue_file,
    work_dir,
    num_attempts,
):
    # Try N times to generate a test that fails for the right reason
    test_files = []
    for i in range(num_attempts):
        test_result = maketest(tcm, issue_file, work_dir, i + 1)
        if (
            "fails_for_expected_reason" in test_result
            and "test_file" in test_result
            and test_result["fails_for_expected_reason"]
        ):
            test_files.append(test_result["test_file"])
            # TODO: Allow it to generate more than one test, if they are diverse.
            break

    if len(test_files) == 0:
        print(
            f"[maketest] Failed to generate a test case that fails for the right reason"
        )

    return test_files
