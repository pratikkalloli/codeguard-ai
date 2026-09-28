"""End-to-end Phase 18 demonstrations; enabled only with Docker integration."""

import os
import unittest

from codeguard.phase18_demo import run_phase18_demonstrations


@unittest.skipUnless(
    os.environ.get("CODEGUARD_DOCKER_INTEGRATION") == "1",
    "Set CODEGUARD_DOCKER_INTEGRATION=1 to run Phase 18 Docker demonstrations.",
)
class Phase18EndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run_phase18_demonstrations()
        cls.by_id = {case["case_id"]: case for case in cls.result["cases"]}

    def test_correct_case_completes_all_stages(self) -> None:
        case = self.by_id["correct"]
        self.assertTrue(case["expectations_met"])
        self.assertEqual(case["observed_behavior"]["test_status"], "passed")
        self.assertEqual(case["observed_behavior"]["claim_status"], "Supported")
        self.assertTrue(case["final_output"]["ml_reliability"]["available"])
        signal = case["final_output"]["ml_reliability"]
        self.assertEqual(case["final_output"]["signals"]["ml_reliability"], signal)
        self.assertEqual(signal["model"], "linear_svr_c0_1")
        self.assertEqual(signal["dataset_size"]["downloaded_records"], 60000)
        self.assertEqual(signal["dataset_size"]["usable_records"], 53401)
        self.assertIsNone(signal["confidence"])
        self.assertGreaterEqual(signal["prediction"], 0.0)
        self.assertLessEqual(signal["prediction"], 1.0)

    def test_incorrect_code_is_exposed_by_function_test(self) -> None:
        case = self.by_id["incorrect_code"]
        self.assertTrue(case["expectations_met"])
        self.assertEqual(case["observed_behavior"]["ast_status"], "valid")
        self.assertEqual(case["docker_execution_result"]["status"], "Passed")
        self.assertEqual(case["observed_behavior"]["test_status"], "failed")

    def test_false_explanation_claim_conflicts_with_documentation(self) -> None:
        case = self.by_id["explanation_error"]
        self.assertTrue(case["expectations_met"])
        self.assertEqual(case["observed_behavior"]["claim_status"], "Contradicted")
        self.assertTrue(case["evidence_results"][0]["chunks"])

    def test_quadratic_solution_has_measured_runtime(self) -> None:
        case = self.by_id["performance"]
        self.assertTrue(case["expectations_met"])
        measurement = next(
            row for row in case["performance_result"]["measurements"]
            if row["metric_name"] == "python_process_wall_time"
        )
        self.assertIsInstance(measurement["metric_value"], (int, float))
        self.assertGreater(measurement["metric_value"], 0)

    def test_risky_file_access_is_flagged_and_container_test_passes(self) -> None:
        case = self.by_id["risk"]
        self.assertTrue(case["expectations_met"])
        self.assertEqual(case["observed_behavior"]["ast_status"], "valid_with_risks")
        self.assertTrue(any(finding["rule"] == "risky_call" for finding in case["ast_result"]["findings"]))
        self.assertEqual(case["observed_behavior"]["test_status"], "passed")


if __name__ == "__main__":
    unittest.main()
