import re
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional


class FileUpdate:
    def __init__(self, search: str, modified: str, file: Optional[str] = None):
        self.original = search
        self.modified = modified
        self.file = file

    def __repr__(self):
        return f"FileUpdate(original={self.original}, modified={self.modified}, file={self.file})"


def extract_changes(content: str) -> List[FileUpdate]:
    # Search for <change> tags
    change_regex = re.compile(r"<change>([\s\S]*?)<\/change>", re.IGNORECASE)
    changes: List[FileUpdate] = []

    # Trim at most one leading and trailing blank lines
    def trim_change(change: str) -> str:
        return change.lstrip("\n").rstrip("\n")

    for match in change_regex.finditer(content):
        change = match.group(1)

        try:
            # Parse XML
            root = ET.fromstring(change)
            # Ensure the correct structure
            original = root.find("original")
            modified = root.find("modified")
            if original is not None and modified is not None:
                update = FileUpdate(
                    search=trim_change(original.text or ""),
                    modified=trim_change(modified.text or ""),
                )
                changes.append(update)
        except ET.ParseError:
            continue

    return changes
