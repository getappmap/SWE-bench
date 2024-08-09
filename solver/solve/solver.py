import argparse
import os
import sys


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(SCRIPT_DIR, ".."))
sys.path.append(os.path.join(SCRIPT_DIR, "..", ".."))
sys.path.append(os.path.join(SCRIPT_DIR, "..", "..", "submodules", "navie-editor"))

from navie.config import Config

from solve.steps.patch import filter_patch_exclude_tests, git_diff, list_files_in_patch
from solve.steps.read_test_directives import read_test_directives
from solve.steps.build_task_manager import build_task_manager
from solve.steps.step_maketest import step_maketest
from solve.steps.step_lint_repair import step_lint_repair
from solve.steps.step_apply import step_apply
from solve.steps.step_generate import step_generate
from solve.steps.step_list import step_list
from solve.steps.step_plan import step_plan
from solve.steps.step_verify import step_verify

DEFAULT_STEPS = {
    "peektest": False,
    "maketest": True,
    "plan": True,
    "generate": True,
    "apply": True,
    "verify": True,
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
        steps=None,
        temperature=0.0,
        changed_files_limit=1,  # TODO: Make this configurable. It's 1 for "Lite", otherwise greater than 1
        test_attempts=1,  # TODO: Make this configurable; ensure that maketest doesn't copy existing failed attempts
    ):
        self.instances_path = instances_path
        self.instance_id = instance_id
        self.issue_file = issue_file
        self.log_dir = log_dir
        self.conda_path = conda_path
        self.conda_env = conda_env
        self.format_command = format_command
        self.lint_command = lint_command
        self.steps = steps or DEFAULT_STEPS
        self.temperature = temperature
        self.changed_files_limit = changed_files_limit
        self.test_attempts = test_attempts

        if not os.path.isfile(self.issue_file):
            raise FileNotFoundError(f"File '{self.issue_file}' not found.")

        self.work_dir = os.path.dirname(os.path.abspath(self.issue_file))
        self.plan_file = os.path.join(self.work_dir, "plan.md")
        self.solution_file = os.path.join(self.work_dir, "solution.md")
        self.apply_file = os.path.join(self.work_dir, "apply.md")
        self.context_yaml_file = os.path.join(self.work_dir, "search_context.yml")

        self.task_manager = build_task_manager(
            self.instances_path,
            self.instance_id,
            self.work_dir,
            self.conda_env,
            self.log_dir,
            self.conda_path,
            timeout=30,
            verbose=True,
        )

        self.files = []
        self.files_changed = []
        self.maketest_errors = []
        self.test_directives = []

    def solve(self):
        if self.steps["peektest"]:
            self.peektest()

        if self.steps["maketest"]:
            self.maketest()

        if self.steps["plan"]:
            self.plan()

        for i in range(2):
            if i > 0:
                print(
                    f"[solver] ({self.instance_id}) No files changed. Retrying apply + generate."
                )

            if self.steps["generate"]:
                self.generate_code(i)

            if self.steps["apply"]:
                self.apply_changes(i)

            if len(self.files_changed) > 0:
                break

        if self.lint_command:
            self.lint_repair()

        if self.steps["verify"]:
            self.verify()

    # Enumerate test cases that should be verified "still passing" with the valid solution.
    # Note that some test cases may be *expected* to fail with a valid solution, so this is no
    # more than a heuristic.
    def peektest(self):
        test_directives = read_test_directives(self.task_manager.instance)
        print(
            f"""[solver] ({self.instance_id}) Named test directives: {", ".join(test_directives)}"""
        )

        self.extend_test_directives(test_directives)

    # Generate a test case to verify the solution.
    def maketest(self):
        maketest_results = step_maketest(
            self.task_manager,
            self.issue_file,
            self.work_dir,
            self.lint_command,
            self.test_attempts,
        )

        results_with_error_summary = [
            result for result in maketest_results if "error_summary" in result
        ]
        self.maketest_errors = [
            result["error_summary"] for result in results_with_error_summary
        ]
        self.extend_test_directives(
            [result["test_directive"] for result in maketest_results]
        )

    def plan(self):
        step_plan(
            self.issue_file,
            self.work_dir,
            self.instance_id,
            self.changed_files_limit,
            self.plan_file,
            # maketest_errors=self.maketest_errors # TODO: Use these once the information is more reliable
        )

    def list_files(self):
        step_list(
            self.work_dir,
            self.instance_id,
            self.plan_file,
        )

    def generate_code(self, iteration):
        step_generate(
            self.work_dir,
            self.instance_id,
            self.plan_file,
            self.solution_file,
            iteration,
        )

    def apply_changes(self, iteration):
        step_apply(self.work_dir, self.instance_id, self.solution_file, iteration)
        self.load_file_changes("apply")

    def lint_repair(self):
        step_lint_repair(
            self.log_dir,
            self.work_dir,
            self.instance_id,
            self.conda_path,
            self.conda_env,
            self.lint_command,
            self.temperature,
        )
        self.load_file_changes("lint_repair")

    def verify(self):
        self.test_directives_succeeded = []

        if not self.files_changed or len(self.files_changed) == 0:
            print(
                f"[solver] ({self.instance_id}) No files changed. Skipping verify step."
            )
            return

        if len(self.test_directives) == 0:
            print(
                f"[solver] ({self.instance_id}) WARN: No test directives have been collected. Skipping verify step."
            )
            self.test_directives_succeeded = []
            return
        else:
            print(
                f"[solver] ({self.instance_id}) Verifying solution using test directives {self.test_directives}"
            )

            self.test_directives_succeeded = step_verify(
                self.task_manager,
                self.work_dir,
                self.instance_id,
                self.test_directives,
            )

        result_name = "verify" if self.verify_succeeded() else "verify_failed"

        self.load_file_changes(result_name)

    def verify_succeeded(self):
        return (
            len(self.test_directives) > 0
            and self.test_directives == self.test_directives_succeeded
        )

    def load_file_changes(self, result_name):
        print(f"[solver] ({self.instance_id}) Loading file changes")

        diff_content = filter_patch_exclude_tests(git_diff(self.log_dir))
        if diff_content:
            self.files_changed = list_files_in_patch(diff_content)

            diff_file = os.path.join(self.work_dir, f"{result_name}.patch")
            with open(diff_file, "w") as f:
                f.write(diff_content)

            print(f"[solver] ({self.instance_id}) Diff saved to file {diff_file}")
        else:
            self.files_changed = []
            print(f"[solver] ({self.instance_id}) Diff is empty.")

    def extend_test_directives(self, test_directives):
        self.test_directives = list(set(self.test_directives + test_directives))


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
        "--directory", type=str, help="Working directory of the project to modify"
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
    parser.add_argument("--format-command", type=str, help="Format command to use")
    parser.add_argument("--lint-command", type=str, help="Lint command to use")
    parser.add_argument("--appmap-command", type=str, help="AppMap command to use")

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
    else:
        steps = DEFAULT_STEPS

    steps_enabled = ", ".join([step for step, enabled in steps.items() if enabled])
    print(f"[solver] Steps: {steps_enabled}")
    if args.log_dir:
        os.makedirs(args.log_dir, exist_ok=True)

    iteration = os.path.basename(os.path.dirname(args.issue_file))
    conda_env = os.path.basename(os.getcwd())
    instance_name = os.path.basename(os.path.dirname(os.path.dirname(args.issue_file)))
    issue_name = os.path.join(instance_name, iteration)

    if args.appmap_command is not None:
        Config.set_appmap_command(args.appmap_command)

    solver = Solver(
        instances_path=args.instances_path,
        instance_id=args.instance_id,
        conda_path=args.path_conda,
        conda_env=conda_env,
        issue_file=args.issue_file,
        log_dir=args.log_dir,
        format_command=args.format_command,
        lint_command=args.lint_command,
        steps=steps,
        temperature=args.temperature,
    )
    solver.solve()
    files_changed = solver.files_changed

    if len(files_changed) == 0:
        print(f"[solver] WARN: No files changed for {issue_name}.")
        sys.exit(1)

    if len(files_changed) > 0:
        print(f"[solver] Changed {len(files_changed)} files for {issue_name}:")
        for file in files_changed:
            print(f"  {file}")
