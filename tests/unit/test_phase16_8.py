import csv
import unittest
from difflib import SequenceMatcher

from codeguard.ml.phase16_5 import FACTS, FACT_FIELDS, OUT
from codeguard.ml.phase16_8_facts import facts
from codeguard.ml.research_dataset import normalize


class Phase168InventoryTests(unittest.TestCase):
    def test_new_facts_have_unique_keys_and_complete_official_provenance(self):
        rows = facts()
        self.assertGreaterEqual(len(rows), 35)
        self.assertEqual(len(rows), len({row["fact_key"] for row in rows}))
        for row in rows:
            self.assertTrue(set(FACT_FIELDS) <= row.keys())
            self.assertTrue(row["source_url"].startswith("https://docs.python.org/3/"))
            self.assertTrue(row["section"] and row["evidence_locator"] and row["evidence_text"])
            self.assertEqual(row["fact_review_status"], "pending_independent_review")

    def test_inventory_expansion_does_not_generate_candidates(self):
        new_keys = {row["fact_key"] for row in facts()}
        self.assertTrue(new_keys.isdisjoint({item[0] for item in FACTS}))

    def test_new_canonical_facts_have_no_exact_or_near_duplicates(self):
        rows = facts()
        with (OUT / "fact_inventory.csv").open(encoding="utf-8-sig", newline="") as handle:
            inventory = list(csv.DictReader(handle))
        new_keys = {row["fact_key"] for row in rows}
        prior = [row for row in inventory if row.get("fact_key") not in new_keys]
        for i, row in enumerate(rows):
            text = normalize(row["canonical_fact"])
            for other in [*prior, *rows[:i]]:
                other_text = normalize(other.get("canonical_fact", ""))
                self.assertNotEqual(text, other_text)
                self.assertLess(SequenceMatcher(None, text, other_text).ratio(), .90)


if __name__ == "__main__":
    unittest.main()
