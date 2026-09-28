"""Offline tests for documentation ingestion, local vectors, and evidence retrieval."""

import tempfile
import unittest
from pathlib import Path

from codeguard.embeddings import build_vector_index, load_or_build_index
from codeguard.ingestion import chunk_documents, load_corpus
from codeguard.retrieval import retrieve_evidence


class RetrievalTests(unittest.TestCase):
    def test_documentation_corpus_has_official_source_metadata(self) -> None:
        corpus = load_corpus()
        self.assertGreaterEqual(len(corpus), 10)
        self.assertTrue(all(item["url"].startswith("https://docs.python.org/") for item in corpus))
        self.assertTrue(all(item["title"] and item["section"] and item["source"] for item in corpus))

    def test_chunking_preserves_provenance_and_splits_long_text(self) -> None:
        record = {
            "doc_id": "sample", "source": "Python Software Foundation",
            "title": "Sample", "url": "https://docs.python.org/3/sample.html",
            "section": "Sample section", "text": "One short sentence. " + "word " * 24 + ".",
            "fact_key": "sample_fact", "polarity": True,
        }
        chunks = chunk_documents([record], max_words=20)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(chunk["source"] == record["source"] for chunk in chunks))
        self.assertTrue(all(chunk["url"] == record["url"] for chunk in chunks))
        self.assertTrue(all(chunk["fact_key"] == record["fact_key"] for chunk in chunks))
        self.assertTrue(all(chunk["chunk_id"].startswith("sample#") for chunk in chunks))

    def test_index_is_written_and_loaded_from_local_disk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "vectors.json"
            first = build_vector_index(index_path=path)
            self.assertTrue(path.exists())
            loaded = load_or_build_index(index_path=path)
        self.assertEqual(len(first["chunks"]), len(first["vectors"]))
        self.assertEqual(len(first["chunks"]), len(loaded["chunks"]))
        self.assertTrue(first["vectors"][0])

    def test_retrieval_returns_ranked_text_and_provenance(self) -> None:
        index = build_vector_index(index_path=None)
        results = retrieve_evidence("Python tuples are immutable", index=index, top_k=3)
        self.assertTrue(results)
        self.assertIn("tuple", results[0]["text"].lower())
        for field in ("source", "title", "url", "section", "chunk_id", "retrieval_score"):
            self.assertIn(field, results[0])
        self.assertGreater(results[0]["retrieval_score"], 0)

    def test_empty_query_returns_no_evidence(self) -> None:
        self.assertEqual(retrieve_evidence("  ", index=build_vector_index(index_path=None)), [])


if __name__ == "__main__":
    unittest.main()
