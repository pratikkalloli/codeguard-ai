"""Deterministic tests for evidence-backed claim statuses."""

import unittest
from unittest.mock import patch

from codeguard.claim_verification import verify_claim, verify_explanation
from codeguard.embeddings import build_vector_index


class ClaimVerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.index = build_vector_index(index_path=None)

    def test_claim_with_matching_official_evidence_is_supported(self) -> None:
        result = verify_claim("Python lists are mutable.", index=self.index)
        self.assertEqual(result.status, "Supported")
        self.assertIn("mutable", result.evidence_text.lower())
        self.assertTrue(result.source_url.startswith("https://docs.python.org/"))
        self.assertGreater(result.retrieval_score or 0, 0)

    def test_claim_conflicting_with_official_evidence_is_contradicted(self) -> None:
        result = verify_claim("Python tuples are mutable.", index=self.index)
        self.assertEqual(result.status, "Contradicted")
        self.assertIn("immutable", result.evidence_text.lower())
        self.assertIn("directly conflicts", result.reason)

    def test_dictionary_order_claim_uses_synonym_normalization(self) -> None:
        supported = verify_claim("Python dicts preserve insertion order.", index=self.index)
        contradicted = verify_claim("Python dictionaries do not preserve insertion order.", index=self.index)
        self.assertEqual(supported.status, "Supported")
        self.assertEqual(contradicted.status, "Contradicted")

    def test_unknown_claim_stays_insufficient_evidence(self) -> None:
        result = verify_claim("Python strings can be resized in place.", index=self.index)
        self.assertEqual(result.status, "Insufficient evidence")
        self.assertFalse(result.source_url)

    def test_empty_claim_is_not_evaluated(self) -> None:
        self.assertEqual(verify_claim("  ", index=self.index).status, "Not evaluated")

    def test_retrieval_failure_does_not_invent_support(self) -> None:
        with patch("codeguard.claim_verification.retrieve_evidence", return_value=[]):
            result = verify_claim("Python lists are mutable.")
        self.assertEqual(result.status, "Insufficient evidence")
        self.assertFalse(result.evidence_text)

    def test_unrecognized_explanatory_sentence_is_not_evaluated(self) -> None:
        results = verify_explanation("Here is an example.")
        self.assertEqual(results[0].status, "Not evaluated")

    def test_unrecognized_factual_rule_is_insufficient_not_keyword_supported(self) -> None:
        result = verify_claim("The Python function silently makes everything faster.", index=self.index)
        self.assertEqual(result.status, "Insufficient evidence")
        self.assertNotEqual(result.status, "Supported")


if __name__ == "__main__":
    unittest.main()
