import os

import yaml
from appmap.navie.editor import Editor
from appmap.navie.fences import extract_fenced_content
from appmap.solve.steps.count_appmaps import count_appmaps
from appmap.solve.steps.index_appmaps import index_appmaps
from appmap.solve.steps.run_test import run_test


def step_maketest(
    tcm,
    log_dir,
    appmap_command,
    issue_file,
    work_dir,
):
    print(f"[maketest] Generating a test case to verify the solution to {issue_file}")

    with open(issue_file, "r") as f:
        issue_content = f.read()

    work_dir = os.path.join(work_dir, "maketest")

    test_to_modify_str = Editor(os.path.join(work_dir, "choosetest")).search(
        f"""Identify a single test case that is most related to the following issue:
                                  
{issue_content}
""",
        format="""## Format instructions
        
Output the result as a YAML list of file paths, and nothing else.
""",
    )
    print(f"[maketest] Test case to modify: {test_to_modify_str}")
    tests_to_modify = extract_fenced_content(test_to_modify_str)
    if not tests_to_modify:
        print(f"No test cases found to modify.")
        return {succeeded: False, test_error: "No test cases found to modify"}
    if len(tests_to_modify) != 1:
        print(f"Expected exactly one file, got {len(tests_to_modify)}")
        return {succeeded: False, test_error: "Expected exactly one file"}

    tests_to_modify = yaml.safe_load(tests_to_modify[0])
    if not tests_to_modify:
        print(f"No test cases found to modify.")
        return {succeeded: False, test_error: "No test cases found to modify"}

    # Expect exactly one file
    if len(tests_to_modify) != 1:
        print(f"Expected exactly one file, got {len(tests_to_modify)}")
        return {succeeded: False, test_error: "Expected exactly one file"}

    test_to_modify = tests_to_modify[0]
    test_to_modify = os.path.relpath(test_to_modify, os.getcwd())
    with open(test_to_modify, "r") as f:
        test_content = f.read()

    navie = Editor(os.path.join(work_dir, "maketest"))
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
    test_number = 1
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

    return {
        "test_file": test_file,
        "succeeded": succeeded,
        "test_error": test_error,
    }
