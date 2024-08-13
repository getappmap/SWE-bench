import pytest
from solver.solve.steps.patch import (
    filter_patch_exclude_tests,
    filter_patch_include_tests,
    clean_patch,
    exclude_files,
)


@pytest.fixture
def sample_patch():
    return """
diff --git a/tests/test_file.py b/tests/test_file.py
new file mode 100644
index 0000000..abababa
diff --git a/src/main.py b/src/main.py
new file mode 100644
index 0000000..e69de29
diff --git a/src/test_file.py b/src/test_file.py
new file mode 100644
index 0000000..abababa
    """


@pytest.fixture
def sample_diff():
    return """
diff --git a/setup.py b/setup.py
new file mode 100644
index 0000000..abababa
diff --git a/tox.ini b/tox.ini
new file mode 100644
index 0000000..e69de29
diff --git a/src/main.py b/src/main.py
new file mode 100644
index 0000000..abababa
    """


def test_filter_patch_include_tests(sample_patch):
    result = filter_patch_include_tests(sample_patch)
    expected = """
diff --git a/tests/test_file.py b/tests/test_file.py
new file mode 100644
index 0000000..abababa

diff --git a/src/test_file.py b/src/test_file.py
new file mode 100644
index 0000000..abababa
    """
    assert result.strip() == expected.strip()


def test_filter_patch_exclude_tests(sample_patch):
    result = filter_patch_exclude_tests(sample_patch)
    expected = """
diff --git a/src/main.py b/src/main.py
new file mode 100644
index 0000000..e69de29
    """
    assert result.strip() == expected.strip()


def test_clean_patch(sample_diff):
    result = clean_patch(sample_diff)
    expected = """
diff --git a/src/main.py b/src/main.py
new file mode 100644
index 0000000..abababa
    """
    assert result.strip() == expected.strip()


def test_exclude_files(sample_diff):
    paths_to_exclude = ["setup.py", "tox.ini"]
    result = exclude_files(sample_diff, paths_to_exclude)
    expected = """
diff --git a/src/main.py b/src/main.py
new file mode 100644
index 0000000..abababa
    """
    assert result.strip() == expected.strip()


if __name__ == "__main__":
    pytest.main()
