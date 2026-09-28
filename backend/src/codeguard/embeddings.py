"""Small deterministic TF-IDF vector embeddings implemented with the stdlib."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any

from codeguard.ingestion import DEFAULT_CORPUS_PATH, chunk_documents, load_corpus


DEFAULT_INDEX_PATH = Path(__file__).resolve().parents[3] / "data" / "python_docs_tfidf.json"
_TOKEN = re.compile(r"[a-z0-9_]+", re.IGNORECASE)
_ALIASES = {"dict": "dictionary"}
_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "being", "by", "can",
    "do", "does", "for", "from", "has", "have", "in", "is", "it", "its", "of",
    "on", "or", "python", "that", "the", "their", "this", "to", "use", "used",
    "using", "was", "were", "will", "with",
}


def tokenize(text: str) -> list[str]:
    """Normalize words for this corpus's local lexical vector representation."""
    normalized = []
    for raw in _TOKEN.findall(text):
        token = raw.lower()
        if token.endswith("ies") and len(token) > 4:
            token = token[:-3] + "y"
        elif token.endswith("s") and not token.endswith("ss") and len(token) > 3:
            token = token[:-1]
        token = _ALIASES.get(token, token)
        if token not in _STOP_WORDS and len(token) > 1:
            normalized.append(token)
    return normalized


def _vectorize(text: str, idf: dict[str, float]) -> dict[str, float]:
    counts = Counter(tokenize(text))
    weighted = {word: (1.0 + math.log(count)) * idf[word] for word, count in counts.items() if word in idf}
    norm = math.sqrt(sum(value * value for value in weighted.values()))
    return {word: value / norm for word, value in weighted.items()} if norm else {}


def build_vector_index(
    corpus_path: str | Path = DEFAULT_CORPUS_PATH,
    index_path: str | Path | None = DEFAULT_INDEX_PATH,
    *,
    max_words: int = 120,
) -> dict[str, Any]:
    """Ingest docs, create normalized TF-IDF vectors, and optionally save locally."""
    corpus_bytes = Path(corpus_path).read_bytes()
    corpus_hash = hashlib.sha256(corpus_bytes).hexdigest()
    chunks = chunk_documents(load_corpus(corpus_path), max_words=max_words)
    document_frequency: Counter[str] = Counter()
    tokenized = []
    for chunk in chunks:
        words = tokenize(chunk["text"])
        tokenized.append(words)
        document_frequency.update(set(words))
    document_count = len(chunks)
    idf = {
        word: math.log((1 + document_count) / (1 + frequency)) + 1.0
        for word, frequency in document_frequency.items()
    }
    vectors = [_vectorize(" ".join(words), idf) for words in tokenized]
    index = {
        "format_version": 2,
        "corpus_sha256": corpus_hash,
        "idf": idf,
        "chunks": chunks,
        "vectors": vectors,
    }
    if index_path is not None:
        target = Path(index_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    return index


def load_or_build_index(
    index_path: str | Path = DEFAULT_INDEX_PATH,
    corpus_path: str | Path = DEFAULT_CORPUS_PATH,
) -> dict[str, Any]:
    """Read the local vector index, rebuilding it if absent or malformed."""
    target = Path(index_path)
    if target.exists():
        try:
            index = json.loads(target.read_text(encoding="utf-8"))
            corpus_hash = hashlib.sha256(Path(corpus_path).read_bytes()).hexdigest()
            if (
                index.get("format_version") == 2
                and index.get("corpus_sha256") == corpus_hash
                and len(index.get("chunks", [])) == len(index.get("vectors", []))
                and index.get("chunks")
            ):
                return index
        except (OSError, json.JSONDecodeError, AttributeError):
            pass
    return build_vector_index(corpus_path, target)
