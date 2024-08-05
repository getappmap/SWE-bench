import pytest
from appmap.solve.steps.patch import filter_patches_to_tests


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


def test_filter_patches_to_tests_retain(sample_patch):
    result = filter_patches_to_tests(sample_patch, retain=True)
    expected = """
diff --git a/tests/test_file.py b/tests/test_file.py
new file mode 100644
index 0000000..abababa
diff --git a/src/test_file.py b/src/test_file.py
new file mode 100644
index 0000000..abababa
    """
    assert result.strip() == expected.strip()


def test_filter_patches_to_tests_filter_out(sample_patch):
    result = filter_patches_to_tests(sample_patch, retain=False)
    expected = """
diff --git a/src/main.py b/src/main.py
new file mode 100644
index 0000000..e69de29
    """
    assert result.strip() == expected.strip()


if __name__ == "__main__":
    pytest.main()
