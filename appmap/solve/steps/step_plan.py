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
    temperature,
):
    print(f"[plan] ({instance_id}) Searching for context using {args.issue_file}")
    with open(args.issue_file, "r") as f:
        issue_content = f.read()

    context_prompt = os.path.join(work_dir, "search_context.txt")
    with open(context_prompt, "w") as apply_f:
        apply_f.write(
            f"""@context /nofence /format=json /noterms
                      
{issue_content}
"""
        )

    run_navie_command(
        log_dir,
        temperature=temperature,
        command=appmap_command,
        input_path=context_prompt,
        output_path=context_file,
        log_path=os.path.join(work_dir, "search_context.log"),
    )

    print(f"[plan] ({instance_id}) Generating a plan for {args.issue_file}")

    plan_question = os.path.join(work_dir, "plan.txt")
    with open(plan_question, "w") as plan_f:
        plan_f.write(
            f"""@plan /nocontext\n

{issue_content}
"""
        )
    plan_prompt = os.path.join(work_dir, "plan.prompt.md")
    with open(plan_prompt, "w") as plan_f:
        plan_f.write(
            """
Focus the plan on modifying exactly one file.

Do not modify test case files. Test case files are those that include "test", "tests" in their paths,
or match the patterns "*_test.py" or "test_*.py".

DO choose the one most relevant file to modify.
DO NOT modify any other files.
DO NOT choose a test case file.
"""
        )

    run_navie_command(
        log_dir,
        command=appmap_command,
        input_path=plan_question,
        prompt_path=plan_prompt,
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
