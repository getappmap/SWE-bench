# Test file is any ".py" file whose basename starts with "test_" or ends with "_test.py"
# or is contained with a directory named "test", "tests" or "testcases"
import os


def is_test_file(file):
    return file.endswith(".py") and (
        any(
            token in file.split(os.path.sep) for token in ["tests", "test", "testcases"]
        )
        or os.path.basename(file).startswith("test_")
        or file.endswith("_test.py")
    )
