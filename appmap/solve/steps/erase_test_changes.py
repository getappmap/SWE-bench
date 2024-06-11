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


def erase_test_changes(instance_id, change_file):
    with open(change_file, "r") as f:
        repair_content = f.read()

    changes = re.findall(r"<change>.*?</change>", repair_content, flags=re.DOTALL)
    for change in changes:
        file_tag = re.search(r"<file.*?</file>", change, flags=re.DOTALL).group(0)
        file_name = re.search(r"<file.*?>(.*?)</file>", file_tag).group(1)
        print(f"[erase_test_changes] ({instance_id}) Checking file {file_tag}")
        if is_test_file(file_name):
            print(
                f"[erase_test_changes] ({instance_id}) Erasing change to test file {file_name}"
            )
            repair_content = repair_content.replace(change, "")

    with open(change_file, "w") as f:
        f.write(repair_content)
