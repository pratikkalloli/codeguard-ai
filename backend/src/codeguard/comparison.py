"""Helpers for grouping saved responses to the same coding prompt."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any


def group_evaluations_by_question(
    evaluations: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Group records using whitespace-insensitive, case-folded exact questions."""
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in evaluations:
        question = re.sub(r"\s+", " ", str(row.get("question_text", ""))).strip()
        if question:
            groups[question.casefold()].append(row)
    return {question: rows for question, rows in groups.items() if len(rows) > 1}
