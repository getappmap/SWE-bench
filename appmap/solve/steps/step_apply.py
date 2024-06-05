from ..run_navie_command import run_navie_command


import os


def step_apply(log_dir, work_dir, appmap_command, solution_file, apply_file):
    apply_prompt = os.path.join(work_dir, "apply.txt")
    with open(apply_prompt, "w") as apply_f:
        apply_f.write("@apply /all\n\n")
        with open(solution_file, "r") as sol_f:
            apply_f.write(sol_f.read())

    print("Applying changes to source files")
    run_navie_command(
        log_dir,
        command=appmap_command,
        input_path=apply_prompt,
        output_path=apply_file,
        log_path=os.path.join(work_dir, "apply.log"),
    )

    print("Changes applied")
