import textwrap
from ..run_navie_command import run_navie_command


import os
import re


def step_plan(
    log_dir,
    args,
    issue_file,
    work_dir,
    instance_id,
    appmap_command,
    plan_file,
    context_file,
):
    print(f"[plan] ({instance_id}) Searching for context using {args.issue_file}")
    context_prompt = os.path.join(work_dir, "search_context.txt")
    with open(context_prompt, "w") as apply_f:
        apply_f.write("@context /nofence /format=json\n")
    run_navie_command(
        log_dir,
        command=appmap_command,
        context_path=issue_file,
        input_path=context_prompt,
        output_path=context_file,
        log_path=os.path.join(work_dir, "search_context.log"),
    )

    print(f"[plan] ({instance_id}) Generating a plan for {args.issue_file}")

    plan_prompt = os.path.join(work_dir, "plan.txt")
    with open(plan_prompt, "w") as plan_f:
        plan_f.write(
            """@plan
"""
        )

    run_navie_command(
        log_dir,
        command=appmap_command,
        context_path=issue_file,
        input_path=plan_prompt,
        output_path=plan_file,
        log_path=os.path.join(work_dir, "plan.log"),
    )

    print(f"[plan] ({instance_id}) Plan stored in {plan_file}")

    # Load the plan file and strip code blocks that are delimited by ```
    with open(plan_file, "r") as f:
        plan_content = f.read()
    original_plan_content = plan_content
    plan_content = re.sub(r"```.*?```", "", plan_content, flags=re.DOTALL)
    # Diff the original and stripped content
    if original_plan_content != plan_content:
        with open(plan_file, "w") as f:
            f.write(plan_content)
