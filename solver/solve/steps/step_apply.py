from navie.editor import Editor
from navie.extract_changes import extract_changes

import os


def step_apply(
    work_dir,
    instance_id,
    solution_file,
):
    with open(solution_file, "r") as f:
        solution_content = f.read()

    changes = extract_changes(solution_content)
    for change in changes:
        print(f"[apply] ({instance_id}) Applying change to file: {change.file}")
        work_dir = os.path.join(work_dir, "apply")
        Editor(work_dir).apply(
            change.file,
            change.modified,
            search=change.original,
        )

    print(f"[apply] ({instance_id}) Changes applied")
