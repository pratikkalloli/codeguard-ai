"""End-to-end orchestration tests use real analysis with only Docker isolated."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codeguard.auth import AuthorizationError, bootstrap_developer, register_user
from codeguard.events import list_events
from codeguard.execution import ExecutionResult, FunctionTestResult
from codeguard.pipeline import run_evaluation
from codeguard.storage import get_evaluation, get_reliability_report


class Phase20PipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.database = Path(self.temp.name) / "pipeline.db"
        self.user = register_user("pipeline-user", "a pipeline password", self.database)

    def tearDown(self) -> None:
        self.temp.cleanup()

    @patch("codeguard.pipeline.predict_pass_rate", return_value={"status": "predicted", "prediction": 0.8, "model": "phase17", "prediction_range": [0, 1], "confidence": None})
    @patch("codeguard.pipeline.run_function_tests")
    @patch("codeguard.pipeline.run_python")
    def test_pipeline_runs_existing_analysis_and_persists_report(self, run_mock, tests_mock, prediction_mock) -> None:
        run_mock.return_value = ExecutionResult(status="Passed", stdout="ok\n", exit_code=0, duration_seconds=0.03, code_execution_seconds=0.02, code_time_measurement_type="container child process")
        tests_mock.return_value = [FunctionTestResult(test_name="basic", status="passed", expected_output="6", actual_output="6")]
        stages = []
        result = run_evaluation(
            self.user["id"],
            "Sum a list",
            "Lists are mutable.\n```python\ndef solution(items):\n    return sum(items)\n```",
            evaluation_name="Sum demo",
            test_function="solution",
            test_cases=[{"inputs": [[1, 2, 3]], "expected": 6}],
            database_path=self.database,
            on_stage=lambda label, state: stages.append((label, state)),
        )
        evaluation = get_evaluation(result["evaluation_id"], self.database, owner_user_id=self.user["id"])
        report = get_reliability_report(result["evaluation_id"], self.database, owner_user_id=self.user["id"])
        self.assertEqual(evaluation["evaluation_name"], "Sum demo")
        self.assertEqual(result["executions"][0]["status"], "Passed")
        self.assertEqual(result["test_results"][0]["status"], "passed")
        self.assertEqual(result["claims"][0]["status"], "Supported")
        self.assertEqual(report["ml_reliability"]["prediction"], 0.8)
        self.assertIn(("Building report", "complete"), stages)
        self.assertEqual(run_mock.call_count, 1)
        self.assertEqual(tests_mock.call_count, 1)
        self.assertEqual(prediction_mock.call_count, 1)
        developer = bootstrap_developer("pipeline-dev", "another pipeline developer password", self.database)
        event_names = {row["event"] for row in list_events(developer["id"], database_path=self.database)}
        self.assertTrue({"EVALUATION_STARTED", "CODE_EXTRACTION_COMPLETED", "STATIC_ANALYSIS_COMPLETED", "DOCKER_EXECUTION_STARTED", "DOCKER_EXECUTION_COMPLETED", "FUNCTION_TESTS_COMPLETED", "PERFORMANCE_COMPLETED", "CLAIMS_EXTRACTED", "EVIDENCE_RETRIEVED", "CLAIMS_VERIFIED", "ML_INFERENCE_COMPLETED", "REPORT_CREATED"} <= event_names)

    def test_pipeline_preserves_explanation_when_no_code_is_present(self) -> None:
        result = run_evaluation(
            self.user["id"], "Explain lists", "Lists are mutable.", database_path=self.database
        )
        self.assertEqual(result["code_blocks"], [])
        self.assertIn("Lists are mutable", result["explanation"])
        self.assertIn("No Python code could be detected", result["report"]["extraction"]["no_code_message"])
        self.assertEqual(result["executions"], [])

    def test_pipeline_refuses_unauthenticated_actor(self) -> None:
        with self.assertRaises(AuthorizationError):
            run_evaluation(999, "Question", "Answer", database_path=self.database)


if __name__ == "__main__":
    unittest.main()
