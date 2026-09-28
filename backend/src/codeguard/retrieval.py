"""Local top-k documentation retrieval over normalized TF-IDF vectors."""

from __future__ import annotations

from functools import lru_cache
import time
from pathlib import Path
from typing import Any

from codeguard.embeddings import DEFAULT_INDEX_PATH, _vectorize, load_or_build_index


@lru_cache(maxsize=1)
def _default_index() -> dict[str, Any]:
    return load_or_build_index()


def retrieve_evidence(
    claim: str,
    top_k: int = 3,
    *,
    index: dict[str, Any] | None = None,
    index_path: str | Path = DEFAULT_INDEX_PATH,
    min_score: float = 0.0,
) -> list[dict[str, Any]]:
    """Return evidence with source metadata and cosine similarity scores."""
    if not claim or not claim.strip():
        return []
    if top_k < 1:
        raise ValueError("top_k must be at least one.")
    started = time.perf_counter()
    active = index if index is not None else (
        _default_index() if Path(index_path) == DEFAULT_INDEX_PATH else load_or_build_index(index_path)
    )
    query_vector = _vectorize(claim, active["idf"])
    ranked = []
    for chunk, vector in zip(active["chunks"], active["vectors"]):
        score = sum(value * vector.get(word, 0.0) for word, value in query_vector.items())
        if score >= min_score and score > 0:
            ranked.append((score, chunk))
    ranked.sort(key=lambda item: (-item[0], item[1]["chunk_id"]))
    elapsed = time.perf_counter() - started
    return [
        {
            **chunk,
            "retrieval_score": round(score, 6),
            "retrieval_seconds": elapsed,
        }
        for score, chunk in ranked[:top_k]
    ]
