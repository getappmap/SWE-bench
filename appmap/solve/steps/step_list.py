import json

from appmap.navie.editor import Editor

from ..is_test_file import is_test_file
from ..run_navie_command import run_navie_command


import os


def step_list(work_dir, instance_id, plan_file):
    print(f"[list] ({instance_id}) Detecting files to be modified")

    with open(plan_file, "r") as f:
        plan = f.read()

    navie = Editor(os.path.join(work_dir, "list"))
    files = navie.list_files(plan)

    # Transform to local paths
    files = [os.path.relpath(f, os.getcwd()) for f in files]
    # Filter out test files
    files = [f for f in files if not is_test_file(f)]

    output_path = os.path.join(work_dir, "files.json")
    with open(output_path, "w") as f:
        f.write(json.dumps(files))

    files_str = ", ".join(files)
    print(f"[list] ({instance_id}) Files to be modified: {files_str}")
