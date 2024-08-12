import os
import pytest
from unittest.mock import patch

from navie.editor import Editor

from solver.solve.steps.choose_test_file import choose_test_file


@pytest.fixture
def setup_test_environment(tmp_path):
    # Create a temporary directory for the test
    work_dir = tmp_path / "work"
    work_dir.mkdir()

    # Create a mock issue content
    issue_content = "This is a test issue content."

    # Create a mock test file
    test_file_path = work_dir / "choose" / "test_file.py"
    test_file_path.parent.mkdir(parents=True, exist_ok=True)
    test_file_path.write_text("def test_example(): pass")

    test_file_path2 = work_dir / "choose" / "test_file_2.py"
    test_file_path2.write_text("def test_example_2(): pass")

    return str(work_dir), issue_content, str(test_file_path), str(test_file_path2)


@patch.object(Editor, "search")
def test_choose_test_file_single(mock_search, setup_test_environment):
    work_dir, issue_content, test_file_path, _ = setup_test_environment

    mock_search.return_value = f"<!-- file: {test_file_path} -->"

    result = choose_test_file("test_instance", work_dir, issue_content)

    assert result == os.path.relpath(test_file_path)


@patch.object(Editor, "search")
def test_choose_test_file_multiple(mock_search, setup_test_environment):
    work_dir, issue_content, test_file_path, test_file_path2 = setup_test_environment

    mock_search.return_value = f"""<!-- file: {test_file_path} -->
<!-- file: {test_file_path2} -->
"""

    result = choose_test_file("test_instance", work_dir, issue_content)

    assert result == os.path.relpath(test_file_path)


@patch.object(Editor, "search")
def test_choose_test_file_none(mock_search, setup_test_environment):

    work_dir, issue_content, _, _ = setup_test_environment

    mock_search.return_value = ""

    result = choose_test_file("test_instance", work_dir, issue_content)

    assert result == {"error": "No test files found"}


@patch.object(Editor, "search")
def test_choose_test_files_plain_text_list(mock_search, setup_test_environment):
    work_dir, issue_content, test_file_path, test_file_path2 = setup_test_environment

    mock_search.return_value = f"{test_file_path}\n{test_file_path2}"

    result = choose_test_file("test_instance", work_dir, issue_content)

    assert result == os.path.relpath(test_file_path)


if __name__ == "__main__":
    pytest.main()
