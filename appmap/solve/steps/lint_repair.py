import subprocess


# Lint the file and return a dictionary of line numbers with lint errors.
def lint(lint_command: list) -> dict:
    lint_result = subprocess.run(
        lint_command, capture_output=True, shell=False, text=True
    )

    lint_output = lint_result.stdout
    lint_errors = lint_output.split("\n")

    # Lint errors are formatted like this:
    # bin/solve.py:257:80: E501 line too long (231 > 79 characters)
    # Collect the line numbers of the lint errors.
    lint_errors_by_line_number = {}
    for error in lint_errors:
        if error:
            tokens = error.split(":")
            if len(tokens) > 1:
                line_number = tokens[1]
                if line_number and line_number.isdigit():
                    lint_errors_by_line_number[int(line_number)] = error

    return lint_errors_by_line_number


def lint_in_conda(conda_path, conda_env, lint_command, file):
    return lint(
        [
            "bash",
            "-c",
            f". {conda_path}/bin/activate {conda_env} && {lint_command} {file}",
        ]
    )
