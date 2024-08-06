import shutil
import yaml

from navie.editor import Editor


import os


def step_plan(
    issue_file,
    work_dir,
    instance_id,
    file_limit,
    plan_file,
    maketest_errors=None,
):
    print(f"[plan] ({instance_id}) Generating a plan for {issue_file}")
    with open(issue_file, "r") as f:
        issue_content = f.read()

    print(f"[plan] ({instance_id}) Searching for the root cause of the issue")
    navie = Editor(os.path.join(work_dir, "plan"), log_dir=work_dir)
    root_cause_search = [
        f"""/noprojectinfo /include=.py /exclude=test
Find the root cause of the issue described below. The root cause is the smallest change that will fix the issue.

The issue is described as follows:
                         
<issue>
{issue_content}
</issue>
    """
    ]
    if maketest_errors:
        maketest_errors_str = "\n\n".join(maketest_errors)
        root_cause_search.append(
            f"""Test cases to confirm the error have provided the following error messages.

<error-messages>
{maketest_errors_str}
</error-messages>
"""
        )
    root_cause_search.append(f"Identify no more than {file_limit} files to modify.")
    root_cause_search.append("Do not modify test case files.")
    root_causes = navie.search(
        "\n\n".join(root_cause_search),
        format="""## Format instructions

Output the result as the file path, and nothing else. Example:

project/src/user_model.py
""",
        options="/noprojectinfo /include=.py /exclude=test",
        extension="txt",
    )

    print(
        f"""[plan] ({instance_id}) Found the root cause in the following files: {root_causes}"""
    )

    print(f"[plan] ({instance_id}) Generating a plan to fix the issue")
    plan_search = f"""Generate a plan to fix the issue described below. The plan should be focused on modifying the root cause of the issue.

Fix the issue using the least number of changes possible.

<issue>
{issue_content}
</issue>

<root-cause>
{root_causes}
</root-cause>

Do not include code snippets in the output. Just describe what needs to be done.
"""
    navie.plan(plan_search, options="/noprojectinfo /include=.py /exclude=test")

    print(f"[plan] ({instance_id}) Copying the plan file to the main work directory")

    output_file = os.path.join(navie.work_dir, "plan", "plan.md")
    shutil.copy(output_file, plan_file)


#     print(f"[plan] ({instance_id}) Generating a plan to fix the issue")

#     code = navie.generate(
#         f"""/include=.py /exclude=test

# {plan}
#     """
#     )
#     print(code)


#     print(f"[plan] ({instance_id}) Rewriting the issue as code search keywords")
#     terms_question = os.path.join(work_dir, "search_terms.txt")
#     terms_output = os.path.join(work_dir, "search_terms.json")
#     terms_log = os.path.join(work_dir, "search_terms.log")
#     with open(terms_question, "w") as rewrite_f:
#         rewrite_f.write(
#             f"""@generate /nocontext


# Generate a list of all file names, module names, class names, function names and varable names that are mentioned in the
# described issue. Do not emit symbols that are part of the programming language itself. Do not emit symbols that are part
# of test frameworks. Focus on library and application code only. Emit the results as a JSON list. Do not emit text, markdown,
# or explanations.

# <issue>
# {issue_content}
# </issue>
# """
#         )
#     run_navie_command(
#         log_dir,
#         temperature=temperature,
#         command=appmap_command,
#         input_path=terms_question,
#         output_path=terms_output,
#         log_path=terms_log,
#     )

#     with open(terms_output, "r") as f:
#         issue_content_as_code = f.read()

#     print(f"[plan] ({instance_id}) Searching for context using {issue_file}")
#     context_prompt = os.path.join(work_dir, "search_context.txt")
#     with open(context_prompt, "w") as apply_f:
#         apply_f.write(
#             f"""@context /nofence /format=yaml /noterms /exclude=(\\btesting\\b|\\btest\\b|\\btests\\b|\\btest_|_test\.py$|\.txt$|\.html$|\.rst$|\.md$)

# {issue_content_as_code}
# """
#         )

#     run_navie_command(
#         log_dir,
#         temperature=temperature,
#         command=appmap_command,
#         input_path=context_prompt,
#         output_path=context_yaml_file,
#         log_path=os.path.join(work_dir, "search_context.log"),
#     )

#     print(f"[plan] ({instance_id}) Generating a plan for {issue_file}")

#     plan_question = os.path.join(work_dir, "plan.txt")
#     with open(plan_question, "w") as plan_f:
#         plan_f.write(
#             f"""@plan /nocontext\n

# {issue_content}
# """
#         )
#     plan_prompt = os.path.join(work_dir, "plan.prompt.md")
#     with open(plan_prompt, "w") as plan_f:
#         plan_f.write(
#             """
# Focus the plan on modifying exactly one file.

# Do not modify test case files. Test case files are those that include "test", "tests" in their paths,
# or match the patterns "*_test.py" or "test_*.py".

# DO choose the one most relevant file to modify.
# DO NOT modify any other files.
# DO NOT choose a test case file.
# """
#         )
#     context_xml_file = os.path.join(work_dir, "plan_context.xml")
#     with open(context_xml_file, "w") as context_f:
#         with open(context_yaml_file, "r") as f:
#             context = yaml.safe_load(f)
#         context_f.write(format_search_context(context))

#     run_navie_command(
#         log_dir,
#         command=appmap_command,
#         input_path=plan_question,
#         prompt_path=plan_prompt,
#         context_path=context_xml_file,
#         output_path=plan_file,
#         log_path=os.path.join(work_dir, "plan.log"),
#     )

#     print(f"[plan] ({instance_id}) Plan stored in {plan_file}")

#     # Load the plan file and strip code blocks that are delimited by ```
#     with open(plan_file, "r") as f:
#         plan_content = f.read()
#     original_plan_content = plan_content
#     plan_content = re.sub(r"```.*?```", "", plan_content, flags=re.DOTALL)
#     # Diff the original and stripped content
#     if original_plan_content != plan_content:
#         with open(plan_file, "w") as f:
#             f.write(plan_content)
