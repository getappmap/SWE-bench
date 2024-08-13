import os
import shutil

from navie.editor import Editor
from navie.format_instructions import xml_format_instructions


def step_generate(
    work_dir,
    instance_id,
    plan_file,
    solution_file,
    iteration,
):
    print(f"[generate] ({instance_id}) Generating code")

    with open(plan_file, "r") as f:
        plan = f.read()

    navie = Editor(
        os.path.join(work_dir, "generate", str(iteration + 1)), log_dir=work_dir
    )
    navie.generate(
        plan=plan,
        options="/noprojectinfo /include=.py /exclude=test",
        prompt=xml_format_instructions(),
    )

    output_file = os.path.join(navie.work_dir, "generate", "generate.md")
    shutil.copy(output_file, solution_file)

    print(f"[generate] ({instance_id}) Code generated in {solution_file}")
