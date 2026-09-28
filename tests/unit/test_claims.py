"""Tests for conservative explanation claim analysis."""

import unittest

from codeguard.claims import analyze_explanation


class ClaimAnalysisTests(unittest.TestCase):
    def test_factual_sentence_needs_evidence(self) -> None:
        claims = analyze_explanation("Python dictionaries preserve insertion order.")
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0].status, "Insufficient evidence")
        self.assertEqual(claims[0].evidence_text, "")

    def test_direct_mutability_conflict_is_marked_internal_contradiction(self) -> None:
        claims = analyze_explanation("Python lists are mutable. Python lists are immutable.")
        self.assertEqual([claim.status for claim in claims], ["Contradicted", "Contradicted"])
        self.assertTrue(all("internal inconsistency" in claim.reason for claim in claims))

    def test_instruction_is_not_treated_as_supported_fact(self) -> None:
        claims = analyze_explanation("Use a dictionary to store these values.")
        self.assertEqual(claims[0].status, "Not evaluated")

    def test_empty_explanation_produces_no_claims(self) -> None:
        self.assertEqual(analyze_explanation(" \n "), [])

    def test_supported_is_never_assigned_without_source_evidence(self) -> None:
        claims = analyze_explanation("The function returns an integer.")
        self.assertNotIn("Supported", {claim.status for claim in claims})


if __name__ == "__main__":
    unittest.main()
