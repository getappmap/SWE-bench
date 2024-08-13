import os

from navie.editor import Editor
from navie.extract_changes import extract_changes


from .patch import git_diff, filter_patch_exclude_tests
from .is_test_file import is_test_file


class ApplyResponse:
    patch: str

    def __init__(self, patch):
        self.patch = patch


def step_apply(
    work_dir,
    instance_id,
    solution_file,
    iteration,
) -> ApplyResponse:
    with open(solution_file, "r") as f:
        solution_content = f.read()

    changes = extract_changes(solution_content)
    for i, change in enumerate(changes):
        if is_test_file(change.file):
            print(
                f"[apply] ({instance_id}) Skipping change {iteration}/{i+1} to test file: {change.file}"
            )
            continue

        print(
            f"[apply] ({instance_id}) Applying change {iteration}/{i+1} to file: {change.file}"
        )
        Editor(
            os.path.join(work_dir, "apply", str(iteration), str(i + 1)),
            log_dir=work_dir,
        ).apply(
            change.file,
            change.modified,
            search=change.original,
        )

    print(f"[apply] ({instance_id}) Changes applied")

    patch = filter_patch_exclude_tests(git_diff(work_dir))
    return ApplyResponse(patch=patch)
