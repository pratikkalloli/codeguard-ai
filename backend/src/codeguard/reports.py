"""Transparent, exportable evaluation report assembly without an overall score."""

from __future__ import annotations

from collections import Counter
import math
from numbers import Real
from typing import Any

from codeguard.validation import validate_python


REPORT_LIMITATIONS = [
    "Static checks report syntax and selected patterns; they do not prove program correctness or safety.",
    "Submitted code execution uses local Docker restrictions, which are not a production-grade security guarantee.",
    "Python process timing includes interpreter startup and shutdown; it is not a pure algorithm benchmark.",
    "Cgroup memory, when available, is whole-container peak memory and includes the Python runtime and sandbox overhead.",
    "Explanation verification uses a small curated Python documentation corpus and explicit rules; it can miss claims and is not a guarantee of factual correctness.",
    "Insufficient evidence means the current corpus or rules did not establish a result; it does not mean the claim is false.",
]


def build_reliability_report(
    evaluation: dict[str, Any],
    test_results: list[dict[str, Any]],
    metrics: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    *,
    ml_reliability: dict[str, Any] | None = None,
    docker_execution: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a unified report whose deterministic, runtime, evidence, and ML signals stay separate."""
    code_blocks = []
    for block in evaluation.get("code_blocks", []):
        validation = validate_python(block["code_text"])
        code_blocks.append(
            {
                "block_index": block["block_index"],
                "code": block["code_text"],
                "static_status": validation.status,
                "static_message": validation.message,
                "findings": [finding.message for finding in validation.findings],
            }
        )
    passed = sum(row.get("status") == "passed" for row in test_results)
    ml_signal = _ml_reliability_signal(ml_reliability)
    static_signal = {"available": bool(code_blocks), "code_blocks": code_blocks}
    docker_signal = _docker_execution_signal(docker_execution)
    function_signal = {
        "available": bool(test_results),
        "execution_environment": "restricted Docker containers",
        "total": len(test_results),
        "passed": passed,
        "failed_or_other": len(test_results) - passed,
        "results": test_results,
    }
    evidence_signal = [
        {
            "claim_text": row.get("claim_text", ""),
            "evidence_text": row.get("evidence_text", ""),
            "source": row.get("source", ""),
            "title": row.get("title", ""),
            "source_url": row.get("source_url", ""),
            "retrieval_score": row.get("retrieval_score"),
            "evidence_chunk_id": row.get("evidence_chunk_id", ""),
        }
        for row in claims
    ]
    claim_signal = {
        "total": len(claims),
        "status_counts": dict(Counter(row.get("status", "Unknown") for row in claims)),
        "results": claims,
    }
    signals = {
        "static_ast_analysis": static_signal,
        "docker_execution": docker_signal,
        "function_tests": function_signal,
        "performance_measurement": {"available": bool(metrics), "measurements": metrics},
        "explanation_claims": {"available": bool(claims), "claims": claims},
        "evidence_retrieval": {"available": any(item["evidence_text"] or item["source_url"] for item in evidence_signal), "claims": evidence_signal},
        "claim_verification": claim_signal,
        "ml_reliability": ml_signal,
    }
    return {
        "report_version": 2,
        "evaluation": {
            "id": evaluation["id"],
            "created_at_utc": evaluation["created_at"],
            "question": evaluation["question_text"],
            "model_or_source": evaluation["model_name"],
        },
        "code_blocks": code_blocks,
        "test_results": test_results,
        "test_summary": {
            "total": len(test_results),
            "passed": passed,
            "failed_or_other": len(test_results) - passed,
            "pass_percentage": (round(100 * passed / len(test_results), 2) if test_results else None),
        },
        "performance_measurements": metrics,
        "explanation": {
            "text": evaluation.get("explanation_text", ""),
            "claims": claims,
            "status_counts": dict(Counter(row.get("status", "Unknown") for row in claims)),
        },
        "ml_reliability": ml_signal,
        "signals": signals,
        "limitations": REPORT_LIMITATIONS,
        "summary_note": "This report presents independent observations. The ML reliability signal is a dataset-domain prediction and is not combined with CodeGuard verification into an overall score.",
    }


def _ml_reliability_signal(value: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize inference output for JSON reports without inventing missing values."""
    unavailable: dict[str, Any] = {
        "available": False,
        "model": None,
        "model_version": None,
        "task": "pass_rate_prediction",
        "task_description": "Predicted execution pass-rate reliability from the Phase 17 source-recorded pass-rate model.",
        "dataset_name": None,
        "dataset_size": {},
        "prediction": None,
        "prediction_range": [0.0, 1.0],
        "confidence": None,
        "confidence_note": "No calibrated confidence or uncertainty estimate is available.",
        "feature_fields": [],
        "feature_summary": {},
        "model_metadata": {},
        "limitations": [],
        "reason": "ML inference was not run for this report.",
    }
    if not isinstance(value, dict):
        return unavailable
    prediction = value.get("prediction")
    valid_number = isinstance(prediction, Real) and not isinstance(prediction, bool)
    if valid_number:
        prediction = float(prediction)
        valid_number = math.isfinite(prediction) and 0.0 <= prediction <= 1.0
    available = value.get("status") == "predicted" and valid_number
    result = {
        **unavailable,
        "available": bool(available),
        "model": value.get("model"),
        "model_version": value.get("model_version"),
        "task": value.get("task", "pass_rate_prediction"),
        "task_description": value.get("task_description", unavailable["task_description"]),
        "dataset_name": value.get("dataset_name"),
        "dataset_size": value.get("dataset_size") if isinstance(value.get("dataset_size"), dict) else {},
        "prediction": prediction if available else None,
        "prediction_range": value.get("prediction_range", [0.0, 1.0]),
        "confidence": value.get("confidence"),
        "confidence_note": value.get("confidence_note", unavailable["confidence_note"]),
        "feature_fields": value.get("feature_fields", []),
        "feature_summary": value.get("feature_summary", {}),
        "model_metadata": value.get("model_metadata", {}),
        "code_block_index": value.get("code_block_index"),
        "limitations": value.get("limitations", []),
        "reason": value.get("reason"),
    }
    if not result["available"] and not result["reason"]:
        result["reason"] = "ML prediction is unavailable or outside the declared range [0, 1]."
    return result


def _docker_execution_signal(value: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {
            "available": False,
            "status": "not_recorded",
            "reason": "No separate isolated-run result was saved with this evaluation. Function tests are reported independently.",
        }
    return {"available": True, **value}
