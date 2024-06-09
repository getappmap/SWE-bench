import argparse
import json
import os
import sys


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(SCRIPT_DIR, "..", ".."))

from appmap.solve.steps.step_posttest import step_posttest
from appmap.solve.steps.step_pretest import step_pretest
from appmap.solve.steps.step_lint_repair import step_lint_repair
from appmap.solve.steps.step_apply import step_apply
from appmap.solve.steps.step_generate import step_generate
from appmap.solve.steps.step_list import step_list
from appmap.solve.steps.step_plan import step_plan

# Add pretest ... posttest to include those in the run.
DEFAULT_STEPS = {
    "pretest": False,
    "plan": True,
    "list": True,
    "generate": True,
    "apply": True,
    "posttest": False,
}


class Solver:
    def __init__(
        self,
        instances_path,
        instance_id,
        issue_file,
        log_dir,
        conda_path,
        conda_env,
        format_command=None,
        lint_command=None,
        appmap_command="appmap",
        steps=None,
    ):
        self.instances_path = instances_path
        self.instance_id = instance_id
        self.issue_file = issue_file
        self.log_dir = log_dir
        self.conda_path = conda_path
        self.conda_env = conda_env
        self.format_command = format_command
        self.lint_command = lint_command
        self.appmap_command = appmap_command
        self.steps = steps or DEFAULT_STEPS

        if self.lint_command and not self.steps["apply"]:
            print(
                f"[solver] ({self.instance_id}) WARN: Lint command will not be executed without apply step."
            )

        if not os.path.isfile(self.issue_file):
            raise FileNotFoundError(f"File '{self.issue_file}' not found.")

        self.work_dir = os.path.dirname(os.path.abspath(self.issue_file))
        self.plan_file = os.path.join(self.work_dir, "plan.md")
        self.solution_file = os.path.join(self.work_dir, "solution.md")
        self.apply_file = os.path.join(self.work_dir, "apply.md")
        self.files = []
        self.files_changed = []
        self.test_succeeded_files = None
        self.posttest_succeeded = True

    def solve(self):
        if self.steps["pretest"]:
            self.pretest()

        if self.steps["plan"]:
            self.plan()

        if self.steps["list"]:
            self.list_files()

        self.base_file_content = self.load_file_content()

        if self.steps["generate"]:
            self.generate_code()

        if self.steps["apply"]:
            self.apply_changes()

        if self.lint_command:
            self.lint_repair()

        if self.steps["posttest"]:
            self.posttest()

    def pretest(self):
        self.posttest_succeeded = False
        self.test_succeeded_files = step_pretest(
            self.log_dir,
            self.work_dir,
            self.instances_path,
            self.instance_id,
            self.conda_path,
            self.conda_env,
            self.appmap_command,
            self.issue_file,
        )

    def plan(self):
        step_plan(
            self.log_dir,
            self,
            self.issue_file,
            self.work_dir,
            self.instance_id,
            self.appmap_command,
            self.plan_file,
        )

    def list_files(self):
        step_list(
            self.log_dir,
            self.work_dir,
            self.instance_id,
            self.appmap_command,
            self.plan_file,
        )
        with open(os.path.join(self.work_dir, "files.json")) as f:
            self.files = json.load(f)

    def generate_code(self):
        step_generate(
            self.log_dir,
            self,
            self.work_dir,
            self.instance_id,
            self.appmap_command,
            self.plan_file,
            self.solution_file,
            self.files,
        )

    def apply_changes(self):
        base_file_content = self.load_file_content()

        step_apply(
            self.log_dir,
            self.work_dir,
            self.instance_id,
            self.appmap_command,
            self.solution_file,
            self.apply_file,
        )

        # Test file is any ".py" file whose basename starts with "test_" or ends with "_test.py"
        # or is contained with a directory named "test", "tests" or "testcases"
        is_test_file = lambda file: (
            file.endswith(".py")
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
                print(
                    f"[solver] ({self.instance_id}) Reverting changes to test file {file}"
                )
                if file in base_file_content:
                    with open(file, "w") as f:
                        f.write(base_file_content[file])
                else:
                    os.remove(file)

        self.load_file_changes()

    def lint_repair(self):
        step_lint_repair(
            self.log_dir,
            self.work_dir,
            self.instance_id,
            self.conda_path,
            self.conda_env,
            self.lint_command,
            self.appmap_command,
            self.base_file_content,
        )
        self.load_file_changes()

    def posttest(self):
        assert(self.test_succeeded_files is not None)
        
        if len(self.test_succeeded_files) == 0:
            print(
                f"[solver] ({self.instance_id}) WARN: No test succeeded files found. Skipping posttest step."
            )
            self.posttest_succeeded = True
            return

        if not self.files_changed or len(self.files_changed) == 0:
            print(
                f"[solver] ({self.instance_id}) No files changed. Skipping posttest step."
            )
            return

        # At this point, some files have changed, and some tests succeeded.
        # Re-run the tests to ensure that the changes did not break anything.

        self.posttest_succeeded = step_posttest(
            self.log_dir,
            self.work_dir,
            self.instances_path,
            self.instance_id,
            self.conda_path,
            self.conda_env,
            self.test_succeeded_files,
        )

    def load_file_changes(self):
        print(f"[solver] ({self.instance_id}) Loading file changes")
        self.files_changed = []
        updated_file_content = self.load_file_content()
        for file in updated_file_content:
            if (
                file not in self.base_file_content
                or updated_file_content[file] != self.base_file_content[file]
            ):
                self.files_changed.append(file)

    def load_file_content(self):
        result = {}
        for file in self.files:
            if os.path.isfile(file):
                with open(file, "r") as f:
                    result[file] = f.read()
        return result


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Solve software issue described in a file."
    )
    parser.add_argument(
        "issue_file", type=str, help="File containing the issue description"
    )

    parser.add_argument(
        "--instances-path",
        type=str,
        help="Path to candidate task instances file",
    )

    parser.add_argument(
        "--instance-id",
        type=str,
        help="Instance ID",
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

    parser.add_argument(
        "--steps",
        type=str,
        help="Comma-separated list of steps to execute",
        default=None,
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()

    if args.directory:
        os.chdir(args.directory)

    print(f"[solver] Solving issue {args.issue_file} in directory {os.getcwd()}")

    steps = None
    if args.steps:
        steps = {step: False for step in DEFAULT_STEPS}
        for step in args.steps.split(","):
            if step in steps:
                steps[step] = True

    if args.log_dir:
        os.makedirs(args.log_dir, exist_ok=True)

    iteration = os.path.basename(os.path.dirname(args.issue_file))
    conda_env = os.path.basename(os.getcwd())
    instance_name = os.path.basename(os.path.dirname(os.path.dirname(args.issue_file)))
    issue_name = os.path.join(instance_name, iteration)

    solver = Solver(
        instances_path=args.instances_path,
        instance_id=args.instance_id,
        conda_path=args.path_conda,
        conda_env=conda_env,
        issue_file=args.issue_file,
        log_dir=args.log_dir,
        format_command=args.format_command,
        lint_command=args.lint_command,
        appmap_command=args.appmap_command,
        steps=steps,
    )
    solver.solve()
    files_changed = solver.files_changed
    posttest_succeeded = solver.posttest_succeeded

    if len(files_changed) == 0:
        print(f"[solver] WARN: No files changed for {issue_name}.")
        sys.exit(1)

    if not posttest_succeeded:
        print(
            f"[solver] Changed {len(files_changed)} files for {issue_name}, but posttest failed."
        )
        sys.exit(1)

    if len(files_changed) > 0:
        print(f"[solver] Changed {len(files_changed)} files for {issue_name}:")
        for file in files_changed:
            print(f"  {file}")
