import unittest

from codeguard.ml.phase16_5 import FACT_FIELDS
from codeguard.ml.phase16_7_facts import REVIEW_STATUS, facts


class Phase167FactInventoryTests(unittest.TestCase):
    def test_inventory_only_facts_have_complete_provenance(self):
        rows = facts()
        self.assertGreaterEqual(len(rows), 15)
        self.assertEqual(len(rows), len({row["fact_key"] for row in rows}))
        required = set(FACT_FIELDS)
        for row in rows:
            self.assertTrue(required <= row.keys())
            self.assertTrue(row["source_url"].startswith("https://docs.python.org/3/"))
            self.assertTrue(row["section"] and row["evidence_locator"] and row["evidence_text"])
            self.assertEqual(row["fact_review_status"], REVIEW_STATUS)
            self.assertEqual(row["source_group"], f"page:{row['source_url']}")

    def test_fact_expansion_is_not_candidate_generation_input(self):
        from codeguard.ml.phase16_5 import FACTS

        expanded_keys = {row["fact_key"] for row in facts()}
        candidate_fact_keys = {item[0] for item in FACTS}
        self.assertTrue(expanded_keys.isdisjoint(candidate_fact_keys))


if __name__ == "__main__":
    unittest.main()
