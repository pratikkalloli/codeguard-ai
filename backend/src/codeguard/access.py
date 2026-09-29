"""Role-checked access to saved evaluation data."""

from __future__ import annotations

from typing import Any

from codeguard.auth import DEVELOPER, USER, require_role
from codeguard.storage import (
    DEFAULT_DATABASE_PATH,
    get_evaluation,
    get_reliability_report,
    list_evaluations,
)


def list_accessible_evaluations(
    actor_user_id: int,
    *,
    limit: int = 100,
    search: str = "",
    offset: int = 0,
    database_path=DEFAULT_DATABASE_PATH,
) -> list[dict[str, Any]]:
    actor = require_role(actor_user_id, {USER, DEVELOPER}, database_path)
    if actor["role"] == DEVELOPER:
        return list_evaluations(limit, database_path, include_all=True, search=search, offset=offset)
    return list_evaluations(
        limit, database_path, owner_user_id=actor["id"], search=search, offset=offset
    )


def get_accessible_evaluation(
    actor_user_id: int,
    evaluation_id: int,
    *,
    database_path=DEFAULT_DATABASE_PATH,
) -> dict[str, Any] | None:
    actor = require_role(actor_user_id, {USER, DEVELOPER}, database_path)
    if actor["role"] == DEVELOPER:
        return get_evaluation(evaluation_id, database_path, include_all=True)
    return get_evaluation(evaluation_id, database_path, owner_user_id=actor["id"])


def get_accessible_report(
    actor_user_id: int,
    evaluation_id: int,
    *,
    database_path=DEFAULT_DATABASE_PATH,
) -> dict[str, Any] | None:
    actor = require_role(actor_user_id, {USER, DEVELOPER}, database_path)
    if actor["role"] == DEVELOPER:
        return get_reliability_report(evaluation_id, database_path, include_all=True)
    return get_reliability_report(evaluation_id, database_path, owner_user_id=actor["id"])
