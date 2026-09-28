"""Small deterministic scikit-learn model factory and artifact loading."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
import joblib

from codeguard.ml.dataset import PROJECT_ROOT
from codeguard.ml.features import NumericPairFeatures, TfidfPairFeatures


DEFAULT_MODEL_PATH = PROJECT_ROOT / "models" / "claim_verifier" / "claim_verifier_v1.joblib"
SVM_MODEL_PATH = PROJECT_ROOT / "models" / "claim_verifier" / "claim_verifier_linear_svm_v1.joblib"


def build_model(name: str = "logistic_regression", random_seed: int = 42) -> Pipeline:
    """Build one fixed, reproducible pipeline. No data-driven tuning is done."""
    if name == "logistic_regression":
        classifier = LogisticRegression(max_iter=2000, class_weight="balanced", random_state=random_seed)
    elif name == "linear_svm":
        classifier = LinearSVC(class_weight="balanced", random_state=random_seed, max_iter=10000)
    else:
        raise ValueError(f"Unknown model name: {name}")
    features = FeatureUnion([
        ("claim_evidence_tfidf", TfidfPairFeatures(ngram_range=(1, 2))),
        ("numeric_pair_features", Pipeline([
            ("extract", NumericPairFeatures()),
            ("scale", StandardScaler(with_mean=False)),
        ])),
    ])
    return Pipeline([("features", features), ("classifier", classifier)])


def build_majority_baseline(train_labels: list[str]) -> str:
    """Return deterministic majority class (lexicographic tie break)."""
    if not train_labels:
        raise ValueError("Training labels cannot be empty.")
    counts: dict[str, int] = {}
    for label in train_labels:
        counts[label] = counts.get(label, 0) + 1
    return sorted(counts, key=lambda label: (-counts[label], label))[0]


def save_model(artifact: dict[str, Any], path: str | Path = DEFAULT_MODEL_PATH) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, target)
    return target


def load_model(path: str | Path = DEFAULT_MODEL_PATH) -> dict[str, Any]:
    target = Path(path)
    if not target.is_file():
        raise FileNotFoundError(f"Trained claim model is not available at {target}.")
    artifact = joblib.load(target)
    if not isinstance(artifact, dict) or "pipeline" not in artifact or "confidence_threshold" not in artifact:
        raise ValueError("Model artifact has an unsupported or malformed structure.")
    return artifact


def predict_with_confidence(artifact: dict[str, Any], records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Predict labels; only probability-producing estimators report confidence."""
    if not isinstance(records, list) or any(not isinstance(row, dict) for row in records):
        raise ValueError("Prediction input must be a list of feature records.")
    if not records:
        return []
    pipeline = artifact.get("pipeline")
    if pipeline is None or not hasattr(pipeline, "predict"):
        raise ValueError("Model artifact has no prediction pipeline.")
    predictions = pipeline.predict(records)
    classifier = pipeline.named_steps.get("classifier")
    probabilities = pipeline.predict_proba(records) if hasattr(classifier, "predict_proba") else None
    output = []
    for index, label in enumerate(predictions):
        confidence = float(max(probabilities[index])) if probabilities is not None else None
        output.append({"prediction": str(label), "confidence": confidence})
    return output


def majority_predict(train_labels: list[str], records: list[dict[str, Any]]) -> list[str]:
    label = build_majority_baseline(train_labels)
    return [label] * len(records)
