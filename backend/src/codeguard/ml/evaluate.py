"""Unseen-test evaluation, train-only cross-validation, and error analysis."""

from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
)
from sklearn.model_selection import StratifiedGroupKFold, cross_validate

from codeguard.ml.dataset import LABELS
from codeguard.ml.models import build_majority_baseline, build_model, majority_predict


def evaluate_predictions(records: list[dict[str, Any]], predictions: list[str], confidences: list[float | None] | None = None) -> dict[str, Any]:
    if len(records) != len(predictions):
        raise ValueError("Prediction count must match the record count.")
    actual = [row["label"] for row in records]
    precision, recall, f1, support = precision_recall_fscore_support(
        actual, predictions, labels=list(LABELS), zero_division=0
    )
    errors = []
    categories: Counter[str] = Counter()
    confidences = confidences or [None] * len(records)
    for record, predicted, confidence in zip(records, predictions, confidences):
        if record["label"] != predicted:
            categories[f"{record['label']} → {predicted}"] += 1
            errors.append({
                "claim": record["claim"], "evidence": record["evidence"],
                "actual_label": record["label"], "predicted_label": predicted,
                "confidence": confidence,
            })
    precision_macro = float(np.mean(precision)) if len(precision) else None
    recall_macro = float(np.mean(recall)) if len(recall) else None
    f1_macro = float(np.mean(f1)) if len(f1) else None
    f1_micro = float(f1_score(actual, predictions, labels=list(LABELS), average="micro", zero_division=0)) if actual else None
    return {
        "sample_count": len(records),
        "accuracy": float(accuracy_score(actual, predictions)) if actual else None,
        "precision": precision_macro,
        "recall": recall_macro,
        "f1": f1_micro,
        "precision_macro": precision_macro,
        "recall_macro": recall_macro,
        "f1_macro": f1_macro,
        "f1_micro": f1_micro,
        "f1_weighted": float(f1_score(actual, predictions, labels=list(LABELS), average="weighted", zero_division=0)) if actual else None,
        "per_class": {
            label: {"precision": float(precision[index]), "recall": float(recall[index]), "f1": float(f1[index]), "support": int(support[index])}
            for index, label in enumerate(LABELS)
        },
        "classification_report": classification_report(
            actual, predictions, labels=list(LABELS), target_names=list(LABELS), output_dict=True, zero_division=0
        ) if actual else {},
        "confusion_matrix": confusion_matrix(actual, predictions, labels=list(LABELS)).tolist(),
        "errors": errors,
        "error_categories": dict(categories),
    }


def stratified_train_cross_validation(train_records: list[dict[str, Any]], model_name: str, random_seed: int = 42) -> dict[str, Any]:
    labels = [row["label"] for row in train_records]
    counts = Counter(labels)
    group_counts = {
        label: len({row["leakage_group"] for row in train_records if row["label"] == label})
        for label in counts
    }
    n_splits = min(group_counts.values(), default=0)
    if n_splits < 2:
        return {"status": "unavailable", "reason": "At least two training examples per class are required."}
    cv = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=random_seed)
    scores = cross_validate(
        build_model(model_name, random_seed), train_records, labels, cv=cv,
        groups=[row["leakage_group"] for row in train_records],
        scoring={"accuracy": "accuracy", "macro_f1": "f1_macro"},
        return_train_score=False, error_score="raise",
    )
    return {
        "status": "computed on training partition only",
        "strategy": "StratifiedGroupKFold; proposition/near-duplicate groups stay within one fold",
        "folds": n_splits,
        "mean_accuracy": float(np.mean(scores["test_accuracy"])),
        "accuracy_std": float(np.std(scores["test_accuracy"], ddof=0)),
        "mean_macro_f1": float(np.mean(scores["test_macro_f1"])),
        "macro_f1_std": float(np.std(scores["test_macro_f1"], ddof=0)),
        "fold_accuracy": [float(value) for value in scores["test_accuracy"]],
        "fold_macro_f1": [float(value) for value in scores["test_macro_f1"]],
    }


def evaluate_models(train_records: list[dict[str, Any]], test_records: list[dict[str, Any]], random_seed: int = 42) -> dict[str, Any]:
    """Fit fixed model configurations on train, evaluate once on unseen test."""
    if not train_records or not test_records:
        raise ValueError("Training and test partitions must both contain records.")
    train_labels = [record["label"] for record in train_records]
    comparison: dict[str, Any] = {
        "majority_baseline": evaluate_predictions(
            test_records, majority_predict(train_labels, test_records)
        ),
        "logistic_regression_tfidf": {},
        "linear_svm_tfidf": {},
    }
    fitted_models = {}
    for model_name, result_key in (("logistic_regression", "logistic_regression_tfidf"), ("linear_svm", "linear_svm_tfidf")):
        pipeline = build_model(model_name, random_seed)
        pipeline.fit(train_records, train_labels)
        predictions = [str(value) for value in pipeline.predict(test_records)]
        classifier = pipeline.named_steps["classifier"]
        confidences = [float(value) for value in np.max(pipeline.predict_proba(test_records), axis=1)] if hasattr(classifier, "predict_proba") else [None] * len(test_records)
        comparison[result_key] = evaluate_predictions(test_records, predictions, confidences)
        comparison[result_key]["cross_validation"] = stratified_train_cross_validation(train_records, model_name, random_seed)
        fitted_models[model_name] = pipeline
    comparison["test_set_policy"] = "The test set was not used for model or threshold selection."
    return {"comparison": comparison, "fitted_models": fitted_models}


def classification_metrics(y_true: list[str], y_pred: list[str]) -> dict[str, Any]:
    """Convenience public metric function for tests and external callers."""
    records = [{"label": actual, "claim": "", "evidence": ""} for actual in y_true]
    return evaluate_predictions(records, y_pred)
