import csv
import json
import unittest
from collections import Counter
from pathlib import Path

from codeguard.ml.phase16_5 import OUT
from codeguard.ml.research_dataset import FIELDS, normalize

ROOT = Path(__file__).resolve().parents[2]


class Phase169CapacityAndExpansionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with (OUT / "candidates.csv").open(encoding="utf-8-sig", newline="") as handle:
            cls.rows = list(csv.DictReader(handle))
        with (ROOT / "data/ml/phase16_9/initial_capacity_analysis.json").open(encoding="utf-8") as handle:
            cls.capacity = json.load(handle)

    def test_measured_capacity_is_conservative_and_below_1000(self):
        c = self.capacity
        self.assertEqual(c["inventory_fact_count"], 205)
        self.assertEqual(c["facts_without_candidates"], 78)
        self.assertEqual(c["new_supported_candidates_passing_dry_run"], 78)
        self.assertEqual(c["dry_run_quality_exclusions"], 0)
        self.assertEqual(c["measured_capacity_with_dry_run_additions"], 389)
        self.assertLess(c["measured_capacity_with_dry_run_additions"], 1000)

    def test_new_rows_have_provenance_and_remain_pending_without_gold(self):
        added = [row for row in self.rows if row.get("review_id", "").startswith("cg169-")]
        self.assertEqual(len(added), 78)
        for row in added:
            for field in FIELDS:
                if field == "label":
                    self.assertEqual(row[field], "")
                elif field == "id":
                    # The review_id is the persisted stable identity in this export.
                    self.assertTrue(row["review_id"].startswith("cg169-"))
                else:
                    self.assertTrue(row.get(field), (row["review_id"], field))
            self.assertEqual(row["data_origin"], "synthetic")
            self.assertEqual(row["review_status"], "pending")
            self.assertEqual(row["proposed_label"], "Supported")
            self.assertEqual(row["gold_label"], "")

    def test_external_partition_has_no_url_fact_or_claim_overlap(self):
        internal = [r for r in self.rows if r["dataset_partition"] == "internal"]
        external = [r for r in self.rows if r["dataset_partition"] == "external"]
        self.assertFalse({r["source_url"] for r in internal} & {r["source_url"] for r in external})
        self.assertFalse({r["fact_key"] for r in internal} & {r["fact_key"] for r in external})
        self.assertFalse({normalize(r["claim"]) for r in internal} & {normalize(r["claim"]) for r in external})
        self.assertEqual(Counter(r["dataset_partition"] for r in self.rows), {"internal": 193, "external": 196})


if __name__ == "__main__":
    unittest.main()
