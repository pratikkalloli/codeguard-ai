"""Tests for CodeGuard AI's SQLite persistence layer."""

import tempfile
import unittest
from pathlib import Path
import sqlite3

from codeguard.storage import (
    get_claim_results,
    get_evaluation,
    get_evaluation_metrics,
    get_test_results,
    list_evaluations,
    save_evaluation,
    save_claim_results,
    save_evaluation_metrics,
    save_test_results,
    save_reliability_report,
    get_reliability_report,
)


class StorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "test_codeguard.db"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_save_and_retrieve_evaluation_with_multiple_code_blocks(self) -> None:
        session_id = save_evaluation(
            question="Write an add function.",
            raw_response="Intro\n```python\ndef add(a, b): return a + b\n```\nDone",
            code_blocks=["def add(a, b): return a + b", "print('example')"],
            explanation="Intro\n\nDone",
            database_path=self.database_path,
        )

        history = list_evaluations(database_path=self.database_path)
        detail = get_evaluation(session_id, database_path=self.database_path)

        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["id"], session_id)
        self.assertEqual(history[0]["question_text"], "Write an add function.")
        self.assertEqual(history[0]["code_block_count"], 2)
        self.assertIsNotNone(detail)
        self.assertEqual(detail["raw_response"], "Intro\n```python\ndef add(a, b): return a + b\n```\nDone")
        self.assertEqual(
            [block["code_text"] for block in detail["code_blocks"]],
            ["def add(a, b): return a + b", "print('example')"],
        )

    def test_get_unknown_evaluation_returns_none(self) -> None:
        self.assertIsNone(get_evaluation(1234, database_path=self.database_path))

    def test_empty_question_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            save_evaluation(
                question="  ",
                raw_response="An answer",
                code_blocks=[],
                explanation="An answer",
                database_path=self.database_path,
            )

    def test_latest_test_results_are_saved_and_retrieved(self) -> None:
        session_id = save_evaluation(
            question="Add two numbers.",
            raw_response="```python\ndef add(a, b): return a + b\n```",
            code_blocks=["def add(a, b): return a + b"],
            explanation="",
            database_path=self.database_path,
        )
        evaluation = get_evaluation(session_id, database_path=self.database_path)
        save_test_results(
            evaluation["response_id"],
            [
                {
                    "test_name": "Test 1",
                    "status": "passed",
                    "inputs_json": "[2, 3]",
                    "expected_output": "5",
                    "actual_output": "5",
                    "error_message": "",
                }
            ],
            database_path=self.database_path,
        )

        results = get_test_results(evaluation["response_id"], database_path=self.database_path)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "passed")
        self.assertEqual(results[0]["inputs_json"], "[2, 3]")

    def test_performance_metrics_keep_measurement_type_and_unavailable_values(self) -> None:
        session_id = save_evaluation(
            question="Measure add.",
            raw_response="```python\ndef add(a, b): return a+b\n```",
            code_blocks=["def add(a, b): return a+b"],
            explanation="",
            database_path=self.database_path,
        )
        evaluation = get_evaluation(session_id, database_path=self.database_path)
        save_evaluation_metrics(
            evaluation["response_id"],
            [
                {
                    "metric_name": "python_process_wall_time",
                    "metric_value": 0.001,
                    "unit": "seconds",
                    "measurement_type": "in-container child process wall time",
                },
                {
                    "metric_name": "container_memory_peak",
                    "metric_value": None,
                    "unit": "bytes",
                    "measurement_type": "unavailable",
                },
            ],
            database_path=self.database_path,
        )
        metrics = get_evaluation_metrics(evaluation["response_id"], database_path=self.database_path)
        self.assertEqual(len(metrics), 2)
        self.assertEqual(metrics[0]["measurement_type"], "in-container child process wall time")
        self.assertIsNone(metrics[1]["metric_value"])
        self.assertEqual(metrics[1]["measurement_type"], "unavailable")

    def test_independent_measurement_categories_do_not_overwrite_each_other(self) -> None:
        session_id = save_evaluation(
            question="Compare measurements.", raw_response="Answer.", code_blocks=[],
            explanation="", database_path=self.database_path,
        )
        evaluation = get_evaluation(session_id, database_path=self.database_path)
        response_id = evaluation["response_id"]
        save_evaluation_metrics(
            response_id,
            [{"metric_name": "model_api_wall_time", "metric_value": 1.2, "unit": "seconds"}],
            database_path=self.database_path,
        )
        save_evaluation_metrics(
            response_id,
            [{"metric_name": "python_process_wall_time", "metric_value": 0.02, "unit": "seconds"}],
            database_path=self.database_path,
        )
        metrics = get_evaluation_metrics(response_id, database_path=self.database_path)
        self.assertEqual({item["metric_name"] for item in metrics}, {"model_api_wall_time", "python_process_wall_time"})

    def test_explanation_claim_analysis_is_persisted(self) -> None:
        session_id = save_evaluation(
            question="Explain lists.",
            raw_response="Python lists are mutable.",
            code_blocks=[],
            explanation="Python lists are mutable.",
            database_path=self.database_path,
        )
        evaluation = get_evaluation(session_id, database_path=self.database_path)
        save_claim_results(
            evaluation["response_id"],
            [
                {
                    "claim_text": "Python lists are mutable.",
                    "status": "Insufficient evidence",
                    "reason": "No trusted docs attached.",
                    "evidence_text": "",
                    "source": "Python Software Foundation",
                    "title": "Python docs",
                    "source_url": "https://docs.python.org/3/tutorial/index.html",
                    "retrieval_score": 0.42,
                    "evidence_chunk_id": "sample#1",
                    "retrieval_seconds": 0.0001,
                }
            ],
            database_path=self.database_path,
        )
        claims = get_claim_results(evaluation["response_id"], database_path=self.database_path)
        self.assertEqual(claims[0]["status"], "Insufficient evidence")
        self.assertEqual(claims[0]["claim_text"], "Python lists are mutable.")
        self.assertEqual(claims[0]["source"], "Python Software Foundation")
        self.assertEqual(claims[0]["source_url"], "https://docs.python.org/3/tutorial/index.html")
        self.assertEqual(claims[0]["retrieval_score"], 0.42)

    def test_ml_advisory_fields_are_persisted_separately_from_rule_result(self) -> None:
        session_id = save_evaluation(
            question="Explain a claim.", raw_response="Claim response.", code_blocks=[],
            explanation="Claim response.", database_path=self.database_path,
        )
        evaluation = get_evaluation(session_id, database_path=self.database_path)
        save_claim_results(evaluation["response_id"], [{
            "claim_text": "An unsupported claim.",
            "status": "Insufficient evidence",
            "rule_result": "Insufficient evidence",
            "ml_result": "SUPPORTED",
            "ml_confidence": 0.77,
            "verification_method": "hybrid",
            "ml_review_required": True,
            "reason": "Advisory only.",
        }], database_path=self.database_path)
        result = get_claim_results(evaluation["response_id"], database_path=self.database_path)[0]
        self.assertEqual(result["status"], "Insufficient evidence")
        self.assertEqual(result["rule_result"], "Insufficient evidence")
        self.assertEqual(result["ml_result"], "SUPPORTED")
        self.assertEqual(result["ml_confidence"], 0.77)
        self.assertEqual(result["verification_method"], "hybrid")
        self.assertEqual(result["ml_review_required"], 1)

    def test_phase8_claim_table_is_migrated_without_losing_rows(self) -> None:
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute(
                """CREATE TABLE explanation_claims (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    response_id INTEGER NOT NULL,
                    claim_index INTEGER NOT NULL,
                    claim_text TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reason TEXT NOT NULL DEFAULT '',
                    evidence_text TEXT NOT NULL DEFAULT '',
                    UNIQUE(response_id, claim_index)
                )"""
            )
            connection.execute(
                """INSERT INTO explanation_claims
                   (response_id, claim_index, claim_text, status, reason, evidence_text)
                   VALUES (1, 1, 'Python lists are mutable.', 'Insufficient evidence', 'Phase 8', '')"""
            )
            connection.commit()
        finally:
            connection.close()
        claims = get_claim_results(1, database_path=self.database_path)
        self.assertEqual(claims[0]["claim_text"], "Python lists are mutable.")
        self.assertEqual(claims[0]["source_url"], "")
        self.assertIsNone(claims[0]["retrieval_score"])

    def test_owned_history_and_reports_use_additive_schema(self) -> None:
        from codeguard.auth import register_user

        owner_id = register_user("owner@example.test", "an owner password here", self.database_path)["id"]
        session_id = save_evaluation(
            question="Owned question", raw_response="Answer", code_blocks=[], explanation="",
            database_path=self.database_path, owner_user_id=owner_id, evaluation_name="Example",
        )
        self.assertEqual(list_evaluations(database_path=self.database_path, owner_user_id=owner_id)[0]["id"], session_id)
        self.assertEqual(list_evaluations(database_path=self.database_path, owner_user_id=7), [])
        save_reliability_report(session_id, {"report_version": 2, "signals": {}}, self.database_path)
        self.assertIsNone(get_reliability_report(session_id, self.database_path, owner_user_id=7))
        self.assertEqual(
            get_reliability_report(session_id, self.database_path, owner_user_id=owner_id)["report_version"], 2
        )


if __name__ == "__main__":
    unittest.main()
