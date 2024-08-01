from appmap.navie.editor import Editor
from appmap.navie.extract_changes import extract_changes
from ..run_navie_command import run_navie_command

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
        print(f"[apply] ({instance_id}) Applying change: {change}")
        file_slug = "".join([c if c.isalnum() else "_" for c in change.file]).strip("_")
        work_dir = os.path.join(work_dir, "apply", file_slug)

        Editor(work_dir).edit(
            change.file,
            change.modified,
            search=change.original,
        )

    print(f"[apply] ({instance_id}) Changes applied")
