"""SQLite persistence for CodeGuard AI evaluation sessions."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Any
from collections.abc import Iterator


DEFAULT_DATABASE_PATH = Path(__file__).resolve().parents[3] / "data" / "codeguard.db"


def _connect(database_path: str | Path = DEFAULT_DATABASE_PATH) -> sqlite3.Connection:
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def _database(database_path: str | Path) -> Iterator[sqlite3.Connection]:
    """Commit or roll back a connection and always release its file handle."""
    connection = _connect(database_path)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialize_database(database_path: str | Path = DEFAULT_DATABASE_PATH) -> None:
    """Create the evaluation tables if they do not already exist."""
    schema = """
    CREATE TABLE IF NOT EXISTS evaluation_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS coding_questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL UNIQUE REFERENCES evaluation_sessions(id) ON DELETE CASCADE,
        question_text TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS ai_responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL REFERENCES evaluation_sessions(id) ON DELETE CASCADE,
        model_name TEXT NOT NULL DEFAULT 'Manual input',
        raw_response TEXT NOT NULL,
        explanation_text TEXT NOT NULL DEFAULT ''
    );

    CREATE TABLE IF NOT EXISTS extracted_code (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        response_id INTEGER NOT NULL REFERENCES ai_responses(id) ON DELETE CASCADE,
        block_index INTEGER NOT NULL,
        code_text TEXT NOT NULL,
        UNIQUE(response_id, block_index)
    );

    CREATE TABLE IF NOT EXISTS test_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        response_id INTEGER NOT NULL REFERENCES ai_responses(id) ON DELETE CASCADE,
        test_name TEXT NOT NULL DEFAULT '',
        inputs_json TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'not_run',
        expected_output TEXT,
        actual_output TEXT,
        error_message TEXT
    );

    CREATE TABLE IF NOT EXISTS evaluation_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        response_id INTEGER NOT NULL REFERENCES ai_responses(id) ON DELETE CASCADE,
        metric_name TEXT NOT NULL,
        metric_value REAL,
        unit TEXT NOT NULL DEFAULT '',
        measurement_type TEXT NOT NULL DEFAULT ''
    );

    CREATE TABLE IF NOT EXISTS explanation_claims (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        response_id INTEGER NOT NULL REFERENCES ai_responses(id) ON DELETE CASCADE,
        claim_index INTEGER NOT NULL,
        claim_text TEXT NOT NULL,
        status TEXT NOT NULL,
        reason TEXT NOT NULL DEFAULT '',
        evidence_text TEXT NOT NULL DEFAULT '',
        source TEXT NOT NULL DEFAULT '',
        title TEXT NOT NULL DEFAULT '',
        source_url TEXT NOT NULL DEFAULT '',
        retrieval_score REAL,
        evidence_chunk_id TEXT NOT NULL DEFAULT '',
        retrieval_seconds REAL,
        rule_result TEXT NOT NULL DEFAULT '',
        ml_result TEXT,
        ml_confidence REAL,
        verification_method TEXT NOT NULL DEFAULT 'rule',
        ml_review_required INTEGER NOT NULL DEFAULT 0,
        UNIQUE(response_id, claim_index)
    );

    CREATE INDEX IF NOT EXISTS idx_sessions_created_at
        ON evaluation_sessions(created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_responses_session_id
        ON ai_responses(session_id);
    """
    with _database(database_path) as connection:
        connection.executescript(schema)
        columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(test_results)").fetchall()
        }
        if "inputs_json" not in columns:
            connection.execute(
                "ALTER TABLE test_results ADD COLUMN inputs_json TEXT NOT NULL DEFAULT ''"
            )
        metric_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(evaluation_metrics)").fetchall()
        }
        if "measurement_type" not in metric_columns:
            connection.execute(
                "ALTER TABLE evaluation_metrics ADD COLUMN measurement_type TEXT NOT NULL DEFAULT ''"
            )
        claim_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(explanation_claims)").fetchall()
        }
        claim_migrations = {
            "source": "TEXT NOT NULL DEFAULT ''",
            "title": "TEXT NOT NULL DEFAULT ''",
            "source_url": "TEXT NOT NULL DEFAULT ''",
            "retrieval_score": "REAL",
            "evidence_chunk_id": "TEXT NOT NULL DEFAULT ''",
            "retrieval_seconds": "REAL",
            "rule_result": "TEXT NOT NULL DEFAULT ''",
            "ml_result": "TEXT",
            "ml_confidence": "REAL",
            "verification_method": "TEXT NOT NULL DEFAULT 'rule'",
            "ml_review_required": "INTEGER NOT NULL DEFAULT 0",
        }
        for column, definition in claim_migrations.items():
            if column not in claim_columns:
                connection.execute(f"ALTER TABLE explanation_claims ADD COLUMN {column} {definition}")


def save_evaluation(
    question: str,
    raw_response: str,
    code_blocks: list[str],
    explanation: str,
    model_name: str = "Manual input",
    database_path: str | Path = DEFAULT_DATABASE_PATH,
) -> int:
    """Save an input and extraction result; return its session ID."""
    if not question.strip():
        raise ValueError("Question cannot be empty.")
    if not raw_response.strip():
        raise ValueError("Response cannot be empty.")

    initialize_database(database_path)
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _database(database_path) as connection:
        cursor = connection.execute(
            "INSERT INTO evaluation_sessions (created_at) VALUES (?)", (created_at,)
        )
        session_id = int(cursor.lastrowid)
        connection.execute(
            "INSERT INTO coding_questions (session_id, question_text) VALUES (?, ?)",
            (session_id, question.strip()),
        )
        response_cursor = connection.execute(
            """INSERT INTO ai_responses
               (session_id, model_name, raw_response, explanation_text)
               VALUES (?, ?, ?, ?)""",
            (session_id, model_name.strip() or "Manual input", raw_response, explanation),
        )
        response_id = int(response_cursor.lastrowid)
        connection.executemany(
            "INSERT INTO extracted_code (response_id, block_index, code_text) VALUES (?, ?, ?)",
            [(response_id, index, code) for index, code in enumerate(code_blocks, start=1)],
        )
    return session_id


def list_evaluations(
    limit: int = 100, database_path: str | Path = DEFAULT_DATABASE_PATH
) -> list[dict[str, Any]]:
    """Return recent evaluation summaries, newest first."""
    initialize_database(database_path)
    with _database(database_path) as connection:
        rows = connection.execute(
            """SELECT s.id, s.created_at, q.question_text, r.model_name,
                      (SELECT COUNT(*) FROM extracted_code c
                       JOIN ai_responses ar ON ar.id = c.response_id
                       WHERE ar.session_id = s.id) AS code_block_count
               FROM evaluation_sessions s
               JOIN coding_questions q ON q.session_id = s.id
               JOIN ai_responses r ON r.session_id = s.id
               ORDER BY s.id DESC LIMIT ?""",
            (max(1, min(int(limit), 500)),),
        ).fetchall()
    return [dict(row) for row in rows]


def get_evaluation(
    session_id: int, database_path: str | Path = DEFAULT_DATABASE_PATH
) -> dict[str, Any] | None:
    """Load one saved evaluation and its extracted code blocks."""
    initialize_database(database_path)
    with _database(database_path) as connection:
        row = connection.execute(
            """SELECT s.id, s.created_at, q.question_text, r.id AS response_id,
                      r.model_name, r.raw_response, r.explanation_text
               FROM evaluation_sessions s
               JOIN coding_questions q ON q.session_id = s.id
               JOIN ai_responses r ON r.session_id = s.id
               WHERE s.id = ? ORDER BY r.id LIMIT 1""",
            (session_id,),
        ).fetchone()
        if row is None:
            return None
        result = dict(row)
        code_rows = connection.execute(
            "SELECT block_index, code_text FROM extracted_code WHERE response_id = ? ORDER BY block_index",
            (result["response_id"],),
        ).fetchall()
    result["code_blocks"] = [dict(code_row) for code_row in code_rows]
    return result


def save_test_results(
    response_id: int,
    results: list[dict[str, Any]],
    database_path: str | Path = DEFAULT_DATABASE_PATH,
) -> None:
    """Replace the latest manual test results for one saved AI response."""
    allowed_statuses = {"passed", "failed", "timeout", "security_blocked", "execution_error"}
    initialize_database(database_path)
    with _database(database_path) as connection:
        exists = connection.execute(
            "SELECT 1 FROM ai_responses WHERE id = ?", (response_id,)
        ).fetchone()
        if exists is None:
            raise ValueError(f"AI response {response_id} does not exist.")
        connection.execute("DELETE FROM test_results WHERE response_id = ?", (response_id,))
        for result in results:
            status = str(result.get("status", "execution_error")).lower()
            if status not in allowed_statuses:
                raise ValueError(f"Unsupported test status: {status}")
        connection.executemany(
            """INSERT INTO test_results
               (response_id, test_name, inputs_json, status, expected_output, actual_output, error_message)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    response_id,
                    str(result.get("test_name", "")),
                    str(result.get("inputs_json", "")),
                    str(result.get("status", "execution_error")).lower(),
                    result.get("expected_output"),
                    result.get("actual_output"),
                    result.get("error_message"),
                )
                for result in results
            ],
        )


def get_test_results(
    response_id: int, database_path: str | Path = DEFAULT_DATABASE_PATH
) -> list[dict[str, Any]]:
    """Return saved test results for one AI response."""
    initialize_database(database_path)
    with _database(database_path) as connection:
        rows = connection.execute(
            """SELECT id, test_name, inputs_json, status, expected_output, actual_output, error_message
               FROM test_results WHERE response_id = ? ORDER BY id""",
            (response_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def save_evaluation_metrics(
    response_id: int,
    metrics: list[dict[str, Any]],
    database_path: str | Path = DEFAULT_DATABASE_PATH,
) -> None:
    """Replace the latest performance measurements for one AI response."""
    initialize_database(database_path)
    with _database(database_path) as connection:
        exists = connection.execute(
            "SELECT 1 FROM ai_responses WHERE id = ?", (response_id,)
        ).fetchone()
        if exists is None:
            raise ValueError(f"AI response {response_id} does not exist.")
        rows: list[tuple[Any, ...]] = []
        for metric in metrics:
            value = metric.get("metric_value")
            if value is not None:
                value = float(value)
                if value != value or value in {float("inf"), float("-inf")}:
                    raise ValueError("Metric values must be finite numbers or None.")
            rows.append(
                (
                    response_id,
                    str(metric["metric_name"]),
                    value,
                    str(metric.get("unit", "")),
                    str(metric.get("measurement_type", "")),
                )
            )
        metric_names = sorted({row[1] for row in rows})
        for metric_name in metric_names:
            connection.execute(
                "DELETE FROM evaluation_metrics WHERE response_id = ? AND metric_name = ?",
                (response_id, metric_name),
            )
        connection.executemany(
            """INSERT INTO evaluation_metrics
               (response_id, metric_name, metric_value, unit, measurement_type)
               VALUES (?, ?, ?, ?, ?)""",
            rows,
        )


def get_evaluation_metrics(
    response_id: int, database_path: str | Path = DEFAULT_DATABASE_PATH
) -> list[dict[str, Any]]:
    """Return the latest saved performance measurements for one response."""
    initialize_database(database_path)
    with _database(database_path) as connection:
        rows = connection.execute(
            """SELECT metric_name, metric_value, unit, measurement_type
               FROM evaluation_metrics WHERE response_id = ? ORDER BY id""",
            (response_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def save_claim_results(
    response_id: int,
    claims: list[dict[str, Any]],
    database_path: str | Path = DEFAULT_DATABASE_PATH,
) -> None:
    """Replace stored explanation claim and evidence verification results."""
    allowed_statuses = {
        "Supported",
        "Contradicted",
        "Insufficient evidence",
        "Not evaluated",
    }
    initialize_database(database_path)
    with _database(database_path) as connection:
        exists = connection.execute(
            "SELECT 1 FROM ai_responses WHERE id = ?", (response_id,)
        ).fetchone()
        if exists is None:
            raise ValueError(f"AI response {response_id} does not exist.")
        for claim in claims:
            if claim.get("status") not in allowed_statuses:
                raise ValueError(f"Unsupported claim status: {claim.get('status')}")
        connection.execute("DELETE FROM explanation_claims WHERE response_id = ?", (response_id,))
        connection.executemany(
            """INSERT INTO explanation_claims
               (response_id, claim_index, claim_text, status, reason, evidence_text,
                source, title, source_url, retrieval_score, evidence_chunk_id, retrieval_seconds,
                rule_result, ml_result, ml_confidence, verification_method, ml_review_required)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    response_id,
                    index,
                    str(claim.get("claim_text", "")),
                    str(claim.get("status", "Not evaluated")),
                    str(claim.get("reason", "")),
                    str(claim.get("evidence_text", "")),
                    str(claim.get("source", "")),
                    str(claim.get("title", "")),
                    str(claim.get("source_url", "")),
                    claim.get("retrieval_score"),
                    str(claim.get("evidence_chunk_id", "")),
                    claim.get("retrieval_seconds"),
                    str(claim.get("rule_result", claim.get("status", ""))),
                    claim.get("ml_result"),
                    claim.get("ml_confidence"),
                    str(claim.get("verification_method", "rule")),
                    int(bool(claim.get("ml_review_required", False))),
                )
                for index, claim in enumerate(claims, start=1)
            ],
        )


def get_claim_results(
    response_id: int, database_path: str | Path = DEFAULT_DATABASE_PATH
) -> list[dict[str, Any]]:
    """Return stored explanation claims and their evidence status."""
    initialize_database(database_path)
    with _database(database_path) as connection:
        rows = connection.execute(
            """SELECT claim_index, claim_text, status, reason, evidence_text,
                      source, title, source_url, retrieval_score, evidence_chunk_id, retrieval_seconds
                      , rule_result, ml_result, ml_confidence, verification_method, ml_review_required
               FROM explanation_claims WHERE response_id = ? ORDER BY claim_index""",
            (response_id,),
        ).fetchall()
    return [dict(row) for row in rows]
