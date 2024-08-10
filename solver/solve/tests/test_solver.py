import os
import unittest
from unittest.mock import patch, MagicMock

from solver.solve.solver import Solver
from solver.solve.steps.step_apply import ApplyResponse
from solver.solve.steps.step_lint_repair import LintRepairResponse
from solver.solve.steps.step_maketest import PrepareTestResponse, MaketestResult
from solver.solve.steps.step_verify import VerifyResponse

issue_file = os.path.join(os.path.dirname(__file__), "issue.txt")
log_dir = os.path.join(os.path.dirname(__file__), "..", "..", "logs")


class TestSolver(unittest.TestCase):
    def setUp(self):
        self.instances_path = "path/to/instances"
        self.conda_path = "path/to/conda"
        self.instance_id = "the-instance-id"

        self.issue_file = issue_file
        self.log_dir = log_dir

        self.conda_env = "test_env"
        self.format_command = "format_command"
        self.lint_command = "lint_command"

        self.steps = {
            "peektest": False,
            "maketest": True,
            "plan": True,
            "generate": True,
            "apply": True,
            "verify": True,
        }

    @patch("solver.solve.solver.build_task_manager")
    @patch("solver.solve.solver.step_maketest")
    @patch("solver.solve.solver.step_lint_repair")
    @patch("solver.solve.solver.step_verify")
    @patch("solver.solve.solver.step_apply")
    @patch("solver.solve.solver.step_generate")
    @patch("solver.solve.solver.step_plan")
    def test_solve_flow(
        self,
        mock_step_plan,
        mock_step_generate,
        mock_step_apply,
        mock_step_verify,
        mock_step_lint_repair,
        mock_step_maketest,
        mock_build_task_manager,
    ):
        mock_step_maketest.return_value = PrepareTestResponse(
            "the-prepare-test-patch",
            [
                MaketestResult(
                    test_directive="the-test-directive", is_issue_reproduced=True
                )
            ],
            1,
        )
        mock_step_plan.return_value = None
        mock_step_generate.return_value = None
        mock_step_apply.return_value = ApplyResponse(patch="the-apply-patch")
        mock_step_verify.return_value = VerifyResponse(
            patch="the-verify-patch",
            test_directives_succeeded=["the-test-directive"],
        )
        mock_step_lint_repair.return_value = LintRepairResponse("the-lint-repair-patch")
        mock_build_task_manager.return_value = MagicMock(
            instance={
                "instance_id": self.instance_id,
            }
        )

        solver = Solver(
            self.instances_path,
            self.instance_id,
            self.issue_file,
            self.log_dir,
            self.conda_path,
            self.conda_env,
            self.format_command,
            self.lint_command,
            self.steps,
        )

        solution = solver.solve()

        # Verify that each step function was called
        mock_step_maketest.assert_called_once()
        mock_step_plan.assert_called_once()
        mock_step_generate.assert_called()
        mock_step_apply.assert_called()
        mock_step_verify.assert_called_once()
        mock_step_lint_repair.assert_called_once()
        mock_build_task_manager.assert_called_once()

        # Verify the solution object
        self.assertIsNotNone(solution)
        self.assertIsNotNone(solution.prepare_test_response)
        self.assertIsNotNone(solution.apply)
        self.assertIsNotNone(solution.lint_repair)
        self.assertIsNotNone(solution.verify)

        self.assertTrue(solution.prepare_test_response.is_issue_reproduced())
        self.assertEqual(solution.apply.patch, "the-apply-patch")
        self.assertEqual(solution.verify.patch, "the-verify-patch")
        self.assertEqual(
            solution.verify.test_directives_succeeded, ["the-test-directive"]
        )


if __name__ == "__main__":
    unittest.main()
