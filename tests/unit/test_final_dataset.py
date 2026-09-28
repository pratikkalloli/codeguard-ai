"""Validation tests for the non-training final dataset build."""

from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from codeguard.ml.final_dataset import FIELDS, PILOT_CSV, build_final_dataset
from codeguard.ml.dataset import LABELS


class FinalDatasetBuildTests(unittest.TestCase):
    def test_final_dataset_preserves_pilot_and_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "final"
            result = build_final_dataset(output_dir=output)
            rows = result["records"]
            self.assertEqual(len(rows), 31)
            with Path(PILOT_CSV).open(encoding="utf-8", newline="") as pilot_file:
                pilot_rows = list(csv.DictReader(pilot_file))
            self.assertTrue({row["claim"] for row in pilot_rows}.issubset({row["claim"] for row in rows}))
            self.assertEqual(set(row["label"] for row in rows), set(LABELS))
            self.assertEqual({row["data_origin"] for row in rows}, {"synthetic"})
            self.assertTrue(all(row["fact_key"] and row["topic"] for row in rows))
            self.assertEqual(result["metadata"]["quality"]["conflicting_labels"], [])
            for filename in ("claims.csv", "train.csv", "validation.csv", "test.csv",
                             "dataset_metadata.json", "dataset_sources.json", "dataset_analysis.json"):
                self.assertTrue((output / filename).is_file(), filename)
            with (output / "claims.csv").open(encoding="utf-8", newline="") as handle:
                self.assertEqual(tuple(next(csv.reader(handle))), FIELDS)
            metadata = json.loads((output / "dataset_metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["total_records"], sum(metadata["records_per_class"].values()))

    def test_group_splits_are_disjoint_and_near_duplicates_stay_together(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = build_final_dataset(output_dir=Path(directory) / "final")
            splits = result["splits"]
            groups = {name: {row["leakage_group"] for row in rows} for name, rows in splits.items()}
            self.assertFalse(groups["train"] & groups["validation"])
            self.assertFalse(groups["train"] & groups["test"])
            self.assertFalse(groups["validation"] & groups["test"])
            for rows in splits.values():
                self.assertEqual({row["label"] for row in rows}, set(LABELS))
            self.assertLessEqual(abs(len(splits["train"]) / 31 - .70), .10)
            self.assertTrue(all(pair["same_leakage_group"] for pair in result["metadata"]["quality"]["near_duplicate_pairs"]))

    def test_public_datasets_are_documented_but_not_mixed_in(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = build_final_dataset(output_dir=Path(directory) / "final")
            self.assertEqual(result["sources"]["used_public_datasets"], [])
            names = {row["name"] for row in result["sources"]["candidates"]}
            self.assertEqual(names, {"FEVER", "SciFact"})


if __name__ == "__main__":
    unittest.main()
