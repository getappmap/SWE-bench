# Test file is any ".py" file whose basename starts with "test_" or ends with "_test.py"
# or is contained with a directory named "test", "tests" or "testcases"
import fnmatch
from os import path
import re

test_glob_patterns = [
    "**/testing/**",
    "**/tests/**",
    "**/test/**",
    "**/test_*.py",
    "**/*_test.py",
]

# Compile test_glob_patterns into regular expressions
test_regular_expressions = [
    re.compile(fnmatch.translate(pattern)) for pattern in test_glob_patterns
]


def is_test_file(file):
    if not file.endswith(".py"):
        return False

    path_entries = file.split(path.sep)
    if "_pytest" in path_entries:
        return False

    if any(
        entry in ["test", "tests", "test", "testing", "testcases"]
        for entry in path_entries
    ):
        return True

    basename = path_entries[-1]
    if basename.startswith("test_") or basename.endswith("_test.py"):
        return True

    return False


def is_non_test_file(filename):
    return not is_test_file(filename)
