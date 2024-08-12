from unidiff import PatchSet

from .is_test_file import is_non_test_file, is_test_file
from ..run_command import run_command

# these files are modified by SWE-bench environment setup
# in sphinx, and the solver has no business touching them anyway
EXCLUDED = ["setup.py", "tox.ini"]


# Run git diff in the log directory and return the output.
# clean: EXCLUDED files are removed from the output before it's returned.
def git_diff(log_dir, clean=True):
    diff_command = "git diff"
    patch = run_command(log_dir, diff_command, fail_on_error=True)
    if clean:
        patch = clean_patch(patch)
    return patch


def clean_patch(diff: str) -> str:
    return exclude_files(diff, EXCLUDED)


# List files that are changed in a patch.
def list_files_in_patch(patch):
    # Iterate through the lines in the patch.
    # When encountering a line that marks the beginning of a new diff hunk, extract the file name.
    # Return a list of file names.

    patch = clean_patch(patch)
    return [p.path for p in PatchSet(patch)]


# Process a patch and return only the changes that apply to files that
# pass the file_test_function.
def filter_patch(patch, file_test_function):
    # Iterate through the lines in the patch.
    # When encountering a line that marks the beginning of a new diff hunk, extract the file name.
    # If the file name passes the file_test_function, set the collect flag to true.
    # If the file name does not pass the file_test_function, set the collect flag to false.
    # If the collect flag is true, append the line to the result.

    patch = clean_patch(patch)
    return "\n".join([str(p) for p in PatchSet(patch) if file_test_function(p.path)])


def filter_patch_match_file(patch, file_name):
    return filter_patch(patch, lambda f: f == file_name)


def filter_patch_include_tests(patch):
    return filter_patch(patch, is_test_file)


def filter_patch_exclude_tests(patch):
    return filter_patch(patch, is_non_test_file)


def exclude_files(diff: str, paths: list[str]) -> str:
    """
    Modify a patch to exclude certain files.
    """
    result = PatchSet("")
    result.extend([p for p in PatchSet(diff) if p.path not in paths])
    return str(result)
