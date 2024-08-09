import os

from navie.editor import Editor
from navie.extract_changes import extract_changes
from navie.format_instructions import xml_format_instructions

from ..log import log_diff
from ..run_navie_command import run_navie_command

from .patch import (
    filter_patch_exclude_tests,
    filter_patch_match_file,
    git_diff,
    list_files_in_patch,
)
from .lint_repair import lint_in_conda
from .is_test_file import is_test_file


class LintRepairContext:
    def __init__(
        self,
        log_dir,
        work_dir,
        instance_id,
        conda_path,
        conda_env,
        lint_command,
    ):
        self.log_dir = log_dir
        self.work_dir = work_dir
        self.instance_id = instance_id
        self.conda_path = conda_path
        self.conda_env = conda_env
        self.lint_command = lint_command
        self.work_dir_base_name = os.path.basename(work_dir)


def norm_file_name(file):
    return file.replace("/", "_")


def diff_file(log_dir, file):
    return filter_patch_match_file(git_diff(log_dir), file)


def lint_error_line_numbers_within_diff_sections(lint_errors_by_line_number, file_diff):
    # The file diff contains chunks like:
    # @@ -147,15 +147,21 @@
    # Find the '+' number, which indicates the start line. Also find the number after the
    # comma, which indicates the number of lines. Report these two numbers for each chunk.
    diff_ranges = [
        [int(ch) for ch in chunk.split(" ")[2].split(",")]
        for chunk in file_diff.split("\n")
        if chunk.startswith("@@")
    ]

    return [
        line_number
        for line_number in lint_errors_by_line_number.keys()
        for diff_range in diff_ranges
        if diff_range[0] <= line_number <= diff_range[0] + diff_range[1]
    ]


class LintRepairResponse:
    def __init__(self, patch):
        self.patch = patch


def step_lint_repair(
    log_dir,
    work_dir,
    instance_id,
    conda_path,
    conda_env,
    lint_command,
    temperature,
):
    context = LintRepairContext(
        log_dir,
        work_dir,
        instance_id,
        conda_path,
        conda_env,
        lint_command,
    )

    file_names = list_files_in_patch(git_diff(log_dir))
    for file in file_names:
        if not file.endswith(".py"):
            print(
                f"[lint-repair] ({instance_id}) Skipping {file} because it is not a Python file"
            )
            continue

        if is_test_file(file):
            print(f"[lint-repair] ({instance_id}) Skipping test file {file}")
            continue

        with open(file, "r") as f:
            base_file_content = f.read()

        print(f"[lint-repair] ({instance_id}) Linting {file}")

        lint_errors_by_line_number = lint_in_conda(
            context.conda_path, context.conda_env, context.lint_command, file
        )
        if not len(lint_errors_by_line_number):
            print(f"[lint-repair] ({instance_id}) No lint errors found in {file}")
            continue

        lint_errors = "\n".join(lint_errors_by_line_number.values())
        print(
            f"[lint-repair] ({instance_id}) Lint errors found in {file}: {lint_errors}"
        )

        file_diff = diff_file(context.log_dir, file)

        line_numbers = lint_error_line_numbers_within_diff_sections(
            lint_errors_by_line_number, file_diff
        )

        if line_numbers:
            lint_errors = [
                lint_errors_by_line_number[line_number] for line_number in line_numbers
            ]

            lint_error_message = "\n".join(
                [
                    "Lint errors within diff sections:",
                    *lint_errors,
                ]
            )
            print(f"[lint-repair] ({instance_id}) Diff:")
            print(file_diff)
            print(f"[lint-repair] ({instance_id}) Lint errors within diff sections:")
            print(lint_errors)

            log_diff(
                log_dir,
                os.path.join(context.work_dir_base_name, file),
                lint_error_message,
            )
        else:
            print(
                f"[lint-repair] ({instance_id}) There are no lint errors within diff sections"
            )
            log_diff(
                log_dir,
                os.path.join(context.work_dir_base_name, file),
                "No lint errors within diff sections",
            )
            continue

        lint_min_line_number = min(line_numbers)
        lint_max_line_number = max(line_numbers)

        # Extract the chunk of code that contains the error
        content_chunk_lines = []
        with open(file, "r") as f:
            lines = f.readlines()

            range_min = max(0, lint_min_line_number - 7)
            range_max = min(len(lines), lint_max_line_number + 7)
            for line_number in range(range_min, range_max):
                content_chunk_lines.append(f"{line_number + 1}: {lines[line_number]}")

        repair_dir = os.path.join(
            work_dir, "lint_repair", norm_file_name(file), str(line_number)
        )
        os.makedirs(repair_dir, exist_ok=True)

        repair_question, repair_prompt, repair_output, repair_log = [
            os.path.join(repair_dir, f"generate.{ext}")
            for ext in ["txt", "prompt.md", "md", "log"]
        ]

        with open(repair_question, "w") as f:
            f.write(
                """@generate /noformat /noterms /nolistfiles /noprojectinfo /exclude=test
                    
<lint-errors>
"""
            )
            f.write("\n".join(lint_errors))
            f.write(
                """
</lint-errors>
<diff>"""
            )
            f.write(file_diff)
            f.write(
                """
</diff>
<file>
<path>"""
            )
            f.write(file)
            f.write(
                """
</path>
<content>
"""
            )
            f.write("".join(content_chunk_lines))
            f.write(
                """
</content>
</file>
"""
            )

        with open(repair_prompt, "w") as f:
            f.write(
                f"""## Objective

Fix the linter errors indicated by the <lint-errors> tag.

The <diff> section contains the current diff between the work-in-progress file and the
current committed version. You can use this to understand the context of the lint errors,
and possibly to restore or repair code that was improperly removed or changed.

The <file> section contains the current content of the file. It contains line numbers
to help you identify the lines that have the lint errors. Do not emit the line numbers
in your solution.

## Instructions

Fix the lint errors by:

* Modifying the line. Example: Fixing syntax.
* Adding other lines that make the line valid. Example: Adding required imports.
* Adjusting leading whitespace. Example: Fixing indentation in Python. 

Don't fix the lint errors by removing the line that has the error. The line that
has the error is important, but it needs to be fixed.

If the lint error is related to an undefined symbol, do your best to import 
the symbol from the correct module.

## Output format

{xml_format_instructions()}

In the <original> and <modified> tags, do not emit line numbers. The line numbers are
only present in the file/content to help you identify which line has the lint error.
"""
            )

        # Plan the repair
        print(f"[lint-repair] ({instance_id}) Generating code to repair {file}")
        run_navie_command(
            log_dir,
            temperature=temperature,
            input_path=repair_question,
            output_path=repair_output,
            prompt_path=repair_prompt,
            log_path=repair_log,
        )

        print(
            f"[lint-repair] ({instance_id}) Code generated to repair source file in {repair_output}"
        )

        print(f"[lint-repair] ({instance_id}) Applying changes to source files")
        with open(repair_output, "r") as f:
            repair_output_content = f.read()

        changes = extract_changes(repair_output_content)
        repair_item = 1
        for change in changes:
            if is_test_file(change.file):
                print(
                    f"[lint-repair] ({instance_id}) Skipping change to test file: {change.file}"
                )
                continue

            print(
                f"[lint-repair] ({instance_id}) Applying change to file: {change.file}"
            )

            work_dir = os.path.join(repair_dir, f"repair_{repair_item}")
            Editor(work_dir).apply(
                change.file,
                change.modified,
                search=change.original,
            )
            repair_item += 1

        post_fix_lint_errors_by_line_number = lint_in_conda(
            context.conda_path, context.conda_env, context.lint_command, file
        )
        post_file_diff = diff_file(context.log_dir, file)

        print(f"[lint-repair] ({instance_id}) Diff after repair:\n{post_file_diff}")

        post_line_numbers = lint_error_line_numbers_within_diff_sections(
            post_fix_lint_errors_by_line_number, post_file_diff
        )

        if post_line_numbers:
            post_lint_errors = [
                post_fix_lint_errors_by_line_number[line_number]
                for line_number in post_line_numbers
            ]

            post_lint_error_message = "\n".join(
                [
                    "Lint errors within diff sections after repair:",
                    *post_lint_errors,
                ]
            )

            print(post_lint_error_message)
            log_diff(
                log_dir,
                os.path.join(context.work_dir_base_name, file),
                post_lint_error_message,
            )
            print(f"Reverting {file} changes whose lint errors cannot be fixed:")
            print("\n".join(post_fix_lint_errors_by_line_number.values()))
            # Replace the file with the original file contents
            with open(file, "w") as f:
                f.write(base_file_content)

        else:
            print("There are no lint errors within diff sections after repair")
            log_diff(
                log_dir,
                os.path.join(context.work_dir_base_name, file),
                "No lint errors within diff sections after repair",
            )

    patch = filter_patch_exclude_tests(git_diff(log_dir))
    return LintRepairResponse(patch)
