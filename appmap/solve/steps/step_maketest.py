import os
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

    prompt = f"""## Output instructions
    
Create a test case that will only pass if the issue is fixed.

Be sure to emit all needed imports.

Generate a name for the test case that is consistent with related test case files.

Do not edit or modify any existing test case.
"""

    navie = Editor(work_dir)
    raw_code = navie.test(issue_content, prompt=prompt)
    files = navie.list_files(raw_code)
    files_str = ", ".join(files)
    print(f"[maketest] Test case generated: {files_str}")
    # Expect exactly one file
    if not files or len(files) != 1:
        print(f"Expected exactly one file, got {len(files)}")
        return {succeeded: False, test_error: "Expected exactly one file"}

    codes = extract_fenced_content(raw_code)
    if not codes or len(codes) != 1:
        print(f"Expected exactly one code block, got {len(codes)}")
        return {succeeded: False, test_error: "Expected exactly one code block"}

    raw_code = codes[0]

    # Write the file content.
    # Convert to a relative path for easier interpretation downstream.
    test_file = os.path.relpath(files[0], os.getcwd())
    print(f"[maketest] Writing test case to {test_file}")

    with open(test_file, "w") as f:
        f.write(raw_code)

    succeeded, test_error = run_test(tcm, test_file, appmap=True)
    appmap_count = count_appmaps()
    if appmap_count:
        instance_id = tcm.instance["instance_id"]
        index_appmaps(instance_id, log_dir, appmap_command)

    return {
        "test_file": test_file,
        "succeeded": succeeded,
        "test_error": test_error,
    }
