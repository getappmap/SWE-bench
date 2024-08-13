import os

from navie.editor import Editor
from navie.fences import extract_fenced_content


# Choose a test case file that is most related to the issue.
def choose_test_file(instance_id, work_dir, issue_content):
    test_to_modify_str = Editor(
        os.path.join(work_dir, "choose"), log_dir=work_dir
    ).search(
        f"""Identify a single test case that is most related to the following issue:

{issue_content}
""",
        format="""## Format instructions
        
Output the result as the file path, and nothing else.

Do not include line numbers or any location within the file. Just the file path.
""",
        options="/noprojectinfo /include=test",
        extension="txt",
    )

    tests_to_modify = []

    # Recognize all file paths like this: <!-- file: /home/runner/work/_temp/tmpcwaaevd8/sympy__sympy__1.11-3/sympy/printing/tests/test_pycode.py -->
    for line in test_to_modify_str.split("\n"):
        if line.startswith("<!-- file: "):
            tests_to_modify.append(line[len("<!-- file: ") : -len(" -->")])

    # Also recognized the fenced output, which should just be a list of files.
    tests_to_modify_lines = "\n".join(extract_fenced_content(test_to_modify_str))
    tests_to_modify.extend(tests_to_modify_lines.split("\n"))

    def resolve_test_path(test):
        if not os.path.exists(test):
            test_relative = test.lstrip("/")
            if os.path.exists(test_relative):
                return test_relative
        return test

    tests_to_modify = [resolve_test_path(test) for test in tests_to_modify]
    tests_to_modify = [test for test in tests_to_modify if os.path.exists(test)]

    if len(tests_to_modify) == 0:
        print(
            f"[maketest] ({instance_id}) Found no existing test files in {test_to_modify_str}"
        )
        return {"error": "No test files found"}

    if len(tests_to_modify) > 1:
        print(
            f"[maketest] ({instance_id}) Found multiple test files in {test_to_modify_str}"
        )

    test_file = tests_to_modify[0]
    return os.path.relpath(test_file, os.getcwd())
