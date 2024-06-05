import argparse
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(SCRIPT_DIR, "..", ".."))

from appmap.solve.steps.step_lint_repair import step_lint_repair
from appmap.solve.steps.step_apply import step_apply
from appmap.solve.steps.step_generate import step_generate
from appmap.solve.steps.step_list import step_list
from appmap.solve.steps.step_plan import step_plan

DEFAULT_STEPS = {"plan": True, "list": True, "generate": True, "apply": True}


class Solver:
    def __init__(
        self,
        issue_file,
        log_dir,
        format_command=None,
        lint_command=None,
        lint_error_pattern=None,
        appmap_command="appmap",
        steps=None,
    ):
        self.issue_file = issue_file
        self.log_dir = log_dir
        self.format_command = format_command
        self.lint_command = lint_command
        self.lint_error_pattern = lint_error_pattern
        self.appmap_command = appmap_command
        self.steps = steps or DEFAULT_STEPS

        if self.lint_command and not self.steps["apply"]:
            print("WARN: Lint command will not be executed without apply step.")

        if not os.path.isfile(self.issue_file):
            raise FileNotFoundError(f"File '{self.issue_file}' not found.")

        self.work_dir = os.path.dirname(os.path.abspath(self.issue_file))

        self.plan_file = os.path.join(self.work_dir, "plan.md")
        self.solution_file = os.path.join(self.work_dir, "solution.md")
        self.apply_file = os.path.join(self.work_dir, "apply.md")
        self.files = []

    def solve(self):
        if self.steps["plan"]:
            self.plan()

        if self.steps["list"]:
            self.list_files()

        if self.steps["generate"]:
            self.generate_code()

        self.base_file_content = {}
        self.files_changed = []
        if self.steps["apply"]:
            self.base_file_content = self.load_file_content()

            self.apply_changes()

            self.updated_file_content = self.load_file_content()
            for file in self.updated_file_content:
                if file not in self.base_file_content or self.updated_file_content[file] != self.base_file_content[file]:
                    self.files_changed.append(file)

        if self.lint_command:
            if len(self.files_changed) > 0:
                self.lint_repair()
            else:
                print(
                    "WARN: No changes were applied. Lint repair step will be skipped."
                )

    def plan(self):
        step_plan(
            self.log_dir,
            self,
            self.issue_file,
            self.work_dir,
            self.appmap_command,
            self.plan_file,
        )

    def list_files(self):
        step_list(self.log_dir, self.work_dir, self.appmap_command, self.plan_file)
        with open(os.path.join(self.work_dir, "files.json")) as f:
            self.files = json.load(f)

    def generate_code(self):
        step_generate(
            self.log_dir,
            self,
            self.work_dir,
            self.appmap_command,
            self.plan_file,
            self.solution_file,
            self.files,
        )

    def load_file_content(self):
        result = {}
        for file in self.files:
            if os.path.isfile(file):
                with open(file, "r") as f:
                    result[file] = f.read()
        return result

    def apply_changes(self):
        step_apply(
            self.log_dir,
            self.work_dir,
            self.appmap_command,
            self.solution_file,
            self.apply_file,
        )

    def lint_repair(self):
        step_lint_repair(
            self.log_dir,
            self,
            self.work_dir,
            self.appmap_command,
            self.base_file_content,
        )


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Solve software issue described in a file."
    )
    parser.add_argument(
        "issue_file", type=str, help="File containing the issue description"
    )

    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Number of times to try and create a code update for each test instance",
    )

    parser.add_argument(
        "--directory",
        type=str,
        help="Working directory of the project to modify",
        default=None,
    )
    parser.add_argument(
        "--log-dir", type=str, help="Directory to store logs", default="logs"
    )
    parser.add_argument(
        "--format-command", type=str, help="Format command to use", default=None
    )
    parser.add_argument(
        "--lint-command", type=str, help="Lint command to use", default=None
    )
    parser.add_argument(
        "--lint-error-pattern", type=str, help="Lint error pattern to use", default=None
    )
    parser.add_argument(
        "--appmap-command", type=str, help="AppMap command to use", default="appmap"
    )

    parser.add_argument("--noplan", action="store_true", help="Do not generate a plan")
    parser.add_argument(
        "--nolist", action="store_true", help="Do not list files to be modified"
    )
    parser.add_argument(
        "--nogenerate", action="store_true", help="Do not generate code"
    )
    parser.add_argument("--noapply", action="store_true", help="Do not apply changes")

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()
    steps = {
        "plan": not args.noplan,
        "list": not args.nolist,
        "generate": not args.nogenerate,
        "apply": not args.noapply,
    }

    if args.directory:
        os.chdir(args.directory)

    if args.log_dir:
        os.makedirs(args.log_dir, exist_ok=True)

    attempt_number = 0
    files_changed = []
    while len(files_changed) == 0:
        solver = Solver(
            issue_file=args.issue_file,
            log_dir=args.log_dir,
            format_command=args.format_command,
            lint_command=args.lint_command,
            lint_error_pattern=args.lint_error_pattern,
            appmap_command=args.appmap_command,
            steps=steps,
        )
        solver.solve()
        files_changed = solver.files_changed
        if len(files_changed) == 0:
            print("No files were changed.")
            attempt_number += 1
            if attempt_number == args.retries:
                print("Giving up after {attempt_number} attempts")
            else:
                print(
                    f"Retrying (attempt number {attempt_number + 1} of {args.retries})"
                )
