"""Phase 15 research dataset schema, provenance and leakage checks."""
from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from codeguard.ml.research_dataset import (
    DEFAULT_DIR, FIELDS, LABELS, build_research_dataset, validate_rows,
)


class ResearchDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temp.name) / "research_dataset"
        cls.result = build_research_dataset(cls.output)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def test_schema_labels_and_review_state(self) -> None:
        rows = self.result["rows"]
        self.assertGreater(len(rows), 40)
        self.assertTrue(all(tuple(row.keys()) == FIELDS for row in rows))
        self.assertTrue(all(row["label"] in LABELS for row in rows))
        self.assertEqual({row["data_origin"] for row in rows}, {"synthetic"})
        self.assertTrue(all(row["review_status"] == "pending_expert_review" for row in rows))
        self.assertFalse(self.result["metadata"]["ready_for_model_training"])

    def test_duplicate_and_conflicting_label_validation(self) -> None:
        sample = dict(self.result["rows"][0])
        duplicate = dict(sample)
        duplicate["id"] = "duplicate"
        with self.assertRaisesRegex(ValueError, "duplicate claim/evidence"):
            validate_rows([sample, duplicate])
        conflict = dict(sample)
        conflict.update(id="conflict", evidence="Different excerpt", label=(
            "Contradicted" if sample["label"] != "Contradicted" else "Supported"))
        with self.assertRaisesRegex(ValueError, "conflicting labels"):
            validate_rows([sample, conflict])

    def test_provenance_license_and_required_fields(self) -> None:
        rows = self.result["rows"]
        self.assertTrue(all(row["source_url"].startswith("https://") for row in rows))
        self.assertTrue(all("License" in row["license"] and row["source_record_id"] for row in rows))
        invalid = dict(rows[0]); invalid["source_url"] = ""
        with self.assertRaisesRegex(ValueError, "missing required fields: source_url"):
            validate_rows([invalid])

    def test_no_group_leakage_and_all_classes_in_each_split(self) -> None:
        splits = self.result["splits"]
        group_sets = {key: {row["evidence_group"] for row in values} for key, values in splits.items()}
        self.assertFalse(group_sets["train"] & group_sets["validation"])
        self.assertFalse(group_sets["train"] & group_sets["test"])
        self.assertFalse(group_sets["validation"] & group_sets["test"])
        for values in splits.values():
            self.assertEqual({row["label"] for row in values}, LABELS)

    def test_external_test_isolated_and_not_mixed_into_internal_splits(self) -> None:
        ext = self.result["external_test"]
        internal_urls = {row["source_url"] for row in self.result["rows"]}
        internal_facts = {row["fact_key"] for row in self.result["rows"]}
        self.assertTrue(ext)
        self.assertFalse({row["source_url"] for row in ext} & internal_urls)
        self.assertFalse({row["fact_key"] for row in ext} & internal_facts)
        self.assertTrue(all(row["source_url"].endswith("/reference/datamodel.html") for row in ext))

    def test_reproducibility_and_required_outputs(self) -> None:
        second = build_research_dataset(Path(self.temp.name) / "second")
        self.assertEqual(self.result["rows"], second["rows"])
        self.assertEqual(self.result["splits"], second["splits"])
        for rel in ("raw/source_facts.json", "processed/dataset.csv", "processed/train.csv",
                    "processed/validation.csv", "processed/test.csv", "processed/external_test.csv",
                    "dataset_metadata.json", "dataset_sources.json", "dataset_statistics.json",
                    "dataset_card.md", "data_dictionary.md", "license_attribution.md",
                    "reports/dataset_quality_report.md", "reports/class_distribution.svg",
                    "reports/source_distribution.svg"):
            self.assertTrue((self.output / rel).is_file(), rel)
        with (self.output / "processed/dataset.csv").open(encoding="utf-8", newline="") as f:
            self.assertEqual(tuple(next(csv.reader(f))), FIELDS)


if __name__ == "__main__":
    unittest.main()
