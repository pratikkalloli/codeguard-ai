"""Harmless integration tests that execute only inside the restricted Docker runner.

Enable explicitly with CODEGUARD_DOCKER_INTEGRATION=1 after Docker Desktop is
running and `python:3.12-slim` has been downloaded.
"""

import os
import unittest

from codeguard.execution import run_function_tests, run_python


@unittest.skipUnless(
    os.environ.get("CODEGUARD_DOCKER_INTEGRATION") == "1",
    "Set CODEGUARD_DOCKER_INTEGRATION=1 to run safe Docker integration samples.",
)
class DockerExecutionIntegrationTests(unittest.TestCase):
    def test_print_sample_returns_separated_timing_and_memory(self) -> None:
        result = run_python("print('safe integration sample')")
        self.assertEqual(result.status, "Passed", result.stderr)
        self.assertEqual(result.stdout.strip(), "safe integration sample")
        self.assertGreater(result.code_execution_seconds or 0, 0)
        self.assertGreater(result.duration_seconds, result.code_execution_seconds or 0)
        self.assertIsNotNone(result.image_readiness_seconds)
        self.assertIsNotNone(result.docker_overhead_estimate_seconds)
        if result.memory_peak_bytes is not None:
            self.assertGreater(result.memory_peak_bytes, 0)
            self.assertIn("whole container", result.memory_measurement_type)
        else:
            self.assertIn("Unavailable", result.memory_measurement_type)
        if result.container_startup_seconds is None:
            self.assertIn("Unavailable", result.container_startup_measurement_type)
        else:
            self.assertGreater(result.container_startup_seconds, 0)

    def test_python_process_timing_includes_bounded_sleep(self) -> None:
        result = run_python("import time\ntime.sleep(0.2)\n", timeout_seconds=5)
        self.assertEqual(result.status, "Passed", result.stderr)
        self.assertGreaterEqual(result.code_execution_seconds or 0, 0.18)
        self.assertGreater(result.docker_run_seconds or 0, result.code_execution_seconds or 0)

    def test_cgroup_peak_tracks_bounded_memory_allocation(self) -> None:
        result = run_python(
            "buffer = bytearray(16 * 1024 * 1024)\nprint(len(buffer))\n",
            timeout_seconds=5,
        )
        self.assertEqual(result.status, "Passed", result.stderr)
        self.assertEqual(result.stdout.strip(), str(16 * 1024 * 1024))
        if result.memory_peak_bytes is not None:
            self.assertGreater(result.memory_peak_bytes, 16 * 1024 * 1024)

    def test_safe_addition_function_cases(self) -> None:
        results = run_function_tests(
            "def add(a, b):\n    return a + b\n",
            "add",
            [
                {"inputs": [2, 3], "expected": 5},
                {"inputs": [-2, 5], "expected": 3},
            ],
        )
        self.assertEqual([result.status for result in results], ["passed", "passed"])
        self.assertTrue(all(result.code_execution_seconds for result in results))

    def test_harmless_bounded_loop_times_out(self) -> None:
        result = run_python("while True:\n    pass\n", timeout_seconds=1)
        self.assertEqual(result.status, "Timeout")


if __name__ == "__main__":
    unittest.main()
