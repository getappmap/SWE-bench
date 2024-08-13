import os
import unittest

from solver.solve.steps.step_apply import ApplyResponse
from solver.solve.steps.step_lint_repair import LintRepairResponse
from solver.solve.steps.step_maketest import PrepareTestResponse, MaketestResult
from solver.solve.steps.step_verify import VerifyResponse
from solver.solve.solver import (
    Solution,
)

issue_file = os.path.join(os.path.dirname(__file__), "issue.txt")
log_dir = os.path.join(os.path.dirname(__file__), "..", "..", "logs")


class TestSolution(unittest.TestCase):
    def test_solution_response_fail_to_pass(
        self,
    ):
        prepare_test_response = PrepareTestResponse(
            "prepare_test_patch",
            [MaketestResult(test_directive="directive1", is_issue_reproduced=True)],
            1,
        )
        apply_response = ApplyResponse(patch="apply_patch")
        lint_repair_response = LintRepairResponse(patch="lint_repair_patch")
        verify_response = VerifyResponse(
            succeeded=True,
            patch="verify_patch",
            test_directives_succeeded=["directive1"],
        )

        solution = Solution(
            prepare_test_response=prepare_test_response,
            apply=apply_response,
            lint_repair=lint_repair_response,
            verify=verify_response,
        )

        solution_response = solution.solution_response()
        self.assertEqual(solution_response.patch_name, "fail_to_pass")
        self.assertEqual(solution_response.patch, "verify_patch")
        self.assertEqual(solution_response.prepare_test_patch, "prepare_test_patch")
        self.assertEqual(solution_response.prepare_test_num_attempts, 1)
        self.assertEqual(solution_response.test_directives, ["directive1"])
        self.assertTrue(solution_response.is_issue_reproduced)
        self.assertEqual(solution_response.apply_patch, "apply_patch")
        self.assertEqual(solution_response.lint_repair_patch, "lint_repair_patch")
        self.assertTrue(solution_response.verify_succeeded)
        self.assertEqual(solution_response.verify_patch, "verify_patch")
        self.assertEqual(
            solution_response.verify_test_directives_succeeded, ["directive1"]
        )

    def test_solution_response_pass_to_pass(
        self,
    ):
        prepare_test_response = PrepareTestResponse(
            None,
            [MaketestResult(test_directive="directive1", is_issue_reproduced=False)],
            1,
        )
        apply_response = ApplyResponse(patch="apply_patch")
        lint_repair_response = LintRepairResponse(patch=None)
        verify_response = VerifyResponse(
            succeeded=True,
            patch=None,
            test_directives_succeeded=['the-test'],
        )

        solution = Solution(
            prepare_test_response,
            apply_response,
            lint_repair_response,
            verify_response,
        )
        solution_response = solution.solution_response()
        self.assertEqual(solution_response.patch_name, "pass_to_pass")
        self.assertEqual(solution_response.patch, "apply_patch")

    def test_solution_pass_to_fail(self):
        prepare_test_response = PrepareTestResponse(
            None,
            [MaketestResult(test_directive="directive1", is_issue_reproduced=False)],
            1,
        )
        apply_response = ApplyResponse(patch="apply_patch")
        lint_repair_response = LintRepairResponse(patch=None)
        verify_response = VerifyResponse(
            succeeded=False,
            patch=None,
            test_directives_succeeded=[],
        )

        solution = Solution(
            prepare_test_response,
            apply_response,
            lint_repair_response,
            verify_response,
        )
        solution_response = solution.solution_response()
        self.assertEqual(solution_response.patch_name, "pass_to_fail")
        self.assertEqual(solution_response.patch, "apply_patch")


if __name__ == "__main__":
    unittest.main()
