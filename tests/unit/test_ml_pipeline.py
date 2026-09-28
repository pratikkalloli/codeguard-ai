"""Tests for the synthetic claim-classification pilot and its safeguards."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codeguard.claim_verification import VerifiedClaim
from codeguard.ml.dataset import (
    LABELS,
    analyze_dataset,
    build_dataset,
    detect_near_duplicates,
    load_records,
    load_dataset_version,
    remove_exact_duplicates,
    validate_records,
)
from codeguard.ml.evaluate import evaluate_predictions
from codeguard.ml.features import NumericPairFeatures, TfidfPairFeatures
from codeguard.ml.inference import apply_ml_advisories
from codeguard.ml.models import load_model, predict_with_confidence
from codeguard.ml.train import run_training


class MLPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory()
        root = Path(cls.temp.name)
        cls.ml_dir = root / "data" / "ml"
        cls.reports_dir = root / "reports"
        cls.models_dir = root / "models"
        cls.training = run_training(cls.ml_dir, cls.reports_dir, cls.models_dir)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def test_dataset_creation_labels_origins_and_metadata(self) -> None:
        records = load_records(self.ml_dir / "claims.csv")
        metadata = self.training["dataset"]["metadata"]
        self.assertEqual(len(records), 15)
        self.assertEqual(metadata["samples_per_class"], {label: 5 for label in LABELS})
        self.assertEqual(metadata["data_origins"], {"synthetic": 15})
        self.assertTrue(all(record["data_origin"] == "synthetic" for record in records))
        self.assertTrue((self.ml_dir / "dataset_metadata.json").is_file())
        versioned = load_dataset_version(metadata["dataset_version"], self.ml_dir)
        self.assertEqual(len(versioned["records"]), 15)
        self.assertTrue((self.ml_dir / "versions" / metadata["dataset_version"] / "train.csv").is_file())

    def test_dataset_validation_labels_missing_evidence_and_duplicates(self) -> None:
        record = {"claim": "A claim", "evidence": "", "label": "INSUFFICIENT_EVIDENCE", "data_origin": "synthetic", "leakage_group": "topic"}
        self.assertEqual(validate_records([record]), [])
        invalid = dict(record, label="MAYBE")
        self.assertTrue(any("unsupported label" in error for error in validate_records([invalid])))
        unique, removed = remove_exact_duplicates([record, dict(record)])
        self.assertEqual((len(unique), removed), (1, 1))
        with self.assertRaises(ValueError):
            remove_exact_duplicates([record, dict(record, label="SUPPORTED")])

    def test_near_duplicate_detection_and_analysis(self) -> None:
        records = load_records(self.ml_dir / "claims.csv")
        pairs = detect_near_duplicates(records)
        self.assertGreaterEqual(len(pairs), 1)
        analysis = analyze_dataset(records)
        self.assertEqual(analysis["total_records"], 15)
        self.assertEqual(analysis["class_distribution"]["CONTRADICTED"], 5)
        self.assertEqual(analysis["exact_duplicate_count_removed"], 0)
        self.assertGreater(analysis["average_claim_length_words"], 0)

    def test_splits_are_group_disjoint_and_class_covered(self) -> None:
        splits = self.training["dataset"]["splits"]
        groups = {name: {row["leakage_group"] for row in rows} for name, rows in splits.items()}
        self.assertFalse(groups["train"] & groups["validation"])
        self.assertFalse(groups["train"] & groups["test"])
        self.assertFalse(groups["validation"] & groups["test"])
        for rows in splits.values():
            self.assertEqual({row["label"] for row in rows}, set(LABELS))
        self.assertEqual([len(splits[key]) for key in ("train", "validation", "test")], [9, 3, 3])

    def test_feature_extraction_ignores_target_label(self) -> None:
        records = load_records(self.ml_dir / "train.csv")
        text_features = TfidfPairFeatures().fit(records)
        matrix = text_features.transform(records)
        self.assertEqual(matrix.shape[0], len(records))
        numeric = NumericPairFeatures().transform(records)
        self.assertEqual(numeric.shape, (len(records), 4))
        changed_labels = [dict(row, label="different-target") for row in records]
        changed_matrix = text_features.transform(changed_labels)
        self.assertEqual((matrix != changed_matrix).nnz, 0)

    def test_models_trained_artifacts_load_and_predict(self) -> None:
        for filename in ("claim_verifier_v1.joblib", "claim_verifier_linear_svm_v1.joblib"):
            artifact = load_model(self.models_dir / filename)
            self.assertIn("pipeline", artifact)
        logistic = load_model(self.models_dir / "claim_verifier_v1.joblib")
        prediction = predict_with_confidence(logistic, [{"claim": "Python sets are unordered.", "evidence": "A set is unordered.", "tfidf_similarity": 0.5}])
        self.assertIn(prediction[0]["prediction"], LABELS)
        self.assertIsInstance(prediction[0]["confidence"], float)

    def test_missing_model_and_malformed_prediction_are_reported(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_model(Path(self.temp.name) / "missing.joblib")
        artifact = load_model(self.models_dir / "claim_verifier_v1.joblib")
        with self.assertRaises(ValueError):
            predict_with_confidence(artifact, "not-a-record-list")  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            predict_with_confidence({"pipeline": None, "confidence_threshold": 0.5}, [{"claim": "x"}])

    def test_metrics_error_analysis_and_artifacts_are_generated(self) -> None:
        metrics = evaluate_predictions(
            [{"claim": "a", "evidence": "x", "label": "SUPPORTED"}, {"claim": "b", "evidence": "y", "label": "CONTRADICTED"}],
            ["CONTRADICTED", "CONTRADICTED"], [0.7, 0.8],
        )
        self.assertEqual(metrics["accuracy"], 0.5)
        self.assertEqual(len(metrics["errors"]), 1)
        self.assertEqual(metrics["errors"][0]["confidence"], 0.7)
        for name in ("ml_metrics.json", "ml_dataset_analysis.json", "model_comparison.csv", "confusion_matrix.png"):
            self.assertTrue((self.reports_dir / name).is_file(), name)
        self.assertIn("logistic_regression_tfidf", self.training["report"]["cross_validation"])

    def test_confidence_threshold_handling_and_rule_status_preservation(self) -> None:
        artifact = load_model(self.models_dir / "claim_verifier_v1.joblib")
        claim = VerifiedClaim(
            claim_text="An unfamiliar claim outside the corpus.", status="Insufficient evidence",
            reason="No explicit rule applies.", evidence_text="", retrieval_score=None,
        )
        result = apply_ml_advisories([claim], self.models_dir / "claim_verifier_v1.joblib")[0]
        self.assertEqual(result.status, "Insufficient evidence")
        self.assertEqual(result.rule_result, "Insufficient evidence")
        self.assertIn(result.ml_result, LABELS)
        self.assertEqual(result.ml_review_required, result.ml_confidence is None or result.ml_confidence < artifact["confidence_threshold"])
        direct = VerifiedClaim(claim_text="Python lists are mutable.", status="Supported", reason="Evidence matches.")
        direct_result = apply_ml_advisories([direct], self.models_dir / "claim_verifier_v1.joblib")[0]
        self.assertEqual(direct_result.status, "Supported")
        self.assertEqual(direct_result.verification_method, "rule")
        self.assertIsNone(direct_result.ml_result)

    def test_missing_model_keeps_deterministic_verification(self) -> None:
        claim = VerifiedClaim(claim_text="unknown", status="Insufficient evidence", reason="rule")
        result = apply_ml_advisories([claim], Path(self.temp.name) / "absent.joblib")[0]
        self.assertEqual(result.status, "Insufficient evidence")
        self.assertEqual(result.rule_result, "Insufficient evidence")
        self.assertIsNone(result.ml_result)
        self.assertEqual(result.verification_method, "rule")


if __name__ == "__main__":
    unittest.main()
