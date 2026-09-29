"""Read-only component probes used by the developer health console."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import platform
from typing import Any

from codeguard.auth import DEVELOPER, require_role
from codeguard.execution import (
    DEFAULT_TIMEOUT_SECONDS,
    MAX_OUTPUT_BYTES,
    MAX_TIMEOUT_SECONDS,
    PYTHON_IMAGE,
    _find_docker,
)
from codeguard.ml.public_reliability import predict_pass_rate
from codeguard.retrieval import retrieve_evidence
from codeguard.storage import DEFAULT_DATABASE_PATH, _database, initialize_database


def _probe_docker(timeout: int = 3) -> dict[str, Any]:
    docker = _find_docker()
    if not docker:
        return {"status": "UNAVAILABLE", "cli": False, "engine": False, "image": False, "python_runtime": "Docker unavailable."}
    try:
        info = subprocess.run(
            [docker, "info", "--format", "{{.OSType}}"],
            capture_output=True, text=True, timeout=timeout, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"status": "UNAVAILABLE", "cli": True, "engine": False, "image": False, "python_runtime": "Not checked", "diagnostic": type(error).__name__}
    if info.returncode != 0 or info.stdout.strip() != "linux":
        return {"status": "WARNING", "cli": True, "engine": False, "image": False, "python_runtime": "Not checked", "diagnostic": (info.stderr or info.stdout).strip()[:500]}
    image = subprocess.run(
        [docker, "image", "inspect", PYTHON_IMAGE, "--format", "{{.Id}}"],
        capture_output=True, text=True, timeout=timeout, check=False,
    )
    return {
        "status": "READY" if image.returncode == 0 else "WARNING",
        "cli": True,
        "engine": True,
        "linux_containers": True,
        "image": image.returncode == 0,
        "image_id": image.stdout.strip()[:100] if image.returncode == 0 else "",
        "python_runtime": "Not run; use the harmless runtime probe on the Docker page." if image.returncode == 0 else "Image unavailable.",
        "diagnostic": "" if image.returncode == 0 else (image.stderr or image.stdout).strip()[:500],
    }


def run_docker_runtime_probe(
    actor_user_id: int, timeout: int = 15, database_path=DEFAULT_DATABASE_PATH
) -> dict[str, Any]:
    require_role(actor_user_id, DEVELOPER, database_path)
    docker = _find_docker()
    if not docker:
        return {"status": "UNAVAILABLE", "message": "Docker unavailable."}
    command = [
        docker, "run", "--rm", "--network=none", "--read-only", "--user=65534:65534",
        "--cap-drop=ALL", "--security-opt=no-new-privileges:true",
        "--memory=128m", "--memory-swap=128m", "--cpus=0.5", "--pids-limit=32",
        "--ulimit=cpu=2:2", "--ulimit=fsize=1048576:1048576", "--ulimit=nofile=64:64",
        "--tmpfs=/tmp:rw,nosuid,nodev,noexec,size=16m,mode=1777", "--workdir=/tmp",
        "--env=PYTHONDONTWRITEBYTECODE=1", "--env=PYTHONUNBUFFERED=1",
        PYTHON_IMAGE, "python", "--version",
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=max(3, min(timeout, 30)), check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"status": "ERROR", "message": type(error).__name__}
    return {
        "status": "READY" if result.returncode == 0 else "ERROR",
        "message": (result.stdout or result.stderr).strip()[:300],
        "exit_code": result.returncode,
    }


def docker_configuration() -> dict[str, Any]:
    return {
        "image": PYTHON_IMAGE,
        "network": "none",
        "filesystem": "read-only root; isolated writable /tmp only",
        "user": "65534:65534",
        "memory": "128 MiB",
        "memory_swap": "128 MiB",
        "cpu": "0.5",
        "process_limit": "32",
        "timeout_seconds": {"default": DEFAULT_TIMEOUT_SECONDS, "maximum": MAX_TIMEOUT_SECONDS, "outer_startup_grace": 15},
        "combined_output_limit_bytes": MAX_OUTPUT_BYTES,
        "security_note": "Local development execution boundary — not a production sandbox.",
    }


def docker_status(actor_user_id: int, database_path=DEFAULT_DATABASE_PATH) -> dict[str, Any]:
    require_role(actor_user_id, DEVELOPER, database_path)
    return {**_probe_docker(), "configuration": docker_configuration()}


def collect_health(actor_user_id: int, project_root: str | Path, database_path=DEFAULT_DATABASE_PATH) -> dict[str, Any]:
    require_role(actor_user_id, DEVELOPER, database_path)
    root = Path(project_root)
    initialize_database(database_path)
    checks: dict[str, dict[str, Any]] = {}
    app_entry = root / "frontend" / "app.py"
    checks["Application"] = {
        "status": "READY" if app_entry.is_file() else "ERROR",
        "entry_point": str(app_entry.relative_to(root)) if app_entry.is_relative_to(root) else str(app_entry),
        "python_version": platform.python_version(),
        "streamlit_version": _streamlit_version(),
        "diagnostic": "Health checks execute inside the running Streamlit process." if app_entry.is_file() else "Streamlit entry point is missing.",
    }
    try:
        with _database(database_path) as connection:
            checks["SQLite"] = {"status": "READY" if connection.execute("PRAGMA quick_check").fetchone()[0] == "ok" else "ERROR", "path": str(database_path)}
    except Exception as error:
        checks["SQLite"] = {"status": "ERROR", "diagnostic": type(error).__name__}

    docker = _probe_docker()
    checks["Docker engine and image"] = docker
    checks["Docker sandbox configuration"] = {"status": "READY", **docker_configuration()}

    model_path = root / "models" / "phase17" / "pass_rate_predictor.joblib"
    if model_path.is_file():
        prediction = predict_pass_rate("def add(a, b):\n    return a + b\n")
        checks["Phase 17 model"] = {
            "status": "READY" if prediction.get("status") == "predicted" else "WARNING",
            "model_path": str(model_path.relative_to(root)),
            "model": prediction.get("model", ""),
            "target": prediction.get("model_metadata", {}).get("target", "Not recorded"),
            "inference_status": prediction.get("status"),
            "diagnostic": prediction.get("reason", ""),
            "scope": "Auxiliary estimate of the upstream dataset's execution pass_rate; not general code correctness or security.",
        }
    else:
        checks["Phase 17 model"] = {"status": "UNAVAILABLE", "message": "ML model unavailable."}

    corpus_path = root / "backend" / "src" / "codeguard" / "corpus" / "python_docs.json"
    try:
        corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
        documents = corpus if isinstance(corpus, list) else corpus.get("documents", corpus.get("chunks", []))
        retrieval = retrieve_evidence("Python list mutability", top_k=1)
        checks["Evidence corpus"] = {
            "status": "READY" if documents and retrieval else "WARNING",
            "document_count": len(documents),
            "retrieval_status": "READY" if retrieval else "NO_MATCH",
            "source_urls": sorted({row.get("source_url", "") for row in documents if row.get("source_url")}),
        }
    except (OSError, ValueError, TypeError, KeyError) as error:
        checks["Evidence corpus"] = {"status": "ERROR", "diagnostic": type(error).__name__}

    directories = ("backend", "frontend", "data", "models", "reports", "tests")
    missing = [name for name in directories if not (root / name).is_dir()]
    checks["Required directories"] = {"status": "READY" if not missing else "ERROR", "missing": missing}
    checks["Configuration"] = {
        "status": "READY",
        "environment": os.environ.get("CODEGUARD_ENV", "local"),
        "log_level": os.environ.get("LOG_LEVEL", "INFO"),
        "openai_api_key_configured": bool(os.environ.get("OPENAI_API_KEY", "").strip()),
        "secret_values_displayed": False,
    }
    overall = "ERROR" if any(item.get("status") == "ERROR" for item in checks.values()) else (
        "WARNING" if any(item.get("status") in {"WARNING", "UNAVAILABLE"} for item in checks.values()) else "READY"
    )
    return {"status": overall, "checked_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "checks": checks}


def developer_statistics(actor_user_id: int, database_path=DEFAULT_DATABASE_PATH) -> dict[str, Any]:
    require_role(actor_user_id, DEVELOPER, database_path)
    initialize_database(database_path)
    today = datetime.now(timezone.utc).date().isoformat()
    with _database(database_path) as connection:
        total = connection.execute("SELECT COUNT(*) FROM evaluation_sessions").fetchone()[0]
        today_count = connection.execute("SELECT COUNT(*) FROM evaluation_sessions WHERE substr(created_at,1,10)=?", (today,)).fetchone()[0]
        claims = connection.execute("SELECT COUNT(*) FROM explanation_claims").fetchone()[0]
        evidence_lookups = connection.execute("SELECT COUNT(*) FROM application_logs WHERE event='EVIDENCE_RETRIEVED'").fetchone()[0]
        tests = connection.execute("SELECT COUNT(*) FROM test_results").fetchone()[0]
        logs = connection.execute("SELECT COUNT(*) FROM application_logs WHERE substr(timestamp,1,10)=?", (today,)).fetchone()[0]
        errors = connection.execute("SELECT COUNT(*) FROM application_logs WHERE substr(timestamp,1,10)=? AND level IN ('ERROR','CRITICAL')", (today,)).fetchone()[0]
        users = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        docker_runs = connection.execute("SELECT COUNT(*) FROM application_logs WHERE event='DOCKER_EXECUTION_COMPLETED'").fetchone()[0]
        avg_execution = connection.execute(
            "SELECT AVG(metric_value) FROM evaluation_metrics WHERE metric_name LIKE '%python_process_wall_time' AND metric_value IS NOT NULL"
        ).fetchone()[0]
    return {
        "total_evaluations": total,
        "evaluations_today_utc": today_count,
        "successful_evaluations": connection_scalar(database_path, "SELECT COUNT(DISTINCT evaluation_id) FROM application_logs WHERE event='DOCKER_EXECUTION_COMPLETED' AND status='Passed' AND evaluation_id<>''"),
        "failed_evaluations": connection_scalar(database_path, "SELECT COUNT(DISTINCT evaluation_id) FROM application_logs WHERE event='EVALUATION_FAILED' AND evaluation_id<>''"),
        "average_python_process_seconds": avg_execution,
        "docker_executions": docker_runs,
        "claims_analyzed": claims,
        "evidence_lookups": evidence_lookups,
        "function_test_rows": tests,
        "errors_today_utc": errors,
        "logs_today_utc": logs,
        "users": users,
        "database_status": "READY",
        "active_model": "Phase 17 pass_rate predictor" if (Path(__file__).resolve().parents[3] / "models/phase17/pass_rate_predictor.joblib").is_file() else "ML model unavailable",
    }


def connection_scalar(database_path, query: str) -> int:
    with _database(database_path) as connection:
        return int(connection.execute(query).fetchone()[0] or 0)


def _streamlit_version() -> str:
    try:
        import streamlit

        return str(streamlit.__version__)
    except ImportError:
        return "Unavailable"
