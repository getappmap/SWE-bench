# Test file is any ".py" file whose basename starts with "test_" or ends with "_test.py"
# or is contained with a directory named "test", "tests" or "testcases"
import fnmatch
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

    for pattern in test_regular_expressions:
        if pattern.match(file):
            return True

    return False
