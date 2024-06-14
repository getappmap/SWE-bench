# Erases all changes that are proposed in a code generation output file.
#
# The file contains XML-style changes in the form:
#
# <change>
#   <file (attrs)>file_name.py</file>
#   <original>
#     original_file_content
#   </original>
#   <modified>
#     modified_file_content
#   </modified>
# </change>
#
# For now:
# - Read the file
# - Find the <change> tags
# - Find the file tag within the change tags
# - Match the file tag content against the list of known test patterns.
# - If there is a match, erase the change.
import re

from ..is_test_file import is_test_file


def erase_test_changes(change_name, change_content):
    match_attribute = lambda m, group_number: (
        m.group(group_number) if m is not None and m.group(group_number) else None
    )

    changes = re.findall(r"<change>.*?</change>", change_content, flags=re.DOTALL)
    for change in changes:
        file_tag = match_attribute(
            re.search(r"<file.*?</file>", change, flags=re.DOTALL), 0
        )
        if not file_tag:
            print(f"[erase_test_changes] ({change_name}) Change has no file tag")
            continue
        file_name = match_attribute(re.search(r"<file.*?>(.*?)</file>", file_tag), 1)
        if not file_name:
            print(f"[erase_test_changes] ({change_name}) File tag has no content")
            continue

        print(f"[erase_test_changes] ({change_name}) Checking file {file_tag}")
        if is_test_file(file_name):
            print(
                f"[erase_test_changes] ({change_name}) Erasing change to test file {file_name}"
            )
            change_content = change_content.replace(change, "")

    return change_content


def erase_test_changes_from_file(change_name, change_file):
    with open(change_file, "r") as f:
        repair_content = f.read()

    repair_content = erase_test_changes(change_name, repair_content)

    with open(change_file, "w") as f:
        f.write(repair_content)
