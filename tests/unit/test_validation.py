"""Tests for static Python validation; submitted code is never executed."""

import unittest

from codeguard.validation import validate_python


class ValidationTests(unittest.TestCase):
    def test_missing_code_is_reported(self) -> None:
        self.assertEqual(validate_python("  ").status, "missing")

    def test_valid_benign_function_passes_syntax_check(self) -> None:
        result = validate_python("def add(a, b):\n    return a + b\n")
        self.assertEqual(result.status, "valid")
        self.assertEqual(result.findings, [])

    def test_invalid_syntax_reports_line(self) -> None:
        result = validate_python("def broken(:\n    pass\n")
        self.assertEqual(result.status, "syntax_error")
        self.assertIn("line 1", result.message)

    def test_risky_calls_are_flagged_without_execution(self) -> None:
        result = validate_python("import os\nos.system('echo hello')\n")
        self.assertEqual(result.status, "valid_with_risks")
        self.assertTrue(any("os.system" in finding.message for finding in result.findings))

    def test_dynamic_execution_is_flagged(self) -> None:
        result = validate_python("eval('1 + 1')")
        self.assertEqual(result.status, "valid_with_risks")
        self.assertTrue(any("eval" in finding.message for finding in result.findings))


if __name__ == "__main__":
    unittest.main()
