import json

from ..is_test_file import is_test_file
from ..run_navie_command import run_navie_command


import os


def step_list(log_dir, work_dir, instance_id, appmap_command, plan_file):
    print(f"[list] ({instance_id}) Detecting files to be modified")

    output_path = os.path.join(work_dir, "files.json")
    log_path = os.path.join(work_dir, "list-files.log")
    run_navie_command(
        log_dir,
        command=appmap_command,
        context_path=plan_file,
        output_path=output_path,
        log_path=log_path,
        additional_args="@list-files /format=json /nofence",
    )

    print(f"[list] ({instance_id}) Files detected. Filtering out test files.")
    with open(output_path) as f:
        files = json.load(f)
        files = [f for f in files if not is_test_file(f)]
        files_str = ", ".join(files)

    with open(output_path, "w") as f:
        f.write(json.dumps(files))

    print(f"[list] ({instance_id}) Files to be modified: {files_str}")
