"""Real health checks report availability and never imply unchecked health."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codeguard.auth import AuthorizationError, bootstrap_developer, register_user
from codeguard.events import log_event
from codeguard.health import collect_health, developer_statistics, docker_configuration, docker_status, run_docker_runtime_probe
from codeguard.storage import get_evaluation, save_evaluation, save_evaluation_metrics


class Phase20HealthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.database = self.root / "health.db"
        self.dev = bootstrap_developer("health-dev", "developer health password", self.database)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_docker_unavailable_is_reported_without_container_run(self) -> None:
        with patch("codeguard.health._find_docker", return_value=None), patch("codeguard.health.subprocess.run") as run:
            result = docker_status(self.dev["id"], self.database)
            probe = run_docker_runtime_probe(self.dev["id"], timeout=3, database_path=self.database)
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertFalse(result["engine"])
        self.assertEqual(probe["status"], "UNAVAILABLE")
        run.assert_not_called()

    def test_docker_probe_uses_engine_and_local_image_checks(self) -> None:
        responses = [
            type("R", (), {"returncode": 0, "stdout": "linux\n", "stderr": ""})(),
            type("R", (), {"returncode": 0, "stdout": "sha256:abc\n", "stderr": ""})(),
        ]
        with patch("codeguard.health._find_docker", return_value="docker.exe"), patch(
            "codeguard.health.subprocess.run", side_effect=responses
        ) as run:
            result = docker_status(self.dev["id"], self.database)
        self.assertEqual(result["status"], "READY")
        self.assertTrue(result["engine"])
        self.assertTrue(result["image"])
        self.assertEqual(run.call_count, 2)

    def test_sandbox_dashboard_preserves_all_restrictions(self) -> None:
        config = docker_configuration()
        self.assertEqual(config["network"], "none")
        self.assertIn("read-only", config["filesystem"])
        self.assertEqual(config["user"], "65534:65534")
        self.assertEqual(config["memory"], "128 MiB")
        self.assertEqual(config["cpu"], "0.5")
        self.assertEqual(config["process_limit"], "32")
        self.assertIn("maximum", config["timeout_seconds"])
        self.assertGreater(config["combined_output_limit_bytes"], 0)
        self.assertIn("not a production sandbox", config["security_note"])

    def test_health_checks_actual_database_model_corpus_and_directories(self) -> None:
        for folder in ("backend", "frontend", "data", "models", "reports", "tests"):
            (self.root / folder).mkdir()
        (self.root / "frontend" / "app.py").write_text("# fixture entry point", encoding="utf-8")
        model_dir = self.root / "models" / "phase17"
        model_dir.mkdir()
        (model_dir / "pass_rate_predictor.joblib").write_bytes(b"artifact")
        corpus_dir = self.root / "backend" / "src" / "codeguard" / "corpus"
        corpus_dir.mkdir(parents=True)
        (corpus_dir / "python_docs.json").write_text(json.dumps([{"url": "https://docs.python.org"}]), encoding="utf-8")
        ready_docker = {"status": "READY", "cli": True, "engine": True, "image": True}
        with patch("codeguard.health._probe_docker", return_value=ready_docker), patch(
            "codeguard.health.predict_pass_rate", return_value={"status": "predicted", "model": "phase17"}
        ), patch("codeguard.health.retrieve_evidence", return_value=[{"source_url": "https://docs.python.org"}]):
            result = collect_health(self.dev["id"], self.root, self.database)
        self.assertEqual(result["status"], "READY")
        self.assertEqual(result["checks"]["SQLite"]["status"], "READY")
        self.assertEqual(result["checks"]["Phase 17 model"]["status"], "READY")
        self.assertEqual(result["checks"]["Evidence corpus"]["document_count"], 1)

    def test_missing_ml_artifact_and_corpus_are_not_reported_ready(self) -> None:
        for folder in ("backend", "frontend", "data", "models", "reports", "tests"):
            (self.root / folder).mkdir()
        with patch("codeguard.health._probe_docker", return_value={"status": "UNAVAILABLE"}):
            result = collect_health(self.dev["id"], self.root, self.database)
        self.assertEqual(result["checks"]["Phase 17 model"]["status"], "UNAVAILABLE")
        self.assertEqual(result["checks"]["Evidence corpus"]["status"], "ERROR")
        self.assertEqual(result["status"], "ERROR")

    def test_user_cannot_read_developer_health(self) -> None:
        user = register_user("health-user", "regular user password", self.database)
        with self.assertRaises(AuthorizationError):
            collect_health(user["id"], self.root, self.database)
        with self.assertRaises(AuthorizationError):
            docker_status(user["id"], self.database)

    def test_developer_statistics_use_real_execution_ids_and_metric_names(self) -> None:
        evaluation_id = save_evaluation("question", "```python\npass\n```", ["pass"], "", database_path=self.database)
        evaluation = get_evaluation(evaluation_id, self.database)
        save_evaluation_metrics(evaluation["response_id"], [
            {"metric_name": "code_1_python_process_wall_time", "metric_value": 0.25, "unit": "seconds"},
        ], self.database)
        log_event("DOCKER_EXECUTION_COMPLETED", evaluation_id=evaluation_id, status="Passed", database_path=self.database)
        result = developer_statistics(self.dev["id"], self.database)
        self.assertEqual(result["successful_evaluations"], 1)
        self.assertAlmostEqual(result["average_python_process_seconds"], 0.25)


if __name__ == "__main__":
    unittest.main()
