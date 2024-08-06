import shutil

from navie.editor import Editor
from navie.format_instructions import xml_format_instructions

from .erase_test_changes import erase_test_changes_from_file

import os


def step_generate(
    work_dir,
    instance_id,
    plan_file,
    solution_file,
):
    print(f"[generate] ({instance_id}) Generating code")

    with open(plan_file, "r") as f:
        plan = f.read()

    content = f"""@generate /exclude=test

{plan}
"""

    navie = Editor(os.path.join(work_dir, "generate"))
    navie.generate(
        plan=plan,
        options="/noprojectinfo /include=.py /exclude=test",
        prompt=xml_format_instructions(),
    )

    output_file = os.path.join(navie.work_dir, "generate", "generate.md")

    erase_test_changes_from_file(instance_id, output_file)

    print(f"[generate] ({instance_id}) Code generated in {solution_file}")

    shutil.copy(output_file, solution_file)
