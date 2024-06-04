from run_navie_command import run_navie_command


import os


def step_list(log_dir, work_dir, appmap_command, plan_file):
    print("Detecting files to be modified")
    run_navie_command(
        log_dir,
        command=appmap_command,
        context_path=plan_file,
        output_path=os.path.join(work_dir, "files.json"),
        log_path=os.path.join(work_dir, "list-files.log"),
        additional_args="@list-files /format=json /nofence",
    )

    print(f"Files to be modified stored in {os.path.join(work_dir, 'files.json')}")
