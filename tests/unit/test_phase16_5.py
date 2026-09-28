"""Phase 16.5 pool, quality-filter, batch, and gold-label protection tests."""
from __future__ import annotations

import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path

from codeguard.ml.phase16_5 import (
    FACT_FIELDS, QUEUE, _assign_batches, _make_fact_records, _quality_filter,
    _text_metrics, export_phase16_5_views,
)
from codeguard.ml.review import (
    initialize_review_db, list_review_records, save_adjudication,
    save_independent_review,
)


class Phase165CandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.facts, cls.sources, cls.candidates = _make_fact_records()
        with QUEUE.open(encoding="utf-8-sig", newline="") as handle:
            cls.existing = [r for r in csv.DictReader(handle) if not r.get("review_id", "").startswith("cg165-")]
        additions=[r for r in cls.candidates if r["review_id"] not in {old.get("review_id") for old in cls.existing}]
        cls.kept, cls.excluded = _quality_filter(additions, cls.existing)

    def test_fact_and_source_inventory_has_complete_provenance(self) -> None:
        self.assertGreaterEqual(len(self.facts), 25)
        self.assertGreaterEqual(len({r["source_url"] for r in self.sources}), 10)
        for fact in self.facts:
            self.assertTrue(all(fact.get(field) for field in FACT_FIELDS))
            self.assertTrue(fact["source_url"].startswith("https://docs.python.org/"))
            self.assertIn("License", fact["license"])
            self.assertTrue(fact["license_url"].startswith("https://"))
            self.assertTrue(fact["evidence_text"])

    def test_new_candidates_remain_pending_and_labels_are_proposals(self) -> None:
        self.assertTrue(self.kept)
        for row in self.kept:
            self.assertEqual(row["data_origin"], "synthetic")
            self.assertEqual(row["review_status"], "pending")
            self.assertIn(row["proposed_label"], {"Supported", "Contradicted", "Insufficient Evidence"})
            self.assertEqual(row["label"], "")
            self.assertEqual(row["gold_label"], "")
            self.assertTrue(row["fact_key"] and row["claim_family"] and row["source_group"])

    def test_duplicate_filter_and_external_source_isolation(self) -> None:
        metrics = _text_metrics(self.kept)
        self.assertEqual(metrics["exact_normalized_claim_duplicates"], 0)
        self.assertEqual(metrics["near_duplicate_pairs_ge_090"], 0)
        internal = {r["source_url"] for r in self.existing + self.kept if r.get("dataset_partition") == "internal"}
        external = {r["source_url"] for r in self.existing + self.kept if r.get("dataset_partition") == "external"}
        self.assertFalse(internal & {r["source_url"] for r in self.kept if r["dataset_partition"] == "external"})
        self.assertFalse({r["fact_key"] for r in self.existing + self.kept if r.get("dataset_partition") == "internal"} &
                         {r["fact_key"] for r in self.kept if r["dataset_partition"] == "external"})
        self.assertTrue(external)
        self.assertTrue(self.excluded)
        self.assertTrue(all("duplicate" in r["exclusion_reason"] for r in self.excluded))

    def test_review_batches_are_stratified_and_external_is_separate(self) -> None:
        rows,batches=_assign_batches(self.existing+self.kept)
        by_id={r["review_id"]:r for r in rows}
        self.assertTrue(all(by_id[r["review_id"]]["batch_id"] for r in rows))
        internal_batches=[b for b in batches if b["partition"]=="internal"]
        self.assertGreaterEqual(len(internal_batches),2)
        for batch in internal_batches:
            self.assertGreaterEqual(batch["count"],25)
            self.assertLessEqual(batch["count"],50)
            self.assertGreaterEqual(batch["topic_count"],3)
            self.assertGreaterEqual(len(batch["proposed_label_counts"]),3)
        self.assertTrue(all(b["batch_id"]=="external_review_pool" for b in batches if b["partition"]=="external"))


class Phase165ReviewExportTests(unittest.TestCase):
    def test_only_real_adjudication_populates_gold_export(self) -> None:
        _,_,candidates=_make_fact_records()
        row=candidates[0]
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); review_dir=root/"review"; review_dir.mkdir()
            queue=review_dir/"review_queue.csv"; db=review_dir/"reviews.sqlite3"; out=root/"phase16_5"
            with queue.open("w",encoding="utf-8",newline="") as handle:
                writer=csv.DictWriter(handle,fieldnames=list(row)); writer.writeheader(); writer.writerow(row)
            initialize_review_db(queue,db)
            save_independent_review(db,row["review_id"],"A",decision="Supported",confidence=4,
                notes="The quoted sentence entails the proposition.",reviewer_id="actual-reviewer-a",
                review_mode="source_verified",source_verified=True)
            agreed=save_independent_review(db,row["review_id"],"B",decision="Supported",confidence=5,
                notes="Independent reading agrees.",reviewer_id="actual-reviewer-b")
            self.assertEqual(agreed["review_status"],"reviewed")
            self.assertEqual(agreed["verified_label"],"")
            self.assertTrue(agreed["reviewer_A_timestamp"])
            self.assertTrue(agreed["reviewer_A_source_verified"])
            export_phase16_5_views(db,out)
            with (out/"reviewed.csv").open(encoding="utf-8-sig",newline="") as handle:
                reviewed=list(csv.DictReader(handle))
            with (out/"adjudicated.csv").open(encoding="utf-8-sig",newline="") as handle:
                adjudicated=list(csv.DictReader(handle))
            self.assertEqual(len(reviewed),1)
            self.assertEqual(reviewed[0]["gold_label"],"")
            self.assertEqual(adjudicated,[])
            final=save_adjudication(db,row["review_id"],decision="Supported",
                notes="Independent adjudication confirms the evidence entailment.",adjudicator_id="actual-adjudicator")
            self.assertEqual(final["review_status"],"adjudicated")
            self.assertTrue(final["adjudication_timestamp"])
            export_phase16_5_views(db,out)
            with (out/"adjudicated.csv").open(encoding="utf-8-sig",newline="") as handle:
                adjudicated=list(csv.DictReader(handle))
            self.assertEqual(len(adjudicated),1)
            self.assertEqual(adjudicated[0]["gold_label"],"Supported")
            self.assertEqual(adjudicated[0]["label"],"Supported")


if __name__ == "__main__":
    unittest.main()
