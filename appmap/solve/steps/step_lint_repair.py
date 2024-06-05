from ..log import log_diff, log_lint
from ..run_command import run_command
from ..run_navie_command import run_navie_command
from ..format_instructions import format_instructions


import os
import re
import subprocess

def install_flake8_if_needed(lint_command):
    if "flake8" not in lint_command:
        print("WARN: flake8 is not in lint_command. Skipping flake8 installation.")
        return
    
    # Run system command flake8 --help to see if it's already present
    flake8_check = subprocess.run(
        ["flake8", "--help"],
        capture_output=True,
        text=True,
    )
    if flake8_check.returncode == 0:
        return
    
    print("flake8 is not installed. Installing...")

    flake8_install = subprocess.run(
        ["pip", "install", "flake8"],
        check=True,
    )
    if flake8_install.returncode != 0:
        print("WARN: Failed to install flake8")

def step_lint_repair(log_dir, args, work_dir, appmap_command, base_file_content):
    lint_command = args.lint_command
    lint_error_pattern = args.lint_error_pattern

    install_flake8_if_needed(lint_command)

    print("Linting source files")

    work_dir_base_name = os.path.basename(work_dir)

    for file in base_file_content.keys():
        print(f"Linting {file}")
        norm_file = file.replace("/", "_")

        lint_args = lint_command.split() + [file]

        lint_result = subprocess.run(
            lint_args,
            capture_output=True,
            text=True,
        )

        lint_output = lint_result.stdout + lint_result.stderr

        log_lint(log_dir, os.path.join(work_dir_base_name, file), lint_output)

        # If lint_error_pattern starts and ends with '/', treat it as a regular expression.
        # Otherwise, treat it as a string literal.
        #
        # Find all lint errors reported in the output. Then select just those errors that
        # are reported on lines that we have modified.
        lint_errors = []
        if lint_error_pattern:
            if lint_error_pattern.startswith("/") and lint_error_pattern.endswith("/"):
                lint_errors = re.findall(lint_error_pattern[1:-1], lint_output)
            else:
                lint_errors = lint_output.split("\n").filter(
                    lambda line: lint_error_pattern in line
                )
        else:
            lint_errors = lint_output.split("\n")

        temp_dir = os.path.join(work_dir, "diff", norm_file)
        os.makedirs(temp_dir, exist_ok=True)
        # Write the base file content
        with open(os.path.join(temp_dir, "base"), "w") as f:
            f.write(base_file_content[file])
        with open(file, "r") as f:
            with open(os.path.join(temp_dir, "updated"), "w") as f2:
                f2.write(f.read())
        # Run the diff command
        diff_command = f"diff -u {os.path.join(temp_dir, 'base')} {os.path.join(temp_dir, 'updated')}"
        file_diff = run_command(log_dir, diff_command, fail_on_error=False)

        log_diff(log_dir, os.path.join(work_dir_base_name, file), file_diff)

        # Lint errors are formatted like this:
        # bin/solve.py:257:80: E501 line too long (231 > 79 characters)
        # Collect the line numbers of the lint errors.
        lint_errors_by_line_number = {}
        for error in lint_errors:
            if error:
                line_number = error.split(":")[1]
                if line_number:
                    lint_errors_by_line_number[int(line_number)] = error
                else:
                    print(f"WARN: No line number in lint error {error}")

        # The file diff contains chunks like:
        # @@ -147,15 +147,21 @@
        # Find the '+' number, which indicates the start line. Also find the number after the
        # comma, which indicates the number of lines. Report these two numbers for each chunk.
        diff_ranges = [
            [int(ch) for ch in chunk.split(" ")[2].split(",")]
            for chunk in file_diff.split("\n")
            if chunk.startswith("@@")
        ]

        for diff_range in diff_ranges:
            print(
                f"The file has changes between lines {diff_range[0]} and {diff_range[0] + diff_range[1]}"
            )

        lint_error_line_numbers_within_diff_sections = [
            line_number
            for line_number in lint_errors_by_line_number.keys()
            for diff_range in diff_ranges
            if diff_range[0] <= line_number <= diff_range[0] + diff_range[1]
        ]

        if lint_error_line_numbers_within_diff_sections:
            lint_errors = [
                lint_errors_by_line_number[line_number]
                for line_number in lint_error_line_numbers_within_diff_sections
            ]

            lint_error_message = "\n".join(
                [
                    "Lint errors within diff sections:",
                    *lint_errors,
                ]
            )

            print(lint_error_message)
            log_diff(
                log_dir, os.path.join(work_dir_base_name, file), lint_error_message
            )
        else:
            print("There are no lint errors within diff sections")
            log_diff(
                log_dir,
                os.path.join(work_dir_base_name, file),
                "No lint errors within diff sections",
            )

        for line_number in lint_error_line_numbers_within_diff_sections:
            lint_error = lint_errors_by_line_number[line_number]
            print(f"Error reported on line {line_number}: {lint_error}")

            # Extract the chunk of code that contains the error
            content_chunk_lines = []
            with open(file, "r") as f:
                lines = f.readlines()

                range_min = max(0, line_number - 7)
                range_max = min(len(lines), line_number + 7)
                for line_number in range(range_min, range_max):
                    content_chunk_lines.append(
                        f"{line_number + 1}: {lines[line_number]}"
                    )

            repair_dir = os.path.join(work_dir, "repair", norm_file, str(line_number))
            os.makedirs(repair_dir, exist_ok=True)

            repair_prompt, repair_output, repair_log = [
                os.path.join(repair_dir, f"generate.{ext}")
                for ext in ["txt", "md", "log"]
            ]
            repair_apply_prompt, repair_apply_output, repair_apply_log = [
                os.path.join(repair_dir, f"apply.{ext}") for ext in ["txt", "md", "log"]
            ]

            with open(repair_prompt, "w") as f:
                f.write(
                    f"""@generate /nocontext /noformat

Fix the linter errors indicated by the <lint-error> tag.

## Output format

{format_instructions()}

In the <original> and <modified> tags, do not emit line numbers. The line numbers are
only present in the file/content to help you identify which line has the lint error.

## Error report

<lint-error>
"""
                )
                f.write(lint_error)
                f.write(
                    """
</lint-error>
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

                # Plan the repair
            print(f"Generating code to repair {file}")
            run_navie_command(
                log_dir,
                command=appmap_command,
                input_path=repair_prompt,
                output_path=repair_output,
                log_path=repair_log,
            )

            print(f"Code generated to repair source file in {repair_output}")

            with open(repair_apply_prompt, "w") as f:
                f.write("@apply /all\n\n")
                with open(repair_output, "r") as plan_fp:
                    f.write(plan_fp.read())

            print("Applying changes to source files")
            run_navie_command(
                log_dir,
                command=appmap_command,
                input_path=repair_apply_prompt,
                output_path=repair_apply_output,
                log_path=repair_apply_log,
            )

            print("Changes applied")
