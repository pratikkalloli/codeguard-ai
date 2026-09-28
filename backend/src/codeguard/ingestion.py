"""Load and chunk the project's curated official Python documentation corpus."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any


DEFAULT_CORPUS_PATH = Path(__file__).resolve().parent / "corpus" / "python_docs.json"
_REQUIRED_FIELDS = {"doc_id", "source", "title", "url", "section", "text"}


def load_corpus(path: str | Path = DEFAULT_CORPUS_PATH) -> list[dict[str, Any]]:
    """Load corpus records, validating provenance before they are indexed."""
    records = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError("The documentation corpus must be a JSON array.")
    for index, record in enumerate(records):
        if not isinstance(record, dict) or not _REQUIRED_FIELDS.issubset(record):
            raise ValueError(f"Corpus record {index} is missing required metadata.")
        if not str(record["url"]).startswith("https://docs.python.org/"):
            raise ValueError(f"Corpus record {index} is not from official Python documentation.")
        if not str(record["text"]).strip():
            raise ValueError(f"Corpus record {index} has no documentation text.")
    return records


def _clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text


def chunk_documents(
    records: list[dict[str, Any]], max_words: int = 120
) -> list[dict[str, Any]]:
    """Split each source record at sentence boundaries and carry its provenance."""
    if max_words < 20:
        raise ValueError("max_words must be at least 20.")
    chunks: list[dict[str, Any]] = []
    for record in records:
        text = _clean_text(str(record["text"]))
        sentences = re.split(r"(?<=[.!?])\s+", text)
        bounded_sentences: list[str] = []
        for sentence in sentences:
            words = sentence.split()
            if len(words) > max_words:
                bounded_sentences.extend(
                    " ".join(words[start : start + max_words])
                    for start in range(0, len(words), max_words)
                )
            elif words:
                bounded_sentences.append(sentence)
        groups: list[str] = []
        pending: list[str] = []
        count = 0
        for sentence in bounded_sentences:
            words = sentence.split()
            if pending and count + len(words) > max_words:
                groups.append(" ".join(pending))
                pending, count = [], 0
            pending.extend(words)
            count += len(words)
        if pending:
            groups.append(" ".join(pending))
        for index, content in enumerate(groups, start=1):
            chunk = {
                key: value
                for key, value in record.items()
                if key not in {"text", "doc_id"}
            }
            chunk.update(
                chunk_id=f"{record['doc_id']}#{index}",
                text=content,
            )
            chunks.append(chunk)
    return chunks
