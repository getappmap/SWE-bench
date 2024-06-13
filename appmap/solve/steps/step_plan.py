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
    print(f"[plan] ({instance_id}) Generating a plan for {issue_file}")
    with open(issue_file, "r") as f:
        issue_content = f.read()

    print(f"[plan] ({instance_id}) Rewriting the issue as code search keywords")
    terms_question = os.path.join(work_dir, "search_terms.txt")
    terms_output = os.path.join(work_dir, "search_terms.json")
    terms_log = os.path.join(work_dir, "search_terms.log")
    with open(terms_question, "w") as rewrite_f:
        rewrite_f.write(
            f"""@generate /nocontext


Generate a list of all file names, module names, class names, function names and varable names that are mentioned in the
described issue. Do not emit symbols that are part of the programming language itself. Do not emit symbols that are part
of test frameworks. Focus on library and application code only. Emit the results as a JSON list. Do not emit text, markdown, 
or explanations.

<issue>
{issue_content}
</issue>
"""
        )
    run_navie_command(
        log_dir,
        temperature=temperature,
        command=appmap_command,
        input_path=terms_question,
        output_path=terms_output,
        log_path=terms_log
    )

    with open(terms_output, "r") as f:
        issue_content_as_code = f.read()

    print(f"[plan] ({instance_id}) Searching for context using {issue_file}")
    context_prompt = os.path.join(work_dir, "search_context.txt")
    with open(context_prompt, "w") as apply_f:
        apply_f.write(
            f"""@context /nofence /format=json /noterms /exclude=(\\btesting\\b|\\btest\\b|\\btests\\b|\\btest_|_test\.py$|\.txt$|\.html$|\.rst$|\.md$)
                      
{issue_content_as_code}
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

    print(f"[plan] ({instance_id}) Generating a plan for {issue_file}")

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
        context_path=context_file,
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
