from unidiff import PatchSet


def exclude_files(diff: str, paths: list[str]) -> str:
    """
    Modify a patch to exclude certain files.
    """
    result = PatchSet("")
    result.extend([p for p in PatchSet(diff) if p.path not in paths])
    return str(result)


# these files are modified by SWE-bench environment setup
# in sphinx, and the solver has no business touching them anyway
EXCLUDED = ["setup.py", "tox.ini"]


def clean_patch(diff: str) -> str:
    return exclude_files(diff, EXCLUDED)
