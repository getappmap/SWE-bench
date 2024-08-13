import argparse
import json
import os
import sys


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(SCRIPT_DIR, ".."))
sys.path.append(os.path.join(SCRIPT_DIR, "..", ".."))
sys.path.append(os.path.join(SCRIPT_DIR, "..", "..", "submodules", "navie-editor"))

from navie.config import Config

from solve.steps.patch import (
    filter_patch_exclude_tests,
    git_diff,
    list_files_in_patch,
)
from solve.steps.read_test_directives import read_test_directives
from solve.steps.build_task_manager import build_task_manager
from solve.steps.step_maketest import MaketestResult, step_maketest, PrepareTestResponse
from solve.steps.step_lint_repair import step_lint_repair, LintRepairResponse
from solve.steps.step_apply import step_apply, ApplyResponse
from solve.steps.step_generate import step_generate
from solve.steps.step_plan import step_plan
from solve.steps.step_verify import step_verify, VerifyResponse

DEFAULT_STEPS = {
    "peektest": False,
    "maketest": True,
    "plan": True,
    "generate": True,
    "apply": True,
    "verify": True,
}

# Patch names in order of increasing quality.
PATCH_NAMES = [
    "apply",
    "lint_repair",
    "pass_to_fail",
    "pass_to_pass",
    "fail_to_pass",
]


class SolutionResponse:
    BEST_PATCH = PATCH_NAMES[-1]

    EXT_FIELDS = {
        "prepare_test_patch": bool,
        "prepare_test_num_attempts": int,
        "is_issue_reproduced": bool,
        "verify_succeeded": bool,
    }

    def __init__(
        self,
        patch_name,
        patch,
        prepare_test_patch,
        prepare_test_num_attempts,
        test_directives,
        is_issue_reproduced,
        apply_patch,
        lint_repair_patch,
        verify_succeeded,
        verify_patch,
        verify_test_directives_succeeded,
    ):
        if patch_name and not patch_name in PATCH_NAMES:
            raise ValueError(f"Invalid patch name: {patch_name}")
        self.patch_name = patch_name
        self.patch = patch
        self.prepare_test_patch = prepare_test_patch
        self.prepare_test_num_attempts = prepare_test_num_attempts
        self.test_directives = test_directives
        self.is_issue_reproduced = is_issue_reproduced
        self.apply_patch = apply_patch
        self.lint_repair_patch = lint_repair_patch
        self.verify_succeeded = verify_succeeded
        self.verify_patch = verify_patch
        self.verify_test_directives_succeeded = verify_test_directives_succeeded

    def to_dict(self):
        return {
            "patch_name": self.patch_name,
            "patch": self.patch,
            "prepare_test_patch": self.prepare_test_patch,
            "prepare_test_num_attempts": self.prepare_test_num_attempts,
            "test_directives": self.test_directives,
            "is_issue_reproduced": self.is_issue_reproduced,
            "apply_patch": self.apply_patch,
            "lint_repair_patch": self.lint_repair_patch,
            "verify_succeeded": self.verify_succeeded,
            "verify_patch": self.verify_patch,
            "verify_test_directives_succeeded": self.verify_test_directives_succeeded,
        }

    @staticmethod
    def from_dict(d):
        return SolutionResponse(
            d["patch_name"],
            d["patch"],
            d["prepare_test_patch"],
            d["prepare_test_num_attempts"],
            d["test_directives"],
            d["is_issue_reproduced"],
            d["apply_patch"],
            d["lint_repair_patch"],
            d["verify_succeeded"],
            d["verify_patch"],
            d["verify_test_directives_succeeded"],
        )

    def to_json(self):
        return json.dumps(self.to_dict())

    def from_json(json_str):
        return SolutionResponse.from_dict(json.loads(json_str))

    def __lt__(self, other):
        return (
            SolutionResponse.compare_patch_names(self.patch_name, other.patch_name) < 0
        )

    @staticmethod
    def patch_name_priority(patch_name):
        return PATCH_NAMES.index(patch_name)

    # Compare patch names
    @staticmethod
    def compare_patch_names(first, second):
        return SolutionResponse.patch_name_priority(
            first
        ) - SolutionResponse.patch_name_priority(second)


class Solution:
    def __init__(
        self,
        prepare_test_response: PrepareTestResponse,
        apply: ApplyResponse,
        lint_repair: LintRepairResponse,
        verify: VerifyResponse,
    ):
        self.prepare_test_response = prepare_test_response
        self.apply = apply
        self.lint_repair = lint_repair
        self.verify = verify

    def solution_response(self) -> SolutionResponse:
        prepare_test_patch = None
        prepare_test_num_attempts = 0
        test_directives = []
        is_issue_reproduced = False
        apply_patch = None
        lint_repair_patch = None
        verify_patch = None
        verify_succeeded = False
        verify_test_directives_succeeded = []
        patch_name = None
        patch = None

        patch_names = []
        if self.prepare_test_response:
            if self.prepare_test_response.patch:
                patch = self.prepare_test_response.patch
                prepare_test_patch = self.prepare_test_response.patch
            prepare_test_num_attempts = self.prepare_test_response.num_attempts
            is_issue_reproduced = self.prepare_test_response.is_issue_reproduced()
            test_directives = self.prepare_test_response.test_directives()

        if self.apply:
            if self.apply.patch:
                patch_names.append("apply")
                patch = self.apply.patch
                apply_patch = self.apply.patch

        if self.lint_repair:
            if self.lint_repair.patch:
                patch_names.append("lint_repair")
                patch = self.lint_repair.patch
                lint_repair_patch = self.lint_repair.patch

        if self.verify:
            if self.verify.patch:
                patch = self.verify.patch
                verify_patch = self.verify.patch
            verify_succeeded = self.verify.succeeded
            verify_test_directives_succeeded = self.verify.test_directives_succeeded

            if (
                self.prepare_test_response
                and self.prepare_test_response.is_issue_reproduced()
                and self.verify.test_directives_succeeded
            ):
                patch_names.append("fail_to_pass")
            elif self.verify.test_directives_succeeded:
                patch_names.append("pass_to_pass")
            else:
                patch_names.append("pass_to_fail")

        patch_name = patch_names[-1] if patch_names else None
        return SolutionResponse(
            patch_name,
            patch,
            prepare_test_patch,
            prepare_test_num_attempts,
            test_directives,
            is_issue_reproduced,
            apply_patch,
            lint_repair_patch,
            verify_succeeded,
            verify_patch,
            verify_test_directives_succeeded,
        )


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
        maketest_retries=1,
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
        self.maketest_retries = maketest_retries

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

        self.files_changed = []
        self.test_directives = []

        self.prepare_test_response = None
        self.apply_response = None
        self.lint_repair_response = None
        self.verify_response = None

    def solve(self) -> Solution:
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

        return Solution(
            self.prepare_test_response,
            self.apply_response,
            self.lint_repair_response,
            self.verify_response,
        )

    # Enumerate test cases that should be verified "still passing" with the valid solution.
    # Note that some test cases may be *expected* to fail with a valid solution, so this is no
    # more than a heuristic.
    def peektest(self):
        test_directives = read_test_directives(self.task_manager.instance)
        print(
            f"""[solver] ({self.instance_id}) Named test directives: {", ".join(test_directives)}"""
        )
        self.prepare_test_response = PrepareTestResponse(
            None,
            [
                MaketestResult(test_directive, False)
                for test_directive in test_directives
            ],
            False,
            1,
        )

        self.extend_test_directives(test_directives)

    # Generate a test case to verify the solution.
    def maketest(self):
        self.prepare_test_response = step_maketest(
            self.task_manager,
            self.issue_file,
            self.work_dir,
            self.lint_command,
            self.maketest_retries,
        )
        self.extend_test_directives(self.prepare_test_response.test_directives())

    def plan(self):
        step_plan(
            self.issue_file,
            self.work_dir,
            self.instance_id,
            self.changed_files_limit,
            self.plan_file,
            # maketest_errors=self.maketest_errors # TODO: Use these once the information is more reliable
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
        self.apply_response = step_apply(
            self.work_dir, self.instance_id, self.solution_file, iteration
        )
        self.load_file_changes("apply")

    def lint_repair(self):
        self.lint_repair_response = step_lint_repair(
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
        if not self.files_changed or len(self.files_changed) == 0:
            print(
                f"[solver] ({self.instance_id}) No files changed. Skipping verify step."
            )
            return

        if len(self.test_directives) == 0:
            print(
                f"[solver] ({self.instance_id}) WARN: No test directives have been collected. Skipping verify step."
            )
            return
        else:
            print(
                f"[solver] ({self.instance_id}) Verifying solution using test directives {self.test_directives}"
            )

            self.verify_response = step_verify(
                self.task_manager,
                self.work_dir,
                self.instance_id,
                self.test_directives,
            )

        result_name = "verify" if self.verify_succeeded() else "verify_failed"

        self.load_file_changes(result_name)

    def verify_succeeded(self):
        return self.verify_response and self.verify_response.succeeded

    def load_file_changes(self, result_name):
        print(f"[solver] ({self.instance_id}) Loading file changes")

        patch = filter_patch_exclude_tests(git_diff(self.log_dir))
        if patch:
            self.files_changed = list_files_in_patch(patch)

            patch_file = os.path.join(self.work_dir, f"{result_name}.patch")
            with open(patch_file, "w") as f:
                f.write(patch)

            print(f"[solver] ({self.instance_id}) Patch saved to file {patch_file}")
        else:
            self.files_changed = []
            print(f"[solver] ({self.instance_id}) Patch is empty.")

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
        "--output-file",
        type=str,
        help="File to write the solution to",
        default="solution.json",
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
    parser.add_argument(
        "--maketest-retries",
        type=int,
        default=1,
        help="(Optional) Number of times to retry maketest",
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
        maketest_retries=args.maketest_retries,
    )
    solution = solver.solve()
    files_changed = solver.files_changed

    solution_response = solution.solution_response()
    with open(args.output_file, "w") as f:
        f.write(solution_response.to_json())

    if len(files_changed) == 0:
        print(f"[solver] WARN: No files changed for {issue_name}.")
        sys.exit(1)

    if len(files_changed) > 0:
        print(f"[solver] Changed {len(files_changed)} files for {issue_name}:")
        for file in files_changed:
            print(f"  {file}")
