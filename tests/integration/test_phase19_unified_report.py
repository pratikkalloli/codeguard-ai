"""Regression tests for first-class Phase 17 signal in CodeGuard reports."""

import unittest
from unittest.mock import patch

from codeguard.ml.public_reliability import predict_pass_rate
from codeguard.reports import build_reliability_report


class UnifiedReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.evaluation = {
            "id": 5,
            "created_at": "2026-09-27T00:00:00+00:00",
            "question_text": "Sum values.",
            "model_name": "Manual",
            "explanation_text": "Lists are mutable.",
            "code_blocks": [{"block_index": 1, "code_text": "def solution(values): return sum(values)"}],
        }
        self.tests = [{"test_name": "test-1", "status": "passed", "expected_output": "3", "actual_output": "3"}]
        self.metrics = [{"metric_name": "python_process_wall_time", "metric_value": 0.04, "unit": "seconds"}]
        self.claims = [{
            "claim_text": "Lists are mutable.",
            "status": "Supported",
            "evidence_text": "Lists are mutable data structures.",
            "source_url": "https://docs.python.org/3/tutorial/datastructures.html",
            "title": "The Python Tutorial: Data Structures",
            "retrieval_score": 0.83,
        }]
        self.prediction = {
            "status": "predicted",
            "model": "linear_svr_c0_1",
            "model_version": "phase17-test-revision",
            "task": "pass_rate_prediction",
            "task_description": "Source-recorded execution pass-rate prediction.",
            "dataset_name": "NVIDIA OpenCodeReasoning-2 Python split",
            "dataset_size": {"downloaded_records": 60000, "usable_records": 53401},
            "prediction": 0.6262,
            "prediction_range": [0.0, 1.0],
            "confidence": None,
            "confidence_note": "No calibrated confidence interval is available.",
            "feature_summary": {"code_lines": 1.0},
            "model_metadata": {"seed": 1701, "parameters": {"C": 0.1}},
        }

    def build(self, *, ml=None, docker=None):
        return build_reliability_report(
            self.evaluation, self.tests, self.metrics, self.claims,
            ml_reliability=ml, docker_execution=docker,
        )

    def test_ml_prediction_appears_in_final_report(self) -> None:
        report = self.build(ml=self.prediction)
        self.assertEqual(report["ml_reliability"]["prediction"], 0.6262)
        self.assertEqual(report["signals"]["ml_reliability"], report["ml_reliability"])

    def test_model_and_dataset_metadata_appear(self) -> None:
        signal = self.build(ml=self.prediction)["ml_reliability"]
        self.assertEqual(signal["model"], "linear_svr_c0_1")
        self.assertEqual(signal["model_version"], "phase17-test-revision")
        self.assertEqual(signal["dataset_name"], "NVIDIA OpenCodeReasoning-2 Python split")
        self.assertEqual(signal["dataset_size"]["usable_records"], 53401)
        self.assertEqual(signal["model_metadata"]["parameters"]["C"], 0.1)

    def test_prediction_is_numeric_and_in_declared_range(self) -> None:
        signal = self.build(ml=self.prediction)["ml_reliability"]
        self.assertTrue(signal["available"])
        self.assertIsInstance(signal["prediction"], float)
        self.assertEqual(signal["prediction_range"], [0.0, 1.0])
        self.assertGreaterEqual(signal["prediction"], 0.0)
        self.assertLessEqual(signal["prediction"], 1.0)
        self.assertIsNone(signal["confidence"])

    def test_ml_failure_does_not_break_report(self) -> None:
        report = self.build(ml={"status": "not_available", "reason": "Model load failed."})
        self.assertFalse(report["ml_reliability"]["available"])
        self.assertEqual(report["ml_reliability"]["reason"], "Model load failed.")
        self.assertEqual(report["test_summary"]["passed"], 1)
        self.assertEqual(report["signals"]["static_ast_analysis"]["code_blocks"][0]["static_status"], "valid")

    def test_ast_result_is_unchanged_when_ml_is_added(self) -> None:
        without_ml = self.build()["code_blocks"]
        with_ml = self.build(ml=self.prediction)["code_blocks"]
        self.assertEqual(with_ml, without_ml)
        self.assertEqual(with_ml[0]["static_status"], "valid")

    def test_docker_execution_result_is_retained_unchanged(self) -> None:
        docker = {"status": "Passed", "stdout": "3\n", "exit_code": 0, "timeout_seconds": 3}
        report = self.build(ml=self.prediction, docker=docker)
        signal = report["signals"]["docker_execution"]
        self.assertTrue(signal["available"])
        for key, value in docker.items():
            self.assertEqual(signal[key], value)

    def test_evidence_and_verification_remain_separate_and_unchanged(self) -> None:
        report = self.build(ml=self.prediction)
        evidence = report["signals"]["evidence_retrieval"]["claims"][0]
        verified = report["signals"]["claim_verification"]["results"][0]
        self.assertEqual(evidence["source_url"], self.claims[0]["source_url"])
        self.assertEqual(verified["status"], "Supported")
        self.assertEqual(report["explanation"]["claims"], self.claims)
        self.assertNotIn("overall_reliability_score", report)

    def test_prediction_api_handles_malformed_input_missing_model_and_model_failure(self) -> None:
        malformed = predict_pass_rate(None)
        self.assertEqual(malformed["status"], "not_available")
        missing = predict_pass_rate("x = 1", model_path="missing-phase19-model.joblib")
        self.assertEqual(missing["status"], "not_available")

        class BrokenModel:
            def predict(self, _frame):
                raise RuntimeError("inference failed")

        with patch("joblib.load", return_value={"model": BrokenModel()}):
            failed = predict_pass_rate("x = 1")
        self.assertEqual(failed["status"], "not_available")
        self.assertIn("inference failed", failed["reason"])


if __name__ == "__main__":
    unittest.main()
