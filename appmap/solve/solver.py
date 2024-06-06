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
        path_conda,
        format_command=None,
        lint_command=None,
        appmap_command="appmap",
        steps=None,
    ):
        self.issue_file = issue_file
        self.log_dir = log_dir
        self.path_conda = path_conda
        self.format_command = format_command
        self.lint_command = lint_command
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
                if (
                    file not in self.base_file_content
                    or self.updated_file_content[file] != self.base_file_content[file]
                ):
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
        base_file_content = self.load_file_content()

        step_apply(
            self.log_dir,
            self.work_dir,
            self.appmap_command,
            self.solution_file,
            self.apply_file,
        )

        # Test file is any ".py" file whose basename starts with "test_" or ends with "_test.py"
        is_test_file = lambda file: (
            file.endswith(".py")
            # file name path tokens contains 'tests' or 'test' directory
            and (
                any(
                    token in file.split(os.path.sep)
                    for token in ["tests", "test", "testcases"]
                )
                or os.path.basename(file).startswith("test_")
                or file.endswith("_test.py")
            )
        )

        # Revert changes to test cases
        for file in self.load_file_content():
            if is_test_file(file):
                print(f"Reverting changes to test file {file}")
                if file in base_file_content:
                    with open(file, "w") as f:
                        f.write(base_file_content[file])
                else:
                    os.remove(file)

    def lint_repair(self):
        step_lint_repair(
            self.log_dir,
            self.work_dir,
            self.path_conda,
            self.lint_command,
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
        "--directory",
        type=str,
        help="Working directory of the project to modify",
        default=None,
    )
    parser.add_argument(
        "--log-dir", type=str, help="Directory to store logs", default="logs"
    )
    parser.add_argument(
        "--path-conda",
        type=str,
        help="Path to the conda installation",
        default="conda",
    )
    parser.add_argument(
        "--format-command", type=str, help="Format command to use", default=None
    )
    parser.add_argument(
        "--lint-command", type=str, help="Lint command to use", default=None
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

    iteration = os.path.basename(os.path.dirname(args.issue_file))
    instance_name = os.path.basename(os.path.dirname(os.path.dirname(args.issue_file)))
    issue_name = os.path.join(instance_name, iteration)

    solver = Solver(
        path_conda=args.path_conda,
        issue_file=args.issue_file,
        log_dir=args.log_dir,
        format_command=args.format_command,
        lint_command=args.lint_command,
        appmap_command=args.appmap_command,
        steps=steps,
    )
    solver.solve()
    files_changed = solver.files_changed

    if len(files_changed) == 0:
        print(f"WARN: Solver did not change any files in {issue_name}.")
        sys.exit(1)

    if len(files_changed) > 0:
        print(f"Solver changed {len(files_changed)} files in {issue_name}:")
        for file in files_changed:
            print(f"  {file}")
