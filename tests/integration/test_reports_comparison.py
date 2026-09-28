"""Tests for descriptive reports and same-question comparison grouping."""

import unittest

from codeguard.comparison import group_evaluations_by_question
from codeguard.reports import build_reliability_report


class ReportComparisonTests(unittest.TestCase):
    def test_grouping_uses_same_question_without_matching_different_prompts(self) -> None:
        grouped = group_evaluations_by_question(
            [
                {"id": 1, "question_text": "Write an add function."},
                {"id": 2, "question_text": "  WRITE an add function. "},
                {"id": 3, "question_text": "Write a multiply function."},
            ]
        )
        self.assertEqual(len(grouped), 1)
        self.assertEqual([row["id"] for row in next(iter(grouped.values()))], [1, 2])

    def test_report_has_transparent_counts_and_no_overall_score(self) -> None:
        report = build_reliability_report(
            {
                "id": 9,
                "created_at": "2026-09-26T00:00:00+00:00",
                "question_text": "Write add.",
                "model_name": "Manual / Model A",
                "explanation_text": "Python lists are mutable.",
                "code_blocks": [{"block_index": 1, "code_text": "def add(a, b): return a + b"}],
            },
            [{"test_name": "Test 1", "status": "passed"}],
            [{"metric_name": "python_process_wall_time", "metric_value": 0.1}],
            [{"claim_text": "Python lists are mutable.", "status": "Supported"}],
        )
        self.assertEqual(report["test_summary"]["pass_percentage"], 100)
        self.assertEqual(report["explanation"]["status_counts"], {"Supported": 1})
        self.assertIn("code_blocks", report)
        self.assertNotIn("overall_reliability_score", report)


if __name__ == "__main__":
    unittest.main()
