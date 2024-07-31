import argparse
import json
import os
import sys


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(SCRIPT_DIR, "..", ".."))

from appmap.solve.patch import clean_patch
from appmap.solve.run_command import run_command
from appmap.solve.is_test_file import is_test_file

from appmap.solve.steps.read_test_directives import read_test_directives
from appmap.solve.steps.step_posttest import step_posttest
from appmap.solve.steps.step_pretest import build_task_manager, step_pretest
from appmap.solve.steps.step_lint_repair import step_lint_repair
from appmap.solve.steps.step_apply import step_apply
from appmap.solve.steps.step_generate import step_generate
from appmap.solve.steps.step_list import step_list
from appmap.solve.steps.step_plan import step_plan

# pretest detects test cases by analysis. peektest looks at the test instance data.
# Add pretest or peektest ... posttest to include those in the run.
DEFAULT_STEPS = {
    "pretest": False,
    "peektest": False,
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
        temperature=0.0,
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
        self.temperature = temperature

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
        self.context_yaml_file = os.path.join(self.work_dir, "search_context.yml")
        self.files = []
        self.files_changed = []
        self.test_succeeded_files = None
        self.posttest_succeeded = True

    def solve(self):
        if self.steps["pretest"]:
            self.pretest()

        if self.steps["peektest"]:
            self.peektest()

        if self.steps["plan"]:
            self.plan()

        if self.steps["list"]:
            self.list_files()

        files_list_file = os.path.join(self.work_dir, "files.json")
        if not os.path.isfile(files_list_file):
            raise FileNotFoundError(
                f"File '{files_list_file}' does not exist. You need to run the 'list' step."
            )

        with open(files_list_file, "r") as f:
            self.files = json.load(f)

        for file in self.files:
            if not os.path.isfile(file):
                print(
                    f"[solver] ({self.instance_id}) WARN: File '{file}' from files.json does not exist."
                )
                self.files.remove(file)

        if len(self.files) == 0:
            print(
                f"[solver] ({self.instance_id}) No files to change. Exiting without a solution."
            )
            return

        self.base_file_content = self.load_file_content()

        # Retry generate + apply in order to get a patch
        for i in range(2):
            if self.steps["generate"]:
                self.generate_code()

            if self.steps["apply"]:
                self.apply_changes()

            if len(self.files_changed) > 0:
                break

            print(
                f"[solver] ({self.instance_id}) No files changed. Retrying apply + generate."
            )

        if self.lint_command:
            self.lint_repair()

        if self.steps["posttest"]:
            self.posttest()
        else:
            self.posttest_succeeded = True

    # Run pass-to-pass test cases to characterize the existing code.
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
        )

    # List the pass-to-pass test cases.
    def peektest(self):
        self.posttest_succeeded = False

        task_manager = build_task_manager(
            self.instances_path,
            self.instance_id,
            self.work_dir,
            self.conda_env,
            self.log_dir,
            self.conda_path,
            timeout=30,
            verbose=True,
        )
        with task_manager:
            self.test_succeeded_files = read_test_directives(task_manager.instance)

        test_succeeded_files_str = ", ".join(self.test_succeeded_files)
        print(
            f"[solver] ({self.instance_id}) Test succeeded files: {test_succeeded_files_str}"
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
            self.context_yaml_file,
            self.temperature,
        )

    def list_files(self):
        step_list(
            self.log_dir,
            self.work_dir,
            self.instance_id,
            self.appmap_command,
            self.plan_file,
            self.temperature,
        )

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
            self.context_yaml_file,
            self.temperature,
        )

    def apply_changes(self):
        step_apply(
            self.log_dir,
            self.work_dir,
            self.instance_id,
            self.appmap_command,
            self.solution_file,
            self.apply_file,
            self.temperature,
        )
        self.load_file_changes("apply")

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
            self.temperature,
        )
        self.load_file_changes("lint_repair")

    def posttest(self):
        assert self.test_succeeded_files is not None

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
        with open(self.plan_file, "r") as f:
            plan = f.read()

        self.posttest_succeeded = step_posttest(
            self.work_dir,
            self.instances_path,
            self.instance_id,
            self.conda_path,
            self.conda_env,
            self.appmap_command,
            plan,
            self.load_file_content(),
            self.test_succeeded_files,
        )

        result_name = "posttest" if self.posttest_succeeded else "posttest_failed"
        self.load_file_changes(result_name)

    def load_file_changes(self, result_name):
        print(f"[solver] ({self.instance_id}) Loading file changes")
        self.files_changed = []
        updated_file_content = self.load_file_content()
        for file in updated_file_content:
            if (
                file not in self.base_file_content
                or updated_file_content[file] != self.base_file_content[file]
            ):
                self.files_changed.append(file)

        print(f"[solver] ({self.instance_id}) Files changed: {self.files_changed}")

        diff_command = f"git diff"
        diff = run_command(self.log_dir, diff_command, fail_on_error=True)
        if diff:
            diff = clean_patch(diff)
            diff_file = os.path.join(self.work_dir, f"{result_name}.patch")
            with open(diff_file, "w") as f:
                f.write(diff)

            print(f"[solver] ({self.instance_id}) Diff saved to file {diff_file}")
        else:
            print(f"[solver] ({self.instance_id}) Diff is empty.")

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
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="(Optional) The temperature to use when running the model",
    )
    parser.add_argument(
        "--temperature_increase",
        type=float,
        default=0.1,
        help="(Optional) The amount to increase the temperature by on each iteration",
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
        temperature=args.temperature,
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
