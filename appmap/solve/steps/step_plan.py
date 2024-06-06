import textwrap
from ..run_navie_command import run_navie_command


import os
import re
import glob

source_regex = re.compile(r"([a-zA-Z]:\\)?[\\\/]?([\w_\-.]+([\\\/]))*?[\w_\-.]+\.py")


def step_plan(log_dir, args, issue_file, work_dir, appmap_command, plan_file, repo):
    print(f"Generating a plan for {args.issue_file}")

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
        plan += """
## References

Below are the file(s) that are referenced in the issue and found within this repository. You can
use these files as a reference for your solution.

<references>
"""
        for path, content in referenced_files.items():
            plan += f"<file path=\"{path}\">\n"
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

    print(f"Plan stored in {plan_file}")

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
    files = {}
    for matches in source_regex.finditer(issue):
        path = matches.group(0)
        if not repo in path:
            continue

        # Take everything after the first instance of the repo name
        # e.g. "/home/user/.pyenv/versions/2.7.6/lib/python2.7/site-packages/requests-2.3.0-py2.7.egg/requests/models.py"
        # ->                                                                        "-2.3.0-py2.7.egg/requests/models.py"
        path = path.split(repo, 1)[1]

        # Remove any leading slashes and partial path segments
        # e.g. "-2.3.0-py2.7.egg/requests/models.py"
        # ->                    "requests/models.py"
        path = path.split("/", 1)[1]

        if path in files:
            continue

        # Verify the file exists, and we're only referencing one file
        # More than one match means the path is ambiguous and we should skip.
        path_matches = glob.glob(path)
        if len(path_matches) != 1:
            continue

        with open(path_matches[0], "r") as f:
            files[path_matches[0]] = f.read()

    return files

