"""Phase 16.6B inventory and candidate integrity checks."""
from __future__ import annotations

import csv
import unittest
from collections import Counter

from codeguard.ml.phase16_5 import (
    FACTS, LEGACY_FACT_COUNT, OUT, QUEUE, _make_fact_records, _quality_filter,
    _text_metrics,
)


class Phase166BInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.facts, cls.sources, cls.generated = _make_fact_records()
        with QUEUE.open(encoding="utf-8-sig", newline="") as handle:
            cls.persisted = list(csv.DictReader(handle))
        cls.new_facts = cls.facts[-(len(FACTS) - LEGACY_FACT_COUNT):]
        cls.new_rows = [r for r in cls.generated if r["review_id"].startswith("cg166b-")]

    def test_appended_inventory_has_unique_keys_and_complete_provenance(self) -> None:
        keys = [r["fact_key"] for r in self.new_facts]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertGreaterEqual(len(self.new_facts), 40)
        for fact in self.new_facts:
            for field in ("canonical_fact", "topic", "source_url", "source_title",
                          "source_group", "section", "evidence_locator", "evidence_text",
                          "license", "license_url", "provenance_status"):
                self.assertTrue(fact.get(field), (fact["fact_key"], field))
            self.assertTrue(fact["source_url"].startswith("https://docs.python.org/3/"))
            self.assertIn("pending", fact["provenance_status"].lower())

    def test_exported_inventory_contains_candidate_fact_keys(self) -> None:
        with (OUT / "fact_inventory.csv").open(encoding="utf-8-sig", newline="") as handle:
            inventory = list(csv.DictReader(handle))
        inventory_keys = [r["fact_key"] for r in inventory]
        candidate_keys = {r["fact_key"] for r in self.persisted if r.get("fact_key")}
        self.assertEqual(len(inventory_keys), len(set(inventory_keys)))
        self.assertTrue(candidate_keys <= set(inventory_keys))
        inventory_only = set(inventory_keys) - candidate_keys
        self.assertTrue(all(r.get("fact_review_status") == "pending_independent_review"
                            for r in inventory if r["fact_key"] in inventory_only))

    def test_candidate_counts_are_varied_and_proposals_are_not_gold(self) -> None:
        counts = Counter(r["fact_key"] for r in self.new_rows)
        self.assertEqual(set(counts), {r["fact_key"] for r in self.new_facts})
        self.assertEqual(set(counts.values()), {2, 3})
        for row in self.new_rows:
            self.assertEqual(row["data_origin"], "synthetic")
            self.assertEqual(row["review_status"], "pending")
            self.assertIn(row["proposed_label"], {"Supported", "Contradicted", "Insufficient Evidence"})
            self.assertEqual(row["gold_label"], "")
            self.assertEqual(row["label"], "")

    def test_external_sources_are_separate_and_new_rows_are_deduplicated(self) -> None:
        existing = [r for r in self.persisted if not r.get("review_id", "").startswith("cg166b-")]
        internal_urls = {r["source_url"] for r in existing + self.new_rows
                         if r.get("dataset_partition") == "internal"}
        external_urls = {r["source_url"] for r in existing + self.new_rows
                         if r.get("dataset_partition") == "external"}
        internal_facts = {r["fact_key"] for r in existing + self.new_rows
                          if r.get("dataset_partition") == "internal"}
        external_facts = {r["fact_key"] for r in existing + self.new_rows
                          if r.get("dataset_partition") == "external"}
        self.assertFalse(internal_urls & external_urls)
        self.assertFalse(internal_facts & external_facts)
        accepted, excluded = _quality_filter(self.new_rows, existing)
        metrics = _text_metrics(accepted)
        self.assertEqual(len(accepted), len(self.new_rows))
        self.assertEqual(excluded, [])
        self.assertEqual(metrics["exact_normalized_claim_duplicates"], 0)
        self.assertEqual(metrics["near_duplicate_pairs_ge_090"], 0)
        self.assertEqual(metrics["same_fact_semantic_duplicates"], 0)

    def test_same_fact_article_variant_is_rejected_but_negation_is_distinct(self) -> None:
        existing = [{"id": "prior", "claim": "A list is mutable", "fact_key": "list_mutability"}]
        candidates = [
            {"id": "duplicate", "claim": "List mutable", "fact_key": "list_mutability"},
            {"id": "contradiction", "claim": "A list is not mutable", "fact_key": "list_mutability"},
        ]
        kept, excluded = _quality_filter(candidates, existing)
        self.assertEqual([r["id"] for r in kept], ["contradiction"])
        self.assertEqual(len(excluded), 1)
        self.assertIn("same-fact semantic duplicate", excluded[0]["exclusion_reason"])

    def test_idempotent_rebuild_does_not_reject_inherited_review_records(self) -> None:
        existing = [
            {"id": "inherited-a", "claim": "A list is mutable", "fact_key": "list_mutability"},
            {"id": "inherited-b", "claim": "A list is mutable", "fact_key": "list_mutability"},
        ]
        kept, excluded = _quality_filter(existing, existing)
        self.assertEqual([r["id"] for r in kept], ["inherited-a", "inherited-b"])
        self.assertEqual(excluded, [])


if __name__ == "__main__":
    unittest.main()
