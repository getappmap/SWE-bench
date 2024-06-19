#!/usr/bin/env python

import argparse
import json
import os
import re
from typing import Optional

from swe_appmap.report.server import serve_reports


def load_jsonl(jsonl_path: str) -> list[dict]:
    with open(jsonl_path, "r") as f:
        return [json.loads(line) for line in f]


def format_code(code: str, language: Optional[str] = None) -> str:
    """
    Format code for markdown
    """
    code = code.replace("\n", "\n    ")
    code = f"```{language or ''}\n    {code.replace('```','``')}\n```"
    return code


def blockquote(text: str) -> str:
    """
    Wraps text (might be multiline) in a blockquote
    by prepending every line with >
    """
    return "\n".join(f"> {line}" for line in text.splitlines())


def format_field(input: dict, field: str) -> str:
    """
    Format a field for markdown
    """
    if "patch" in field:
        return format_code(input, "diff")
    if field in ["problem_statement", "hints_text", "plan.md"]:
        return blockquote(input)
    if "." in field:
        return format_code(input)
    return input


def make_details(title: str, content: str, open: bool = False) -> str:
    """
    Make a collapsible details section if more than one line
    """
    title = title.replace("_", " ").capitalize()
    if "\n" not in content and len(content) < 80:
        return f"{title}: {content}<br>\n"
    return (
        f"<details{' open' if open else ''}><summary>{title}</summary>\n\n{content}\n</details>\n\n"
    )


def read_files(dir: str) -> dict[str, str]:
    result = {}
    for name in os.listdir(dir):
        path = os.path.join(dir, name)
        if os.path.isfile(path):
            with open(path) as f:
                result[name] = f.read()

    return result


def make_solution_report(solve_log_dir: str) -> str:
    """
    Make a report for a solve attempt
    """
    report = ""

    files = read_files(solve_log_dir)

    ORDER = [
        "issue.txt",
        "plan.txt",
        "plan.log",
        "plan.md",
        "list-files.log",
        "files.json",
        "generate.txt",
        "context.txt",
        "solution.md",
        "generate.log",
        "apply.txt",
        "apply.md",
        "apply.log",
    ]

    for name in ORDER:
        if name in files:
            report += make_details(name, format_field(files.pop(name), name), open_by_default(name))

    for name, content in files.items():
        report += make_details(name, format_code(content))

    return report


def open_by_default(name):
    return name == "plan.md"


def extract_eval_title(eval_log: str) -> str:
    """
    Extract the title from the eval log
    by searching for the last line starting with >>>>>
    """
    for line in reversed(eval_log.splitlines()):
        if line.startswith(">>>>> "):
            return line[6:]
    return "Evaluation"


def create_report(
    instance: dict, solve_log_dir: Optional[str], eval_log_file: Optional[str]
) -> str:
    """
    Create a per-instance report
    """
    instance = instance.copy()
    instance_id = instance["instance_id"]

    excluded_fields = {
        field: instance.pop(field)
        for field in [
            "appmap_archive",
            "has_appmaps",
            "model_patch",
            "model_name_or_path",
            "patch",
        ]
        if field in instance
    }

    report = make_details(*format_problem(instance)[2:].split("\n", 1))

    appmap_archive_desc = excluded_fields.get("appmap_archive", "none")
    report += f"Appmaps: {appmap_archive_desc}\n\n"

    if solve_log_dir:
        dirs = [
            name
            for name in os.listdir(solve_log_dir)
            if os.path.isdir(os.path.join(solve_log_dir, name))
        ]
        for i, name in enumerate(dirs):
            path = os.path.join(solve_log_dir, name)
            report += make_details(
                f"Solve attempt {name}", make_solution_report(path), i == len(dirs) - 1
            )

    if excluded_fields.get("model_patch", None):
        report += make_details(
            "Generated patch", format_code(excluded_fields["model_patch"], "diff"), True
        )

    report += make_details("Gold patch", format_code(excluded_fields["patch"]))

    eval_title = None

    if eval_log_file:
        with open(eval_log_file) as f:
            eval_log = f.read()
        eval_title = extract_eval_title(eval_log)
        report += make_details(eval_title, format_code(eval_log))

    if eval_title:
        report = f"# {instance_id} — {eval_title.lower()}\n\n{report}"
    else:
        report = f"# {instance_id}\n\n{report}"

    return report, eval_title


def format_problem(instance: dict) -> str:
    instance = instance.copy()
    instance.pop("instance_id")
    problem = blockquote(instance.pop("problem_statement")) + "\n\n"

    # Add each field as a collapsible details section
    for field in [
        "repo",
        "version",
        "created_at",
        "base_commit",
        "environment_setup_commit",
        "test_cmd",
        "test_directives",
        "hints_text",
    ]:
        if field in instance:
            problem += make_details(field, format_field(instance.pop(field), field))

    # Format the rest
    for field in instance:
        problem += make_details(field, format_field(instance[field], field))

    return problem


def print_verbose(message):
    pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create per-instance reports")

    parser.add_argument("directory", nargs="?", help="working directory", type=str)

    parser.add_argument(
        "--predictions",
        help="Path to predictions file",
        default="predictions.jsonl",
        type=str,
    )
    parser.add_argument("--log_dir", type=str, help="Path to log directory", default="logs")
    parser.add_argument(
        "--output",
        help="Path to output directory",
        default="reports",
        type=str,
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="(Optional) Be verbose, specify multiple times for more output",
    )

    parser.add_argument(
        "--serve", type=int, nargs="?", help="Serve reports", const=54711, dest="port"
    )

    args = parser.parse_args()

    if args.directory:
        os.chdir(args.directory)

    if not os.path.exists(args.output):
        os.makedirs(args.output)

    if args.verbose:
        print_verbose = print

    results = []

    for prediction in load_jsonl(args.predictions):
        print_verbose(f"Creating report for {prediction['instance_id']}")
        solve_log_dir = os.path.join(args.log_dir, "solve", prediction["instance_id"])
        if not os.path.exists(solve_log_dir):
            print_verbose(f"No solve log found for {prediction['instance_id']}")
            solve_log_dir = None
        else:
            print_verbose(f"Solve log found for {prediction['instance_id']}")

        eval_log_file = os.path.join(
            args.log_dir, "navie", f"{prediction['instance_id']}.navie.eval.log"
        )
        if os.path.exists(eval_log_file):
            print_verbose(f"Eval log found for {prediction['instance_id']}")
        else:
            print_verbose(f"No eval log found for {prediction['instance_id']}")
            eval_log_file = None
        report, eval_result = create_report(prediction, solve_log_dir, eval_log_file)
        report_path = f"{args.output}/{prediction['instance_id']}.md"
        with open(report_path, "w") as f:
            f.write(report)
        results.append({"id": prediction["instance_id"], "result": eval_result})
        print_verbose(f"Report saved to {report_path}")

    print(f"{len(results)} reports saved in {os.path.abspath(args.output)}")

    if args.port:
        serve_reports(args.output, args.port, results)
