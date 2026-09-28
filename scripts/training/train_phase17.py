"""Reproduce Phase 17 preprocessing, grouped splitting, baselines and reports."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


import joblib
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import (
    accuracy_score, average_precision_score, confusion_matrix, f1_score,
    mean_absolute_error, mean_squared_error, precision_score, recall_score,
    r2_score, roc_auc_score,
)
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.svm import LinearSVR
from sklearn.linear_model import Ridge

from codeguard.ml.phase17_public_data import REVISION, code_features, iter_raw_rows, preprocess

SEED = 1701
TARGET = "pass_rate"
NUMERIC = [
    "code_chars", "code_lines", "dangerous_api_mentions", "syntax_valid", "ast_nodes",
    "functions", "classes", "imports", "loops", "branches", "try_blocks", "comprehensions",
]
CATEGORICAL = ["source", "dataset", "difficulty"]


def union_find_groups(records: list[dict]) -> list[str]:
    """Connect rows sharing a task ID or exact normalized code hash."""
    parent = list(range(len(records)))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    seen: dict[tuple[str, str], int] = {}
    for i, row in enumerate(records):
        for key in (("question", row["question_id"]), ("code", row["code_sha256"])):
            if key in seen:
                union(i, seen[key])
            else:
                seen[key] = i
    roots = [find(i) for i in range(len(records))]
    return [str(root) for root in roots]


def make_splits(records: list[dict]) -> dict[str, list[dict]]:
    groups = np.asarray(union_find_groups(records))
    row_indices = np.arange(len(records))
    first = GroupShuffleSplit(n_splits=1, test_size=0.15, random_state=SEED)
    trainval_idx, test_idx = next(first.split(row_indices, groups=groups))
    second = GroupShuffleSplit(n_splits=1, test_size=(0.15 / 0.85), random_state=SEED + 1)
    train_rel, val_rel = next(second.split(trainval_idx, groups=groups[trainval_idx]))
    train_idx, val_idx = trainval_idx[train_rel], trainval_idx[val_rel]
    return {name: [records[int(i)] for i in idx] for name, idx in {
        "train": train_idx, "validation": val_idx, "test": test_idx,
    }.items()}


def frame(records: list[dict]) -> pd.DataFrame:
    rows = []
    for row in records:
        item = {key: row.get(key, "") for key in CATEGORICAL}
        item["code"] = row["code"]
        item[TARGET] = float(row[TARGET])
        item.update(row["features"])
        rows.append(item)
    return pd.DataFrame(rows)


def feature_transformer() -> ColumnTransformer:
    return ColumnTransformer([
        ("code_tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=50000, sublinear_tf=True), "code"),
        ("metadata", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
        ("code_shape", StandardScaler(with_mean=False), NUMERIC),
    ], sparse_threshold=1.0)


def metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    corr = spearmanr(y_true, y_pred).statistic if len(np.unique(y_true)) > 1 and len(np.unique(y_pred)) > 1 else None
    observed_binary = (y_true >= 0.5).astype(int)
    predicted_binary = (y_pred >= 0.5).astype(int)
    result = {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "r2": float(r2_score(y_true, y_pred)),
        "spearman_rho": float(corr) if corr is not None and np.isfinite(corr) else None,
        "derived_binary_target": "pass_rate >= 0.5 (analysis threshold; not an original dataset label)",
        "accuracy": float(accuracy_score(observed_binary, predicted_binary)),
        "precision": float(precision_score(observed_binary, predicted_binary, zero_division=0)),
        "recall": float(recall_score(observed_binary, predicted_binary, zero_division=0)),
        "f1": float(f1_score(observed_binary, predicted_binary, zero_division=0)),
        "macro_f1": float(f1_score(observed_binary, predicted_binary, average="macro", zero_division=0)),
        "weighted_f1": float(f1_score(observed_binary, predicted_binary, average="weighted", zero_division=0)),
        "confusion_matrix_labels_0_1": confusion_matrix(observed_binary, predicted_binary, labels=[0, 1]).tolist(),
        "roc_auc": float(roc_auc_score(observed_binary, y_pred)) if len(np.unique(observed_binary)) == 2 else None,
        "pr_auc": float(average_precision_score(observed_binary, y_pred)) if len(np.unique(observed_binary)) == 2 else None,
    }
    return result


def main() -> None:
    raw_root = ROOT / "data" / "raw" / "phase17" / "opencodereasoning2"
    processed = ROOT / "data" / "processed" / "phase17_records.jsonl"
    stats_json = ROOT / "reports" / "phase17" / "phase17_dataset_statistics.json"
    sample = ROOT / "reports" / "phase17" / "phase17_dataset_sample.json"
    prep_json = ROOT / "reports" / "phase17" / "phase17_preprocessing_report.json"
    prep_md = ROOT / "docs" / "research" / "phase17" / "phase17_preprocessing_report.md"
    report = preprocess(raw_root, processed, prep_json, sample)
    records = [json.loads(line) for line in processed.read_text(encoding="utf-8").splitlines() if line]
    if len(records) < 100:
        raise RuntimeError(f"Only {len(records)} usable examples; refusing to train a misleading model")

    splits = make_splits(records)
    split_dir = ROOT / "data" / "splits" / "phase17"
    split_dir.mkdir(parents=True, exist_ok=True)
    for name, rows in splits.items():
        (split_dir / f"{name}.jsonl").write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")
    question_groups = {name: {row["question_id"] for row in rows} for name, rows in splits.items()}
    code_groups = {name: {row["code_sha256"] for row in rows} for name, rows in splits.items()}
    overlap = {"question_id": {}, "normalized_code_sha256": {}}
    for i, left in enumerate(("train", "validation", "test")):
        for right in ("train", "validation", "test")[i + 1:]:
            overlap["question_id"][f"{left}:{right}"] = len(question_groups[left] & question_groups[right])
            overlap["normalized_code_sha256"][f"{left}:{right}"] = len(code_groups[left] & code_groups[right])
    if any(value for family in overlap.values() for value in family.values()):
        raise RuntimeError(f"Leakage audit failed: {overlap}")
    split_report = {
        "seed": SEED, "strategy": "70/15/15 two-stage GroupShuffleSplit over connected components of question_id and normalized exact code SHA-256",
        "counts": {name: len(rows) for name, rows in splits.items()},
        "group_counts": {name: len(question_groups[name]) for name in splits},
        "overlaps": overlap,
        "near_duplicate_policy": "Exact normalized code and question groups are held together. Semantic near-duplicate analysis is not claimed.",
    }
    (ROOT / "reports" / "phase17" / "phase17_split_report.json").write_text(json.dumps(split_report, indent=2) + "\n", encoding="utf-8")

    train_df, val_df, test_df = (frame(splits[key]) for key in ("train", "validation", "test"))
    feature_cols = ["code", *CATEGORICAL, *NUMERIC]
    y_train, y_val, y_test = (df[TARGET].to_numpy(dtype=float) for df in (train_df, val_df, test_df))
    models = {
        "dummy_mean": ("all", DummyRegressor(strategy="mean")),
        "ridge_a1": ("all", Ridge(alpha=1.0)),
        "linear_svr_c0_1": ("all", LinearSVR(C=0.1, random_state=SEED, max_iter=5000, dual="auto")),
        "extra_trees_numeric": ("numeric", ExtraTreesRegressor(n_estimators=120, min_samples_leaf=3, max_features=0.8, n_jobs=1, random_state=SEED)),
    }
    results = {}
    artifacts = {}
    for name, (kind, estimator) in models.items():
        if kind == "all":
            pipeline = Pipeline([("features", feature_transformer()), ("model", estimator)])
            X_train, X_val, X_test = train_df[feature_cols], val_df[feature_cols], test_df[feature_cols]
        else:
            pipeline = estimator
            X_train, X_val, X_test = train_df[NUMERIC], val_df[NUMERIC], test_df[NUMERIC]
        pipeline.fit(X_train, y_train)
        val_pred = np.clip(pipeline.predict(X_val), 0.0, 1.0)
        test_pred = np.clip(pipeline.predict(X_test), 0.0, 1.0)
        results[name] = {"validation": metrics(y_val, val_pred), "test": metrics(y_test, test_pred)}
        artifacts[name] = pipeline
        if name == "linear_svr_c0_1":
            prediction = test_pred
            validation_prediction = val_pred
    selected = min(results, key=lambda name: results[name]["validation"]["mae"])
    selected_pipeline = artifacts[selected]
    if selected == "linear_svr_c0_1":
        test_prediction = prediction
    else:
        model_kind = models[selected][0]
        selected_test_df = test_df[feature_cols] if model_kind == "all" else test_df[NUMERIC]
        test_prediction = np.clip(selected_pipeline.predict(selected_test_df), 0.0, 1.0)

    model_dir = ROOT / "models" / "phase17"
    model_dir.mkdir(parents=True, exist_ok=True)
    model_file = model_dir / "pass_rate_predictor.joblib"
    joblib.dump({"model": selected_pipeline, "model_name": selected, "task": "execution_pass_rate_regression", "target": TARGET, "revision": REVISION, "seed": SEED}, model_file)
    (model_dir / "feature_config.json").write_text(json.dumps({
        "text_vectorizer": {"field": "code", "analyzer": "word", "ngram_range": [1, 2], "min_df": 2, "max_features": 50000, "sublinear_tf": True},
        "categorical_fields": CATEGORICAL,
        "numeric_fields": NUMERIC,
        "excluded_fields": ["pass_rate", "judgement", "qwq_critique", "r1_generation", "question"],
    }, indent=2) + "\n", encoding="utf-8")
    (model_dir / "target_definition.json").write_text(json.dumps({
        "target": "pass_rate", "type": "regression", "range": [0.0, 1.0],
        "source": "NVIDIA OpenCodeReasoning-2 upstream field; source pass-rate derived from provided execution/test process",
        "binary_reporting_threshold": 0.5,
        "binary_threshold_is_original_label": False,
        "codeguard_label_mapping": None,
    }, indent=2) + "\n", encoding="utf-8")
    (model_dir / "training_config.json").write_text(json.dumps({
        "seed": SEED, "split": split_report["strategy"], "model_selection": "Lowest validation MAE",
        "models": {"dummy_mean": {}, "ridge_a1": {"alpha": 1.0},
                   "linear_svr_c0_1": {"C": 0.1, "max_iter": 5000, "dual": "auto"},
                   "extra_trees_numeric": {"n_estimators": 120, "min_samples_leaf": 3, "max_features": 0.8, "n_jobs": 1}},
        "dataset_revision": REVISION,
    }, indent=2) + "\n", encoding="utf-8")
    results_doc = {
        "dataset": "NVIDIA OpenCodeReasoning-2 Python split (three-shard prefix)", "revision": REVISION,
        "task": "Regression for source-recorded pass_rate; auxiliary only, not CodeGuard labels or human review",
        "target_range": [0.0, 1.0], "seed": SEED, "split_counts": split_report["counts"],
        "selected_model_by_validation_mae": selected, "models": results,
        "test_prediction_summary": {"mean": float(test_prediction.mean()), "std": float(test_prediction.std())},
        "feature_policy": {"include": ["solution TF-IDF", "AST/code-shape metrics", "source/dataset/difficulty metadata"], "exclude": ["pass_rate input", "QwQ critique", "generated right/wrong judgement", "R1 rationale", "problem text (blank in release)"]},
        "limitations": ["Dataset labels and solutions are generated/automated, not human-reviewed.", "The release's question field is blank; this model uses solution code and metadata only.", "Upstream execution pass_rate may be unavailable or noisy.", "No CodeGuard Supported/Contradicted/Insufficient Evidence labels are learned.", "Generalization beyond competitive-programming source distributions is unverified."],
        "model_file": str(model_file.relative_to(ROOT)), "preprocessing_report": str(prep_json.relative_to(ROOT)),
    }
    result_json = ROOT / "reports" / "phase17" / "phase17_model_results.json"
    result_json.write_text(json.dumps(results_doc, indent=2) + "\n", encoding="utf-8")
    result_rows = ["# Phase 17 model results", "", "Regression target: source-recorded `pass_rate` in [0, 1]. Accuracy/F1/AUC use the derived reporting threshold `pass_rate >= 0.5`; this is not an original dataset label.", "", "| Model | Val MAE | Test MAE | Test RMSE | Test R² | Test accuracy* | Test macro F1* | Test weighted F1* |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for name, score in results.items():
        val, test = score["validation"], score["test"]
        result_rows.append(f"| {name} | {val['mae']:.4f} | {test['mae']:.4f} | {test['rmse']:.4f} | {test['r2']:.4f} | {test['accuracy']:.4f} | {test['macro_f1']:.4f} | {test['weighted_f1']:.4f} |")
    result_rows.extend(["", f"Selected using validation MAE: **{selected}**.", "", "The held-out test set was not used for model or hyperparameter selection. See `phase17_model_results.json` for precision/recall, ROC-AUC, PR-AUC, confusion matrices and Spearman correlation.", ""])
    (ROOT / "docs" / "research" / "phase17" / "phase17_model_results.md").write_text("\n".join(result_rows), encoding="utf-8")
    write_figures(y_test, test_prediction, results, ROOT / "reports" / "phase17")
    write_comparison(y_test, test_prediction, test_df, ROOT / "docs" / "research" / "phase17" / "phase17_system_comparison.md")

    card = f"""# Phase 17 model card\n\n- Purpose: auxiliary regression estimate of benchmark execution pass rate for competitive-programming Python solutions.\n- Dataset: NVIDIA OpenCodeReasoning-2 Python split, pinned revision `{REVISION}`; three contiguous shards, row-level license filter.\n- Task/target: regression to recorded `pass_rate` in [0, 1]. This is not a CodeGuard claim label or a human-reviewed correctness judgment.\n- Model: {selected}; alternatives: mean dummy, Ridge, LinearSVR, and ExtraTrees numeric baseline.\n- Features: solution-code word TF-IDF, deterministic AST/code-shape features, source/upstream dataset/difficulty metadata. No critique, generated judgement, pass_rate input, or R1 rationale.\n- Split: fixed seed {SEED}; grouped 70/15/15 by connected components of question ID and normalized exact code hash.\n- Test metrics: `{json.dumps(results[selected]['test'], sort_keys=True)}`.\n- Limitations: generated/automated source; no human verification; blank question text; noisy or unavailable execution pass_rate; contest-domain only; no evidence-grounded factual verification; exact duplicates grouped but semantic near duplicates not fully excluded.\n- Intended use: display as an auxiliary dataset-domain signal alongside the independent validators.\n- Not intended: standalone correctness/safety proof, factual verification, replacing isolated tests, or assigning CodeGuard review/gold labels.\n"""
    (model_dir / "MODEL_CARD.md").write_text(card, encoding="utf-8")

    stats = {
        "total_downloaded_rows": report["counts"]["original_rows"], "valid_rows": len(records),
        "invalid_rows": report["counts"]["original_rows"] - len(records), "python_rows": len(records),
        "non_python_rows": 0, "missing_values": {"target": report["counts"].get("excluded_invalid_pass_rate", 0), "code": report["counts"].get("excluded_missing_code", 0)},
        "duplicate_rows_removed": report["counts"].get("excluded_exact_duplicate", 0), "license_counts": report["license_counts_before_filtering"],
        "source_distribution": {key: int(value) for key, value in pd.Series([row["source"] for row in records]).value_counts().items()},
        "upstream_dataset_distribution": {key: int(value) for key, value in pd.Series([row["dataset"] for row in records]).value_counts().items()},
        "target_distribution": report["pass_rate_bins"], "average_code_chars": float(np.mean([len(r["code"]) for r in records])),
        "average_code_words": float(np.mean([len(r["code"].split()) for r in records])),
        "average_code_lines": float(np.mean([len(r["code"].splitlines()) for r in records])),
        "average_explanation_length": None, "explanation": "Generated rationale fields are not retained or used as model features; the published question field is a placeholder in this split.",
        "malformed_python_syntax": report["counts"].get("syntax_invalid", 0), "unsafe_examples": "Not executed; dangerous API mentions counted only as static text features.",
        "dangerous_api_mention_rows": sum(row["features"]["dangerous_api_mentions"] > 0 for row in records),
        "records_without_usable_code_or_target": report["counts"]["original_rows"] - len(records),
        "exact_duplicate_rate": report["counts"].get("excluded_exact_duplicate", 0) / max(1, report["counts"]["original_rows"]),
        "near_duplicate_rate": None,
    }
    stats_json.write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    stats_md = ["# Phase 17 dataset statistics", "", f"- Downloaded rows: {stats['total_downloaded_rows']}", f"- Valid rows: {stats['valid_rows']}", f"- Invalid/excluded rows: {stats['invalid_rows']}", f"- Python rows: {stats['python_rows']}", f"- Non-Python rows: {stats['non_python_rows']}", f"- Exact duplicate rows removed: {stats['duplicate_rows_removed']} ({stats['exact_duplicate_rate']:.2%})", f"- Average code length: {stats['average_code_chars']:.1f} characters, {stats['average_code_words']:.1f} whitespace tokens, {stats['average_code_lines']:.1f} lines", f"- Source distribution: `{json.dumps(stats['source_distribution'], sort_keys=True)}`", f"- Upstream dataset distribution: `{json.dumps(stats['upstream_dataset_distribution'], sort_keys=True)}`", "- Near-duplicate rate: not estimated; question IDs and exact normalized code hashes are grouped across splits.", "- Explanation length: unavailable; the published question field is a placeholder and generated rationale was excluded.", "- Target distribution and missing/filter counts: see `phase17_dataset_statistics.json` and `phase17_preprocessing_report.json`.", ""]
    (ROOT / "docs" / "research" / "phase17" / "phase17_dataset_statistics.md").write_text("\n".join(stats_md), encoding="utf-8")
    prep_md.write_text("# Phase 17 preprocessing report\n\n" + json.dumps(report, indent=2) + "\n", encoding="utf-8")
    selection = ROOT / "docs" / "research" / "PHASE_17_DATASET_SELECTION.md"
    if selection.exists():
        text = selection.read_text(encoding="utf-8").split("\n## Observed run counts")[0]
        text += f"\n\n## Observed run counts\n\n- Downloaded rows: {report['counts']['original_rows']}\n- Usable rows after license, code, ID, target, and exact duplicate filters: {len(records)}\n- Split sizes: `{json.dumps(split_report['counts'], sort_keys=True)}`\n"
        selection.write_text(text, encoding="utf-8")
    metadata_path = ROOT / "data" / "raw" / "phase17" / "DATASET_METADATA.json"
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["record_count"] = report["counts"]["original_rows"]
        metadata["usable_record_count"] = len(records)
        metadata["sha256"] = hashlib_sha_of_files(metadata.get("downloaded_files", []))
        metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results_doc, indent=2))


def hashlib_sha_of_files(files: list[dict]) -> str:
    import hashlib
    digest = hashlib.sha256()
    for entry in files:
        digest.update(entry["sha256"].encode("ascii"))
    return digest.hexdigest()


def write_figures(y_true: np.ndarray, y_pred: np.ndarray, results: dict, reports: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    reports.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.scatter(y_true, y_pred, s=8, alpha=0.25)
    ax.plot([0, 1], [0, 1], "--", color="black")
    ax.set(xlabel="Recorded test pass rate", ylabel="Predicted pass rate", xlim=(0, 1), ylim=(0, 1), title="Phase 17 held-out predictions")
    fig.tight_layout(); fig.savefig(reports / "phase17_metrics.png", dpi=150); plt.close(fig)
    matrix = confusion_matrix((y_true >= 0.5).astype(int), (y_pred >= 0.5).astype(int), labels=[0, 1])
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.imshow(matrix, cmap="Blues")
    ax.set(xticks=[0, 1], yticks=[0, 1], xticklabels=["< 0.5", "≥ 0.5"], yticklabels=["< 0.5", "≥ 0.5"],
           xlabel="Predicted pass-rate bin", ylabel="Observed pass-rate bin", title="Derived threshold confusion matrix")
    for (row, col), value in np.ndenumerate(matrix):
        ax.text(col, row, str(value), ha="center", va="center")
    fig.tight_layout(); fig.savefig(reports / "phase17_confusion_matrix.png", dpi=150); plt.close(fig)


def write_comparison(y_true: np.ndarray, y_pred: np.ndarray, test_df: pd.DataFrame, path: Path) -> None:
    from sklearn.metrics import accuracy_score, precision_recall_fscore_support
    truth = (y_true >= 0.5).astype(int)
    ml = (y_pred >= 0.5).astype(int)
    deterministic = (test_df["syntax_valid"].to_numpy() > 0).astype(int)
    combined = ((test_df["syntax_valid"].to_numpy() > 0) & (y_pred >= 0.5)).astype(int)
    def scores(pred: np.ndarray) -> dict:
        p, r, f, _ = precision_recall_fscore_support(truth, pred, average="binary", zero_division=0)
        return {"accuracy": float(accuracy_score(truth, pred)), "precision": float(p), "recall": float(r), "f1": float(f)}
    content = """# Phase 17 proxy comparison\n\nThis comparison is limited to the public benchmark target `pass_rate >= 0.5`. It is **not** a CodeGuard decision comparison. `Deterministic` is Python AST syntax validity, `ML` thresholds predicted pass rate, and `Combined` requires syntax validity and predicted pass rate >= 0.5. Evidence retrieval and the application's explanation verifier are not applicable to this code-only benchmark.\n\n| Method | Accuracy | Precision | Recall | F1 |\n|---|---:|---:|---:|---:|\n"""
    for name, pred in (("ML alone", ml), ("Deterministic syntax alone", deterministic), ("Combined proxy", combined)):
        metric = scores(pred)
        content += f"| {name} | {metric['accuracy']:.4f} | {metric['precision']:.4f} | {metric['recall']:.4f} | {metric['f1']:.4f} |\n"
    path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
