from ..run_navie_command import run_navie_command


import os


def step_apply(
    log_dir, work_dir, instance_id, appmap_command, solution_file, apply_file
):
    apply_prompt = os.path.join(work_dir, "apply.txt")
    with open(apply_prompt, "w") as apply_f:
        apply_f.write(
            """@apply /all
""")
        with open(solution_file, "r") as sol_f:
            apply_f.write(sol_f.read())

    print(f"[apply] ({instance_id}) Applying changes to source files")
    run_navie_command(
        log_dir,
        command=appmap_command,
        input_path=apply_prompt,
        output_path=apply_file,
        log_path=os.path.join(work_dir, "apply.log"),
    )

    print(f"[apply] ({instance_id}) Changes applied")
