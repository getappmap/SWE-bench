import os
from typing import List, TypedDict, Optional, Union

from navie.editor import Editor
from navie.extract_changes import extract_changes
from navie.fences import extract_fenced_content
from navie.format_instructions import xml_format_instructions
from solver.solve.steps.choose_test_file import choose_test_file

from .patch import filter_patch_include_tests, git_diff
from .lint_repair import lint_in_conda
from .run_test import run_test
from .test_files_to_modules import test_files_to_modules
from .is_test_file import is_test_file


class MaketestError(TypedDict):
    error: str


class MaketestResult(TypedDict):
    test_directive: str
    is_issue_reproduced: bool
    error_summary: Optional[str]


class PrepareTestResponse:
    def __init__(
        self,
        patch: Optional[str],
        test_results: List[MaketestResult],
        num_attempts: int,
    ):
        self.patch = patch
        self.test_results = test_results
        self.num_attempts = num_attempts

    def is_issue_reproduced(self):
        is_issue_reproduced_values = [
            result["is_issue_reproduced"]
            for result in self.test_results
            if "is_issue_reproduced" in result
        ]
        return any(is_issue_reproduced_values)

    def errors(self):
        results_with_error_summary = [
            result for result in self.test_results if "error_summary" in result
        ]
        [result["error_summary"] for result in results_with_error_summary]

    def test_directives(self):
        return [result["test_directive"] for result in self.test_results]


def maketest(
    tcm,
    issue_file,
    work_dir,
    lint_command,
    test_number,
) -> Union[MaketestResult, MaketestError]:
    instance = tcm.instance
    instance_id = tcm.instance["instance_id"]

    print(
        f"[maketest] ({instance_id}) Generating a test case to verify the solution to {issue_file}"
    )

    with open(issue_file, "r") as f:
        issue_content = f.read()

    maketest_work_dir = os.path.join(work_dir, "maketest", str(test_number))

    test_file = choose_test_file(instance_id, maketest_work_dir, issue_content)

    print(f"[maketest] ({instance_id}) Modifying test case {test_file}")

    with open(test_file, "r") as f:
        test_content = f.read()
        original_test_content = test_content

    navie = Editor(os.path.join(maketest_work_dir, "generate"), log_dir=work_dir)

    test_prompt = f"""## Task

Add a new test to the following test file. 

The new test should verify the solution to the issue that's described by the user.

The test case MUST FAIL if the issue is NOT FIXED.

If any new imports are needed, be sure to include them.

<test>
{test_content}
</test>

## Output format

{xml_format_instructions()}
"""

    test_output = navie.test(
        issue_content,
        options="/noprojectinfo /nolistfiles /include=.py /exclude=test",
        prompt=test_prompt,
    )

    test_changes_content = "\n\n".join(extract_fenced_content(test_output))

    changes = extract_changes(test_changes_content)
    # Iterate through changes, with an index
    for i, change in enumerate(changes):
        if not is_test_file(change.file):
            print(
                f"[maketest] ({instance_id}) Skipping change {i+1} to non-test file: {change.file}"
            )
            continue

        if change.original:
            print(
                f"[maketest] ({instance_id}) Applying test change {i+1} to file: {test_file}"
            )
            Editor(
                os.path.join(maketest_work_dir, "apply", str(i + 1)), log_dir=work_dir
            ).apply(
                test_file,
                change.modified,
                search=change.original,
            )
        else:
            print(
                f"[maketest] ({instance_id}) Planned test change {i+1} has no <original> section, so it will be appended to: {test_file}"
            )
            with open(test_file, "a") as f:
                f.write("\n")
                f.write(change.modified)

    with open(test_file, "r") as f:
        test_content = f.read()

    print(f"[maketest] ({instance_id}) Generated test changes to {test_file}:")
    print(filter_patch_include_tests(git_diff(work_dir)))
    print(f"[maketest] ({instance_id}) Linting test file {test_file}")

    lint_errors_by_line_number = lint_in_conda(
        tcm.conda_path,
        tcm.venv,
        lint_command,
        test_file,
    )
    if lint_errors_by_line_number:
        lint_error_str = "\n".join(list(lint_errors_by_line_number.values()))
        print(
            f"[maketest] ({instance_id}) Lint errors found in test file {test_file}:\n{lint_error_str}"
        )

        lint_repair = Editor(
            os.path.join(maketest_work_dir, "lint_repair"), log_dir=work_dir
        )
        test_content_with_line_numbers = "\n".join(
            [f"{i+1:6}: {line}" for i, line in enumerate(test_content.split("\n"))]
        )

        lint_repair_content = lint_repair.generate(
            lint_error_str,
            prompt=f"""## Task

A developer is fixing a software issue:

<issue>
{issue_content}
</issue>

The code solution is:

<code>
{test_content_with_line_numbers}
</code>

There are lint errors in the code. Fix the lint errors.

## Output format

{xml_format_instructions()}
""",
            options="/noprojectinfo /exclude=test /nolistfiles",
        )
        lint_repair_changes = extract_changes(lint_repair_content)

        for i, change in enumerate(lint_repair_changes):
            if not is_test_file(change.file):
                print(
                    f"[maketest] ({instance_id}) Skipping lint repair change {i+1} to test file: {change.file}"
                )
                continue

            if change.original:
                print(
                    f"[maketest] ({instance_id}) Applying lint repair change {i+1} to file: {test_file}"
                )
                Editor(
                    os.path.join(maketest_work_dir, "apply", str(i + 1)),
                    log_dir=work_dir,
                ).apply(
                    test_file,
                    change.modified,
                    search=change.original,
                )
            else:
                print(
                    f"[maketest] ({instance_id}) Planned lint repair change {i+1} has no <original> section, so it will be appended to: {test_file}"
                )
                with open(test_file, "a") as f:
                    f.write("\n")
                    f.write(change.modified)

        lint_errors_by_line_number_after_repair = lint_in_conda(
            tcm.conda_path, tcm.venv, lint_command, test_file
        )
        if lint_errors_by_line_number_after_repair:
            lint_errors_after_repair_str = "\n".join(
                list(lint_errors_by_line_number_after_repair.values())
            )
            print(
                f"[maketest] ({instance_id}) Lint errors found in test file {test_file} after lint repair:\n{lint_errors_after_repair_str}"
            )
    else:
        print(
            f"[maketest] ({instance_id}) No lint errors found in test file {test_file}"
        )

    # TODO: Don't record appmap data of the test yet
    # succeeded, test_error = run_test(tcm, test_file, appmap=True)
    # appmap_count = count_appmaps()
    # if appmap_count:
    #     instance_id = tcm.instance["instance_id"]
    #     index_appmaps(instance_id, log_dir, appmap_command)

    succeeded, test_error = run_test(tcm, test_file, appmap=False)

    # Verify that the test_error indicates that the issue is being reproduced
    fails_for_expected_reason = False
    if succeeded:
        print(
            f"[maketest] ({instance_id}) Test case {test_file} succeeded. This is unexpected!"
        )
    else:
        print(
            f"[maketest] ({instance_id}) Test case {test_file} failed. This is expected. Let's see if it failed for the planned reason."
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

        whyfailed = Editor(
            os.path.join(maketest_work_dir, "check"), log_dir=work_dir
        ).ask(
            f"""/nocontext 

<error>
{test_error}
</error>

<issue>
{issue_content}
</issue>
""",
            context=[],
            prompt="""## Task

A test case has been created that is currently expected to fail due to a known issue.

Examine the error message below to determine if the test case is failing due to the reason described 
in the issue.

If the issue contains a specific error message, the test case should fail with that error message.
        
## Output format
            
Emit a single word that indicates whether the test error is consistent with the described issue.

- Emit "yes" if the test error is consistent with the described issue.
- Emit "maybe" if the test error is possibly consistent with the described issue.
- Emit "no" if the test error is NOT consistent with the described issue.
""",
        )

        if whyfailed == "no":
            print(
                f"[maketest] ({instance_id}) Test case {test_file} DID NOT fail for the planned reason"
            )
            print(
                f"[maketest] ({instance_id}) Reverting test changes to {test_file} and trying again"
            )
            with open(test_file, "w") as f:
                f.write(original_test_content)
        else:
            fails_for_expected_reason = True
            print(
                f"[maketest] ({instance_id}) It looks like it failed for the planned reason"
            )

    if instance["repo"] == "django/django":
        test_directive = test_files_to_modules([test_file])[0]
    else:
        test_directive = test_file

    result = MaketestResult(
        test_directive=test_directive,
        is_issue_reproduced=fails_for_expected_reason,
        error_summary=None,
    )
    if fails_for_expected_reason:
        error_summary = Editor(
            os.path.join(maketest_work_dir, "summarize"), log_dir=work_dir
        ).ask(
            f"""/nocontext A test case is failing.

Examine the message below. Extract the most relevant information about the error.

For example, include:

- Error message
- Stack trace
- Other exception details
- Other explanatory information

DO NOT include:

- Test setup and configuration
- Test teardown and cleanup

<error>
{test_error}
</error>
""",
            context=[],
        )
        result["error_summary"] = error_summary

    return result


def step_maketest(
    tcm,
    issue_file,
    work_dir,
    lint_command,
    num_attempts,
) -> PrepareTestResponse:
    # Try N times to generate a test that fails for the planned reason
    instance_id = tcm.instance["instance_id"]
    test_results = []
    for attempt_number in range(num_attempts):
        test_result = maketest(
            tcm, issue_file, work_dir, lint_command, attempt_number + 1
        )
        if "test_directive" in test_result:
            if test_result["is_issue_reproduced"]:
                print(
                    f"[maketest] ({instance_id}) Test case {test_result['test_directive']} verifies the issue"
                )
                test_results = [test_result]
                break
            else:
                test_results.append(test_result)
    file_diff = filter_patch_include_tests(git_diff(work_dir))
    if file_diff:
        print(f"[maketest] ({instance_id}) Generated test diff:")
        print(file_diff)
    else:
        print(f"[maketest] ({instance_id}) No test changes were accepted.")

    patch = filter_patch_include_tests(git_diff(work_dir))
    response = PrepareTestResponse(
        patch,
        test_results[0:1],
        attempt_number + 1,
    )

    if not response.is_issue_reproduced():
        print(
            f"[maketest] ({tcm.instance['instance_id']}) No test cases were generated that verify the issue. Returning the first test case for pass-to-pass purposes."
        )

    return response
