"""Transparent claim/evidence features; labels are never inspected here."""

from __future__ import annotations

import re
from typing import Any

import numpy as np
from scipy.sparse import csr_matrix
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.feature_extraction.text import TfidfVectorizer


def _tokens(text: str) -> list[str]:
    return re.findall(r"\b\w+\b", (text or "").casefold())


def pair_text(record: dict[str, Any]) -> str:
    """Join input text fields; no label or label-derived feature is used."""
    return f"claim: {record.get('claim', '')} evidence: {record.get('evidence', '')}"


class TfidfPairFeatures(TransformerMixin, BaseEstimator):
    """Word unigram/bigram TF-IDF over claim plus retrieved evidence."""

    def __init__(self, ngram_range: tuple[int, int] = (1, 2)):
        self.ngram_range = ngram_range
        self.vectorizer: TfidfVectorizer | None = None

    def fit(self, records: list[dict[str, Any]], y: Any = None) -> "TfidfPairFeatures":
        self.vectorizer = TfidfVectorizer(ngram_range=self.ngram_range, sublinear_tf=True)
        self.vectorizer.fit([pair_text(record) for record in records])
        return self

    def transform(self, records: list[dict[str, Any]]):
        if self.vectorizer is None:
            raise RuntimeError("TF-IDF features have not been fitted.")
        return self.vectorizer.transform([pair_text(record) for record in records])

    def get_feature_names_out(self, input_features: Any = None) -> np.ndarray:
        if self.vectorizer is None:
            raise RuntimeError("TF-IDF features have not been fitted.")
        return self.vectorizer.get_feature_names_out()


class NumericPairFeatures(TransformerMixin, BaseEstimator):
    """Claim/evidence word counts, lexical overlap, and pair TF-IDF cosine."""

    feature_names = np.array(["claim_length_words", "evidence_length_words", "keyword_overlap", "tfidf_similarity"])

    def fit(self, records: list[dict[str, Any]], y: Any = None) -> "NumericPairFeatures":
        return self

    def transform(self, records: list[dict[str, Any]]):
        rows = []
        for record in records:
            claim = str(record.get("claim", ""))
            evidence = str(record.get("evidence", ""))
            claim_tokens = _tokens(claim)
            evidence_tokens = set(_tokens(evidence))
            overlap = len(set(claim_tokens) & evidence_tokens) / len(set(claim_tokens)) if claim_tokens else 0.0
            similarity = record.get("tfidf_similarity")
            if similarity in (None, ""):
                similarity = 0.0
            try:
                similarity = float(similarity)
            except (TypeError, ValueError):
                similarity = 0.0
            rows.append([len(claim_tokens), len(_tokens(evidence)), overlap, similarity])
        return csr_matrix(np.asarray(rows, dtype=np.float64).reshape((-1, 4)))

    def get_feature_names_out(self, input_features: Any = None) -> np.ndarray:
        return self.feature_names.copy()
