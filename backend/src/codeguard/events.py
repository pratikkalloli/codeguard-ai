"""Structured, bounded evaluation/application events with secret redaction."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from typing import Any

from codeguard.auth import DEVELOPER, require_role
from codeguard.storage import DEFAULT_DATABASE_PATH, _database, initialize_database

MAX_LOG_ROWS = 5000
MAX_DETAILS_CHARS = 4000
_SENSITIVE_KEY = re.compile(r"password|secret|api.?key|token|authorization|credential", re.I)
_SECRET_TEXT = re.compile(
    r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+|((?:sk|key|token)[-_])[A-Za-z0-9_-]{12,}"
)


def _redact(value: Any, key: str = "") -> Any:
    if _SENSITIVE_KEY.search(key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k)[:80]: _redact(v, str(k)) for k, v in list(value.items())[:40]}
    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value[:40]]
    if isinstance(value, str):
        return _SECRET_TEXT.sub(lambda match: (match.group(1) or "") + "[REDACTED]", value[:1000])
    if value is None or isinstance(value, (int, float, bool)):
        return value
    return str(value)[:100]


def log_event(
    event: str,
    *,
    user_id: int | None = None,
    evaluation_id: int | str | None = None,
    level: str = "INFO",
    component: str = "application",
    duration_ms: float | None = None,
    status: str = "",
    error_type: str = "",
    details: dict[str, Any] | None = None,
    database_path=DEFAULT_DATABASE_PATH,
) -> int:
    initialize_database(database_path)
    event_name = re.sub(r"[^A-Z0-9_]", "_", str(event).upper())[:100]
    level_name = str(level).upper()
    if level_name not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        level_name = "INFO"
    if isinstance(evaluation_id, int):
        eval_key = f"EVL-{evaluation_id:07d}"
    else:
        eval_key = str(evaluation_id or "")[:80]
    clean_details = _redact(details or {})
    details_json = json.dumps(clean_details, ensure_ascii=False, separators=(",", ":"))[:MAX_DETAILS_CHARS]
    with _database(database_path) as connection:
        cursor = connection.execute(
            """INSERT INTO application_logs
               (timestamp,event,level,evaluation_id,user_id,component,duration_ms,status,error_type,details_json)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                event_name,
                level_name,
                eval_key,
                int(user_id) if user_id is not None else None,
                str(component)[:80],
                float(duration_ms) if duration_ms is not None else None,
                str(status)[:80],
                str(error_type)[:120],
                details_json,
            ),
        )
        connection.execute(
            "DELETE FROM application_logs WHERE id NOT IN (SELECT id FROM application_logs ORDER BY id DESC LIMIT ?)",
            (MAX_LOG_ROWS,),
        )
        return int(cursor.lastrowid)


def list_events(
    actor_user_id: int,
    *,
    limit: int = 200,
    search: str = "",
    level: str = "All",
    event: str = "All",
    evaluation_id: str = "",
    errors_only: bool = False,
    start_date: str = "",
    end_date: str = "",
    database_path=DEFAULT_DATABASE_PATH,
) -> list[dict[str, Any]]:
    require_role(actor_user_id, DEVELOPER, database_path)
    initialize_database(database_path)
    query = """SELECT l.id,l.timestamp,l.event,l.level,l.evaluation_id,l.user_id,l.component,
                      l.duration_ms,l.status,l.error_type,l.details_json,
                      u.username AS actor FROM application_logs l
               LEFT JOIN users u ON u.id=l.user_id"""
    conditions: list[str] = []
    parameters: list[Any] = []
    if search.strip():
        term = f"%{search.strip()[:200]}%"
        conditions.append("(l.event LIKE ? OR l.evaluation_id LIKE ? OR l.component LIKE ? OR l.error_type LIKE ?)")
        parameters.extend((term, term, term, term))
    if level != "All":
        conditions.append("l.level = ?")
        parameters.append(level.upper())
    if event != "All":
        conditions.append("l.event = ?")
        parameters.append(event.upper())
    if evaluation_id.strip():
        conditions.append("l.evaluation_id LIKE ?")
        parameters.append(f"%{evaluation_id.strip()[:80]}%")
    if errors_only:
        conditions.append("l.level IN ('ERROR','CRITICAL')")
    if start_date:
        conditions.append("substr(l.timestamp,1,10) >= ?")
        parameters.append(start_date)
    if end_date:
        conditions.append("substr(l.timestamp,1,10) <= ?")
        parameters.append(end_date)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY l.id DESC LIMIT ?"
    parameters.append(max(1, min(int(limit), MAX_LOG_ROWS)))
    with _database(database_path) as connection:
        rows = connection.execute(query, parameters).fetchall()
    results = []
    for row in rows:
        item = dict(row)
        item["details"] = json.loads(item.pop("details_json") or "{}")
        results.append(item)
    return results
