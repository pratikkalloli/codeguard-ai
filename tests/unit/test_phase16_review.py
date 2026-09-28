"""Phase 16 candidate inventory, review-state and safe persistence tests."""
from __future__ import annotations

import csv
import sqlite3
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path

from codeguard.ml.phase16 import (
    CANDIDATE_FIELDS, DECISIONS, PHASE15_DIR, build_phase16_workspace,
    validate_candidates, write_manifest, write_phase16_report,
    write_phase16_reports, write_research_reports,
)
from codeguard.ml.review import (
    get_review_record, initialize_review_db, list_review_records, review_state,
    save_adjudication, save_independent_review,
)


class Phase16WorkspaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name) / "phase16"
        cls.inventory = build_phase16_workspace(cls.root)
        write_manifest(cls.root, source_facts_path=PHASE15_DIR / "raw" / "source_facts.json")
        write_research_reports(cls.root, cls.inventory)
        cls.metrics = write_phase16_reports(cls.root, cls.inventory)
        write_phase16_report(cls.root, cls.inventory, cls.metrics)
        cls.db = cls.root / "review" / "reviews.sqlite3"
        initialize_review_db(cls.root / "review" / "review_queue.csv", cls.db)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def test_candidate_schema_and_explicit_decisions(self) -> None:
        rows = self.inventory["candidates"]
        validate_candidates(rows)
        self.assertGreaterEqual(len(rows), 15)
        self.assertTrue(all(set(row) == set(CANDIDATE_FIELDS) for row in rows))
        self.assertTrue({row["decision"] for row in rows}.issubset(DECISIONS))
        self.assertTrue(all(row["exclusion_reason"] for row in rows))
        invalid = dict(rows[0]); invalid["decision"] = "SILENTLY_DROP"
        with self.assertRaisesRegex(ValueError, "invalid decision"):
            validate_candidates([invalid])

    def test_inventory_review_queue_has_complete_provenance_and_licenses(self) -> None:
        queue = self.inventory["queue"]
        self.assertEqual(len(queue), 72)
        self.assertTrue(all(row["source_url"].startswith("https://") for row in queue))
        self.assertTrue(all(row["source_record_id"] and row["license"] and row["provenance"] for row in queue))
        self.assertEqual({row["review_status"] for row in queue}, {"pending"})
        self.assertEqual({row["reviewer_A_id"] for row in queue}, {""})
        self.assertEqual({row["reviewer_B_id"] for row in queue}, {""})
        self.assertEqual({row["final_adjudicated_label"] for row in queue}, {""})

    def test_grouped_splits_and_external_source_fact_isolation(self) -> None:
        partitions: dict[str, set[str]] = defaultdict(set)
        for row in self.inventory["internal"]:
            self.assertIn(row["split"], {"train", "validation", "test"})
            partitions[row["evidence_group"]].add(row["split"])
        self.assertTrue(all(len(split_names) == 1 for split_names in partitions.values()))
        internal_sources = {r["source_url"] for r in self.inventory["internal"]}
        internal_facts = {r["fact_key"] for r in self.inventory["internal"]}
        self.assertFalse(internal_sources & {r["source_url"] for r in self.inventory["external"]})
        self.assertFalse(internal_facts & {r["fact_key"] for r in self.inventory["external"]})

    def test_duplicate_near_duplicate_and_quality_indicators(self) -> None:
        self.assertEqual(self.metrics["exact_duplicate_count"], 0)
        self.assertEqual(self.metrics["normalized_claim_label_conflicts"], 0)
        self.assertGreater(self.metrics["near_duplicate_pairs_ge_090"], 0)
        self.assertEqual(self.metrics["near_duplicate_leakage_violations"], 0)
        self.assertEqual(self.metrics["source_group_split_violations"], 0)
        self.assertEqual(self.metrics["source_pages"], len(self.metrics["source_page_distribution"]))
        self.assertEqual(self.metrics["reviewed_count"], 0)

    def test_external_export_has_no_proposed_or_gold_labels_before_review(self) -> None:
        path = self.root / "external" / "external_test.csv"
        with path.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f); rows = list(reader)
            self.assertIn("gold_label", reader.fieldnames)
            self.assertNotIn("label", reader.fieldnames)
            self.assertNotIn("proposed_label", reader.fieldnames)
        self.assertEqual(len(rows), 6)
        self.assertTrue(all(row["gold_label"] == "" and row["review_status"] == "pending" for row in rows))

    def test_required_phase16_outputs_exist(self) -> None:
        for rel in (
            "candidates/dataset_candidates.csv", "raw/README.md", "processed/canonical.csv",
            "processed/verified.csv", "processed/pending_review.csv", "processed/rejected.csv",
            "review/review_queue.csv", "review/reviews.sqlite3", "external/external_test.csv",
            "dataset_manifest.json", "reports/DATASET_CANDIDATES.md", "reports/LICENSE_AUDIT.md",
            "reports/LABEL_MAPPING.md", "reports/DATASET_CARD.md", "reports/QUALITY_REPORT.md",
            "reports/PHASE_16_REPORT.md"):
            self.assertTrue((self.root / rel).is_file(), rel)


class ReviewStateAndPersistenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name) / "phase16"
        cls.inventory = build_phase16_workspace(cls.root)
        cls.db = cls.root / "review" / "reviews.sqlite3"
        initialize_review_db(cls.root / "review" / "review_queue.csv", cls.db)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def test_review_state_transitions(self) -> None:
        self.assertEqual(review_state("", ""), ("pending", "pending", ""))
        self.assertEqual(review_state("Supported", ""), ("pending", "awaiting_second_review", ""))
        self.assertEqual(review_state("Supported", "Supported"), ("reviewed", "agreement_pending_adjudication", ""))
        self.assertEqual(review_state("Supported", "Contradicted"), ("disputed", "disagreement", ""))
        self.assertEqual(review_state("Reject", "Reject"), ("rejected", "rejected_by_reviewers", ""))
        self.assertEqual(review_state("Needs adjudication", ""), ("disputed", "disagreement", ""))

    def test_reviewer_validation_requires_real_identifier_and_valid_confidence(self) -> None:
        row_id = self.inventory["internal"][0]["id"]
        with self.assertRaisesRegex(ValueError, "real reviewer identifier"):
            save_independent_review(self.db,row_id,"A",decision="Supported",confidence=3,notes="",reviewer_id=" ")
        with self.assertRaisesRegex(ValueError, "1 to 5"):
            save_independent_review(self.db,row_id,"A",decision="Supported",confidence=8,notes="",reviewer_id="real-reviewer-a")
        with self.assertRaisesRegex(ValueError, "notes"):
            save_independent_review(self.db,row_id,"A",decision="Reject",confidence=3,notes="",reviewer_id="real-reviewer-a")

    def test_independent_agreement_persists_and_exports_verified_label(self) -> None:
        row_id = self.inventory["internal"][0]["id"]
        save_independent_review(self.db,row_id,"A",decision="Supported",confidence=4,notes="Evidence directly states this.",reviewer_id="reviewer-a")
        current=get_review_record(self.db,row_id)
        self.assertEqual(current["review_status"],"pending")
        self.assertEqual(current["reviewer_label"],"Supported")
        with self.assertRaisesRegex(ValueError,"different real people"):
            save_independent_review(self.db,row_id,"B",decision="Supported",confidence=4,notes="Same.",reviewer_id="reviewer-a")
        saved=save_independent_review(self.db,row_id,"B",decision="Supported",confidence=5,notes="Independently confirms.",reviewer_id="reviewer-b")
        self.assertEqual(saved["review_status"],"reviewed")
        self.assertEqual(saved["verified_label"],"")
        self.assertEqual(saved["review_status"],"reviewed")
        adjudicated=save_adjudication(self.db,row_id,decision="Supported",notes="The supplied documentation directly entails the claim.",adjudicator_id="adjudicator-a")
        self.assertEqual(adjudicated["review_status"],"adjudicated")
        self.assertEqual(adjudicated["verified_label"],"Supported")
        with (self.root/"processed"/"adjudicated.csv").open(encoding="utf-8",newline="") as f:
            rows=list(csv.DictReader(f))
        match=next(row for row in rows if row["id"]==row_id)
        self.assertEqual(match["label"],"Supported")
        self.assertEqual(match["gold_label"],"Supported")
        with (self.root/"processed"/"verified.csv").open(encoding="utf-8",newline="") as f:
            self.assertEqual(list(csv.DictReader(f)),[])
        connection = sqlite3.connect(self.db)
        try:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM review_events WHERE review_id=?",(row_id,)).fetchone()[0],2)
        finally:
            connection.close()

    def test_disagreement_requires_independent_adjudicator_and_can_reject(self) -> None:
        row_id = self.inventory["internal"][1]["id"]
        save_independent_review(self.db,row_id,"A",decision="Supported",confidence=2,notes="Tentative.",reviewer_id="reviewer-c")
        disputed=save_independent_review(self.db,row_id,"B",decision="Contradicted",confidence=4,notes="Passage differs.",reviewer_id="reviewer-d")
        self.assertEqual(disputed["review_status"],"disputed")
        with self.assertRaisesRegex(ValueError,"independent"):
            save_adjudication(self.db,row_id,decision="Reject",notes="Duplicate",adjudicator_id="reviewer-c")
        with self.assertRaisesRegex(ValueError,"notes"):
            save_adjudication(self.db,row_id,decision="Reject",notes="",adjudicator_id="reviewer-e")
        rejected=save_adjudication(self.db,row_id,decision="Reject",notes="This record is ambiguous and unsuitable.",adjudicator_id="reviewer-e")
        self.assertEqual(rejected["review_status"],"rejected")
        self.assertEqual(rejected["verified_label"],"")
        self.assertEqual(rejected["final_adjudicated_label"],"")

    def test_escalation_can_be_adjudicated_with_a_real_third_person(self) -> None:
        row_id = self.inventory["internal"][2]["id"]
        save_independent_review(self.db,row_id,"A",decision="Needs adjudication",confidence=2,notes="The evidence scope is ambiguous.",reviewer_id="reviewer-f")
        resolved=save_adjudication(self.db,row_id,decision="Insufficient Evidence",notes="The passage does not establish either side of the proposition.",adjudicator_id="adjudicator-g")
        self.assertEqual(resolved["review_status"],"adjudicated")
        self.assertEqual(resolved["verified_label"],"Insufficient Evidence")
        self.assertEqual(resolved["final_adjudicated_label"],"Insufficient Evidence")


if __name__ == "__main__":
    unittest.main()
