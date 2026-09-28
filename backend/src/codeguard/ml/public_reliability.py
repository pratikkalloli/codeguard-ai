"""Inference adapter for the Phase 17 execution-pass-rate auxiliary model."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


TASK_DESCRIPTION = (
    "Predict source-recorded execution test pass rate for competitive-programming Python solutions. "
    "This is not a general code-correctness or explanation-verification score."
)


def _phase17_metadata(project_root: Path, artifact: dict[str, Any]) -> dict[str, Any]:
    """Read the training run's saved metadata; tolerate absent optional files."""
    result: dict[str, Any] = {
        "dataset_name": "NVIDIA OpenCodeReasoning-2 Python split (bounded three-shard prefix)",
        "dataset_size": {},
        "model_metadata": {
            "seed": artifact.get("seed"),
            "artifact_task": artifact.get("task"),
            "target": artifact.get("target"),
        },
    }
    try:
        dataset = json.loads((project_root / "data" / "raw" / "phase17" / "DATASET_METADATA.json").read_text(encoding="utf-8"))
        result["dataset_name"] = dataset.get("dataset_name", result["dataset_name"])
        result["dataset_size"] = {
            "downloaded_records": dataset.get("record_count"),
            "usable_records": dataset.get("usable_record_count"),
            "reported_full_python_records": dataset.get("reported_full_python_record_count"),
        }
    except (OSError, ValueError, TypeError):
        pass
    try:
        config = json.loads((project_root / "models" / "phase17" / "training_config.json").read_text(encoding="utf-8"))
        selected_name = str(artifact.get("model_name", ""))
        result["model_metadata"] = {
            "seed": artifact.get("seed", config.get("seed")),
            "artifact_task": artifact.get("task"),
            "target": artifact.get("target"),
            "parameters": config.get("models", {}).get(selected_name, {}),
        }
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return result


def _unavailable(reason: str) -> dict[str, Any]:
    return {
        "status": "not_available",
        "task": "pass_rate_prediction",
        "task_description": TASK_DESCRIPTION,
        "prediction_range": [0.0, 1.0],
        "confidence": None,
        "confidence_note": "No calibrated confidence or uncertainty estimate is available.",
        "reason": reason,
        "limitations": [
            "This model does not predict general code correctness, factual correctness, or explanation correctness.",
            "This signal is not a Supported/Contradicted/Insufficient Evidence result or a human-verified label.",
        ],
    }


def predict_pass_rate(
    code: str,
    explanation: str = "",
    metadata: dict[str, Any] | None = None,
    model_path: str | Path | None = None,
) -> dict[str, Any]:
    """Return an auxiliary benchmark pass-rate estimate without executing code.

    ``explanation`` is accepted for a uniform app API but intentionally unused:
    the public training corpus has no aligned nonblank question text in this
    release, and rationale/critique inputs would leak generated judgements.
    """
    del explanation
    if not isinstance(code, str) or not code.strip():
        return _unavailable("A non-empty Python code string is required for prediction.")
    try:
        path = Path(model_path) if model_path else Path(__file__).resolve().parents[4] / "models" / "phase17" / "pass_rate_predictor.joblib"
        artifact_exists = path.is_file()
    except (OSError, TypeError, ValueError) as error:
        return _unavailable(f"Phase 17 model path is invalid or inaccessible: {type(error).__name__}: {error}")
    if not artifact_exists:
        return _unavailable("Phase 17 model artifact is not installed.")
    try:
        import joblib
        import pandas as pd

        from codeguard.ml.phase17_public_data import code_features

        artifact = joblib.load(path)
        if not isinstance(artifact, dict) or not callable(getattr(artifact.get("model"), "predict", None)):
            return _unavailable("Phase 17 model artifact has an unsupported format.")
        fields = {key: str((metadata or {}).get(key) or "unknown") for key in ("source", "dataset", "difficulty")}
        row = {"code": code, **fields, **code_features(code)}
        predicted_values = artifact["model"].predict(pd.DataFrame([row]))
        if len(predicted_values) != 1:
            return _unavailable("Phase 17 model returned an unexpected number of predictions.")
        prediction = float(predicted_values[0])
        if not math.isfinite(prediction):
            return _unavailable("Phase 17 model returned a non-finite prediction.")
        prediction = min(1.0, max(0.0, prediction))
    except Exception as error:
        return _unavailable(f"Phase 17 prediction failed: {type(error).__name__}: {error}")

    project_root = Path(__file__).resolve().parents[4]
    metadata_fields = _phase17_metadata(project_root, artifact)
    try:
        feature_config = json.loads((project_root / "models" / "phase17" / "feature_config.json").read_text(encoding="utf-8"))
        features = feature_config.get("numeric_fields", []) + feature_config.get("categorical_fields", [])
    except (OSError, ValueError, TypeError):
        features = []
    return {
        "status": "predicted",
        "task": "pass_rate_prediction",
        "task_description": TASK_DESCRIPTION,
        "prediction_range": [0.0, 1.0],
        "prediction": prediction,
        "confidence": None,
        "confidence_note": "Regression output; no calibrated confidence or uncertainty interval is available.",
        "model": artifact.get("model_name", "phase17_pass_rate_predictor"),
        "model_version": artifact.get("revision", "unknown"),
        **metadata_fields,
        "feature_fields": features,
        "feature_summary": {key: row[key] for key in ("code_chars", "code_lines", "syntax_valid", "ast_nodes", "functions", "imports", "loops", "branches")},
        "limitations": [
            "This auxiliary signal estimates dataset-domain source-recorded pass rate; it is not general code correctness, factual correctness, or explanation verification.",
            "The training release does not provide problem text in this split.",
            "This prediction does not execute or prove code correctness and is not a human-verified CodeGuard label.",
        ],
    }
