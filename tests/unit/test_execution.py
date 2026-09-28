"""Unit tests for test-case result handling; no host code execution occurs."""

import unittest
from unittest.mock import patch

from codeguard.execution import (
    ExecutionResult,
    run_function_tests,
    run_python,
)


class ExecutionTests(unittest.TestCase):
    def test_empty_code_is_blocked_without_calling_docker(self) -> None:
        with patch("codeguard.execution.subprocess.run") as docker_call:
            result = run_python(" ")
        self.assertEqual(result.status, "Security blocked")
        docker_call.assert_not_called()

    def test_invalid_timeout_is_blocked(self) -> None:
        result = run_python("print('safe')", timeout_seconds=60)
        self.assertEqual(result.status, "Security blocked")

    @patch("codeguard.execution.run_python")
    def test_function_test_passes_on_matching_json_return(self, run_mock) -> None:
        run_mock.return_value = ExecutionResult(
            status="Passed",
            stdout="__CODEGUARD_RESULT__5\n",
            exit_code=0,
            duration_seconds=0.2,
        )
        results = run_function_tests(
            "def add(a, b): return a + b",
            "add",
            [{"inputs": [2, 3], "expected": 5}],
        )
        self.assertEqual(results[0].status, "passed")
        self.assertEqual(results[0].actual_output, "5")

    @patch("codeguard.execution.run_python")
    def test_function_test_fails_on_mismatched_json_return(self, run_mock) -> None:
        run_mock.return_value = ExecutionResult(
            status="Passed",
            stdout="__CODEGUARD_RESULT__4\n",
            exit_code=0,
        )
        results = run_function_tests(
            "def add(a, b): return a - b",
            "add",
            [{"inputs": [2, 3], "expected": 5}],
        )
        self.assertEqual(results[0].status, "failed")

    @patch("codeguard.execution.run_python")
    def test_json_boolean_is_not_equal_to_integer_one(self, run_mock) -> None:
        run_mock.return_value = ExecutionResult(
            status="Passed",
            stdout="__CODEGUARD_RESULT__1\n",
            exit_code=0,
        )
        results = run_function_tests(
            "def answer(): return 1",
            "answer",
            [{"inputs": [], "expected": True}],
        )
        self.assertEqual(results[0].status, "failed")

    def test_invalid_function_name_is_blocked(self) -> None:
        results = run_function_tests("pass", "add(1)", [{"inputs": [], "expected": None}])
        self.assertEqual(results[0].status, "security_blocked")


if __name__ == "__main__":
    unittest.main()
