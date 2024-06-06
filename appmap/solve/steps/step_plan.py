import textwrap
from ..run_navie_command import run_navie_command

import os
import re
import glob

source_regex = re.compile(r"([a-zA-Z]:\\)?[\\\/]?([\w_\-.]+([\\\/]))*?[\w_\-.]+\.py")


def step_plan(
    log_dir, args, issue_file, work_dir, instance_id, appmap_command, plan_file, repo
):
    print(f"[plan] ({instance_id}) Generating a plan for {args.issue_file}")

    plan_prompt = os.path.join(work_dir, "plan.txt")
    plan = """@plan

## Guidelines

* Try to solve the problem with a minimal set of code changes.
* Do not output code blocks or fenced code. Output only a text description of the suggested
    changes, along with the file names.
* Solve the problem as if you were a contributor to the project, responding to an end-user
    bug report.
* Do not consider changing any code snippets that appear to be downstream of the problem.
"""
    referenced_files = get_referenced_files(repo, issue_file)
    if len(referenced_files) > 0:
        print(
            f"[plan] ({instance_id}) Identified {len(referenced_files)} files referenced from the issue."
        )
        plan += """
## References

Below are the file(s) that are referenced in the issue and found within this repository. You can
use these files as a reference for your solution.

<references>
"""
        for path, content in referenced_files.items():
            print(f"[plan] ({instance_id}) Appending {path}")
            plan += f'<file path="{path}">\n'
            plan += f"{content}\n"
            plan += "</file>\n"
        plan += "</references>\n"

    with open(plan_prompt, "w") as plan_f:
        plan_f.write(plan)

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


def get_referenced_files(repo, issue_file):
    """
    Parses the given issue text and returns a dictionary of paths to the files referenced in the issue.

    Args:
      repo (str): The name of the repository.
      issue (str): The issue text to parse.

    Returns:
      dict: A dictionary of paths to file contents.
    """
    with open(issue_file, "r") as f:
        issue = f.read()
    repo = repo.split("/")[-1]
    unique_paths = {match.group(0) for match in source_regex.finditer(issue)}
    files = {}
    for path in unique_paths:
        print(f"[plan] {path}")
        if not repo in path:
            continue

        path_segments = re.split(r"[\\\/]", path)
        path_matches = glob.glob(f"**/*/{path_segments[-1]}", recursive=True)
        while len(path_segments) > 0:
            search_path = path_segments.pop()
            path_matches = [x for x in path_matches if search_path in x]
            if len(path_matches) == 0:
                break

            if len(path_matches) == 1:
                with open(path_matches[0], "r") as f:
                    files[path_matches[0]] = f.read()
                break

    return files
