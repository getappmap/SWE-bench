from .is_test_file import is_non_test_file, is_test_file
from ..run_command import run_command


# Run git diff in the log directory and return the output.
def git_diff(log_dir):
    diff_command = "git diff"
    return run_command(log_dir, diff_command, fail_on_error=True)


# List files that are changed in a patch.
def list_files_in_patch(patch):
    # Iterate through the lines in the patch.
    # When encountering a line that marks the beginning of a new diff hunk, extract the file name.
    # Return a list of file names.

    lines = patch.splitlines()
    files = []
    for line in lines:
        if line.startswith("diff --git a/"):
            pieces = line.split()
            filename = pieces[-1]
            if filename.startswith("b/"):
                filename = filename[2:]
            files.append(filename)
    return files


# Process a patch and return only the changes that apply to files that
# pass the file_test_function.
def filter_patch(patch, file_test_function):
    # Iterate through the lines in the patch.
    # When encountering a line that marks the beginning of a new diff hunk, extract the file name.
    # If the file name passes the file_test_function, set the collect flag to true.
    # If the file name does not pass the file_test_function, set the collect flag to false.
    # If the collect flag is true, append the line to the result.

    lines = patch.splitlines(keepends=True)
    result = []
    collect = False
    for line in lines:
        if line.startswith("diff --git a/"):
            pieces = line.split()
            filename = pieces[-1]
            if filename.startswith("b/"):
                filename = filename[2:]
            collect = file_test_function(filename)
        if collect:
            result.append(line)
    return "".join(result)


def filter_patch_match_file(patch, file_name):
    return filter_patch(patch, lambda f: f == file_name)


def filter_patch_include_tests(patch):
    return filter_patch(patch, is_test_file)


def filter_patch_exclude_tests(patch):
    return filter_patch(patch, is_non_test_file)
