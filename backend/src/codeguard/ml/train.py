"""Rebuild dataset, train fixed baselines, evaluate once, and save artifacts."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from codeguard.ml import MODEL_VERSION
from codeguard.ml.dataset import DEFAULT_ML_DIR, LABELS, RANDOM_SEED, analyze_dataset, build_dataset, load_records
from codeguard.ml.evaluate import evaluate_models
from codeguard.ml.models import DEFAULT_MODEL_PATH, SVM_MODEL_PATH, save_model


PROJECT_ROOT = Path(__file__).resolve().parents[4]
REPORTS_DIR = PROJECT_ROOT / "reports" / "pilot"


def derive_confidence_threshold(pipeline: Any, validation_records: list[dict[str, Any]]) -> dict[str, Any]:
    """Choose a reject threshold from validation mistakes, not from test data."""
    if not validation_records:
        return {"threshold": math.nextafter(1.0, math.inf), "method": "No validation rows: reject every ML prediction."}
    classifier = pipeline.named_steps["classifier"]
    if not hasattr(classifier, "predict_proba"):
        return {"threshold": None, "method": "Estimator has no predict_proba; confidence threshold unavailable."}
    predictions = [str(value) for value in pipeline.predict(validation_records)]
    confidence = np.max(pipeline.predict_proba(validation_records), axis=1)
    wrong = [float(confidence[i]) for i, row in enumerate(validation_records) if predictions[i] != row["label"]]
    correct = [float(confidence[i]) for i, row in enumerate(validation_records) if predictions[i] == row["label"]]
    if wrong:
        threshold = math.nextafter(max(wrong), math.inf)
        method = "Next representable confidence above the most confident validation error; prevents that observed error from being accepted. Tiny validation set makes this provisional."
    elif correct:
        threshold = min(correct)
        method = "Minimum confidence among validation predictions, all of which were correct. This is provisional due to the tiny validation set."
    else:
        threshold = math.nextafter(1.0, math.inf)
        method = "No correct validation predictions; threshold is above the possible probability range, so all predictions require review."
    return {
        "threshold": float(threshold), "method": method,
        "validation_count": len(validation_records),
        "validation_correct": len(correct), "validation_incorrect": len(wrong),
        "validation_predictions": [
            {"claim": row["claim"], "actual": row["label"], "predicted": predictions[i], "confidence": float(confidence[i])}
            for i, row in enumerate(validation_records)
        ],
    }


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")


def _save_confusion_matrix(metrics: dict[str, Any], destination: Path) -> None:
    matrix = np.asarray(metrics["confusion_matrix"], dtype=int)
    fig, axis = plt.subplots(figsize=(7.2, 5.8), constrained_layout=True)
    image = axis.imshow(matrix, interpolation="nearest", cmap="Blues")
    fig.colorbar(image, ax=axis, fraction=0.046, pad=0.04)
    axis.set(
        xticks=np.arange(len(LABELS)), yticks=np.arange(len(LABELS)),
        xticklabels=LABELS, yticklabels=LABELS,
        xlabel="Predicted label", ylabel="Actual label", title="Logistic Regression — held-out test set",
    )
    plt.setp(axis.get_xticklabels(), rotation=25, ha="right", rotation_mode="anchor")
    midpoint = matrix.max() / 2 if matrix.size else 0
    for row in range(matrix.shape[0]):
        for column in range(matrix.shape[1]):
            axis.text(column, row, str(matrix[row, column]), ha="center", va="center", color="white" if matrix[row, column] > midpoint else "black")
    destination.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destination, dpi=160)
    plt.close(fig)


def run_training(ml_dir: str | Path = DEFAULT_ML_DIR, reports_dir: str | Path = REPORTS_DIR, model_dir: str | Path | None = None) -> dict[str, Any]:
    ml_dir, reports_dir = Path(ml_dir), Path(reports_dir)
    model_dir = Path(model_dir) if model_dir else DEFAULT_MODEL_PATH.parent
    dataset_result = build_dataset(ml_dir)
    train_records = load_records(ml_dir / "train.csv")
    validation_records = load_records(ml_dir / "validation.csv")
    test_records = load_records(ml_dir / "test.csv")

    evaluation = evaluate_models(train_records, test_records, RANDOM_SEED)
    logistic_pipeline = evaluation["fitted_models"]["logistic_regression"]
    svm_pipeline = evaluation["fitted_models"]["linear_svm"]
    confidence_rule = derive_confidence_threshold(logistic_pipeline, validation_records)
    threshold = confidence_rule["threshold"]
    model_payload = {
        "version": MODEL_VERSION,
        "dataset_version": dataset_result["metadata"]["dataset_version"],
        "pipeline": logistic_pipeline,
        "classes": list(LABELS),
        "confidence_threshold": threshold,
        "confidence_method": "Maximum LogisticRegression class probability. It is uncalibrated and is not a probability that a claim is true.",
        "threshold_derivation": confidence_rule,
    }
    svm_payload = {
        "version": MODEL_VERSION,
        "dataset_version": dataset_result["metadata"]["dataset_version"],
        "pipeline": svm_pipeline,
        "classes": list(LABELS),
        "confidence_threshold": None,
        "confidence_method": "LinearSVC does not produce calibrated probabilities; confidence is unavailable.",
    }
    save_model(model_payload, model_dir / DEFAULT_MODEL_PATH.name)
    save_model(svm_payload, model_dir / SVM_MODEL_PATH.name)

    comparison = evaluation["comparison"]
    report = {
        "model_version": MODEL_VERSION,
        "dataset_version": dataset_result["metadata"]["dataset_version"],
        "dataset_size": len(dataset_result["records"]),
        "class_distribution": dataset_result["metadata"]["samples_per_class"],
        "data_origins": dataset_result["metadata"]["data_origins"],
        "split_samples": dataset_result["metadata"]["split_samples"],
        "split_class_distribution": dataset_result["metadata"]["split_class_distribution"],
        "random_seed": RANDOM_SEED,
        "test_metrics": {
            name: {key: value for key, value in result.items() if key != "cross_validation"}
            for name, result in comparison.items() if isinstance(result, dict) and "accuracy" in result
        },
        "cross_validation": {
            name: result.get("cross_validation", {"status": "not applicable"})
            for name, result in comparison.items() if isinstance(result, dict) and "accuracy" in result
        },
        "confidence_threshold": confidence_rule,
        "test_set_policy": comparison["test_set_policy"],
        "error_analysis": {
            name: {"errors": result.get("errors", []), "error_categories": result.get("error_categories", {})}
            for name, result in comparison.items() if isinstance(result, dict) and "accuracy" in result
        },
        "integrity_note": "All 15 data records are synthetic. Test metrics are computed on three held-out examples and are not estimates of real-world generalization.",
    }
    _write_json(reports_dir / "ml_metrics.json", report)
    dataset_analysis = dict(dataset_result["metadata"]["analysis"])
    dataset_analysis.update({
        "dataset_version": dataset_result["metadata"]["dataset_version"],
        "split_samples": dataset_result["metadata"]["split_samples"],
        "split_class_distribution": dataset_result["metadata"]["split_class_distribution"],
        "split_policy": dataset_result["metadata"]["split_strategy"],
    })
    _write_json(reports_dir / "ml_dataset_analysis.json", dataset_analysis)
    _save_confusion_matrix(comparison["logistic_regression_tfidf"], reports_dir / "confusion_matrix.png")

    fields = ["model", "accuracy", "precision", "recall", "f1_micro", "f1_macro", "f1_weighted", "test_samples"]
    with (reports_dir / "model_comparison.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for name, result in comparison.items():
            if isinstance(result, dict) and "accuracy" in result:
                writer.writerow({"model": name, **{field: result[field] for field in fields[1:-1]}, "test_samples": result["sample_count"]})
    return {"dataset": dataset_result, "comparison": comparison, "report": report, "artifact": model_payload}


if __name__ == "__main__":
    result = run_training()
    print(json.dumps({
        "dataset_size": result["report"]["dataset_size"],
        "class_distribution": result["report"]["class_distribution"],
        "test_metrics": {name: values["accuracy"] for name, values in result["report"]["test_metrics"].items()},
        "confidence_threshold": result["report"]["confidence_threshold"],
    }, indent=2))
