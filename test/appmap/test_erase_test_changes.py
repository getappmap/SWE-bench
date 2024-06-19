from pathlib import Path
import sys
import pytest
import os

# Add the parent directory to the Python path
thisdir = Path(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(thisdir.parent.parent.as_posix())

from swe_appmap.solve.steps.erase_test_changes import erase_test_changes


@pytest.fixture
def change_data_with_test():
    return """
    <change>
        <file>tests/test_file.py</file>
        <original>
            original_content_1
        </original>
        <modified>
            modified_content_1
        </modified>
    </change>
    <change>
        <file>src/main.py</file>
        <original>
            original_content_2
        </original>
        <modified>
            modified_content_2
        </modified>
    </change>
    """


@pytest.fixture
def change_data_without_test(tmpdir):
    return """
    <change>
        <file>src/main.py</file>
        <original>
            original_content_1
        </original>
        <modified>
            modified_content_1
        </modified>
    </change>
    <change>
        <file>src/utils.py</file>
        <original>
            original_content_2
        </original>
        <modified>
            modified_content_2
        </modified>
    </change>
    """


@pytest.fixture
def change_data_with_no_changes():
    return """
    <xchange>
        <xfile>src/main.py</xfile>
        <xoriginal>
            original_content_1
        </xoriginal>
        <xmodified>
            modified_content_1
        </xmodified>
    </xchange>
    """


@pytest.fixture
def change_data_with_no_file():
    return """
    <change>
        <xfile>src/main.py</xfile>
        <xoriginal>
            original_content_1
        </xoriginal>
        <xmodified>
            modified_content_1
        </xmodified>
    </change>
    """


def test_erase_test_changes_with_test(change_data_with_test):
    content = erase_test_changes("test_instance", change_data_with_test)

    assert "<file>tests/test_file.py<" not in content
    assert "<file>src/main.py<" in content


def test_erase_test_changes_without_test(change_data_without_test):
    content = erase_test_changes("test_instance", change_data_without_test)

    assert "<file>src/main.py<" in content
    assert "<file>src/utils.py<" in content


def test_erase_test_data_with_no_changes(change_data_with_no_changes):
    content = erase_test_changes("test_instance", change_data_with_no_changes)

    assert change_data_with_no_changes == content


def test_erase_test_data_with_no_file(change_data_with_no_file):
    content = erase_test_changes("test_instance", change_data_with_no_file)

    assert change_data_with_no_file == content
