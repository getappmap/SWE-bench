from navie.editor import Editor
from navie.extract_changes import extract_changes

import os


def step_apply(
    work_dir,
    instance_id,
    solution_file,
    iteration,
):
    with open(solution_file, "r") as f:
        solution_content = f.read()

    changes = extract_changes(solution_content)
    for i, change in enumerate(changes):
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
