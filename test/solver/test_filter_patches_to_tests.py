import pytest

from solver.solve.steps.patch import filter_patch_exclude_tests, filter_patch_include_tests


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


if __name__ == "__main__":
    pytest.main()
