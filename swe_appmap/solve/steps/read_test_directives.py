import re

from swe_appmap.solve.steps.test_files_to_modules import test_files_to_modules


DATA_FILE_EXTS = [
    ".json",
    ".csv",
    ".txt",
    ".md",
    ".yml",
    ".yaml",
    ".toml",
    ".pkl",
]

BINARY_FILE_EXTS = [
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".tiff",
    ".tif",
    ".ico",
    ".svg",
    ".webp",
    ".flif",
    ".heif",
    ".bpg",
    ".avif",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".mp3",
    ".mp4",
    ".mkv",
    ".avi",
    ".mov",
    ".flv",
    ".wmv",
    ".webm",
    ".m4a",
    ".m4v",
    ".flac",
    ".wav",
    ".ogg",
    ".opus",
    ".srt",
]

NON_TEST_EXTS = DATA_FILE_EXTS + BINARY_FILE_EXTS


# From: https://github.com/aorwall/SWE-bench-docker/blob/a4b1d0bffd23150efd34fbd631b6dc12c9edc9ab/swebench_docker/utils.py#L173
# MIT License
def read_test_directives(instance: dict) -> list:
    """
    Get test directives from the test_patch of a task instance

    Args:
        instance (dict): task instance
    Returns:
        directives (list): List of test directives
    """
    # Get test directives from test patch and remove non-test files
    diff_pat = r"diff --git a/.* b/(.*)"
    test_patch = instance["test_patch"]
    directives = re.findall(diff_pat, test_patch)
    directives = [d for d in directives if not any(d.endswith(ext) for ext in NON_TEST_EXTS)]

    if instance["repo"] == "django/django":
        directives = test_files_to_modules(directives)

    return directives
