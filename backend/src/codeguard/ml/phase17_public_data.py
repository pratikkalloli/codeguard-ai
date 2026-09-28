"""Phase 17 public-data parsing and transparent code features."""

from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

import pyarrow.parquet as pq


REVISION = "eadf535931451525f3e5621d0f960c240bc62fd9"
DATASET_NAME = "NVIDIA OpenCodeReasoning-2 (Python)"
LICENSE_ALLOWLIST = {"apache-2.0", "mit", "cc-by-4.0"}
SHARD_PATTERN = "train/python/*.parquet"
INPUT_COLUMNS = [
    "id", "question_id", "solution", "pass_rate", "judgement", "source",
    "license", "dataset", "split", "difficulty",
]


def code_features(code: str) -> dict[str, float]:
    """Extract only deterministic code-shape/syntax features; never execute input."""
    text = str(code or "")
    features: dict[str, float] = {
        "code_chars": float(len(text)),
        "code_lines": float(len(text.splitlines())),
        "dangerous_api_mentions": float(len(re.findall(r"\b(eval|exec|__import__)\s*\(", text))),
        "syntax_valid": 0.0,
        "ast_nodes": 0.0,
        "functions": 0.0,
        "classes": 0.0,
        "imports": 0.0,
        "loops": 0.0,
        "branches": 0.0,
        "try_blocks": 0.0,
        "comprehensions": 0.0,
    }
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError, TypeError, MemoryError, RecursionError):
        return features
    nodes = list(ast.walk(tree))
    features.update({
        "syntax_valid": 1.0,
        "ast_nodes": float(len(nodes)),
        "functions": float(sum(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) for n in nodes)),
        "classes": float(sum(isinstance(n, ast.ClassDef) for n in nodes)),
        "imports": float(sum(isinstance(n, (ast.Import, ast.ImportFrom)) for n in nodes)),
        "loops": float(sum(isinstance(n, (ast.For, ast.AsyncFor, ast.While)) for n in nodes)),
        "branches": float(sum(isinstance(n, (ast.If, ast.IfExp, ast.Match)) for n in nodes)),
        "try_blocks": float(sum(isinstance(n, (ast.Try, getattr(ast, "TryStar", ast.Try))) for n in nodes)),
        "comprehensions": float(sum(isinstance(n, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)) for n in nodes)),
    })
    return features


def normalize_license(value: Any) -> str:
    return str(value or "").strip().casefold().replace(" ", "")


def normalized_code_hash(code: str) -> str:
    normalized = "\n".join(line.rstrip() for line in str(code or "").replace("\r\n", "\n").splitlines()).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def iter_raw_rows(raw_root: str | Path) -> Iterable[dict[str, Any]]:
    """Read needed columns in bounded batches from downloaded Parquet shards."""
    root = Path(raw_root)
    files = sorted(root.glob(SHARD_PATTERN))
    if not files:
        raise FileNotFoundError(f"No OpenCodeReasoning-2 Python shards under {root}")
    for file in files:
        parquet = pq.ParquetFile(file)
        available = set(parquet.schema.names)
        columns = [name for name in INPUT_COLUMNS if name in available]
        for batch in parquet.iter_batches(batch_size=512, columns=columns):
            yield from batch.to_pylist()


def preprocess(raw_root: str | Path, output_path: str | Path, report_path: str | Path, sample_path: str | Path) -> dict[str, Any]:
    from collections import Counter

    counts: Counter[str] = Counter()
    licenses: Counter[str] = Counter()
    pass_bins: Counter[str] = Counter()
    seen_rows: set[str] = set()
    seen_codes: set[str] = set()
    samples: list[dict[str, Any]] = []
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as stream:
        for raw in iter_raw_rows(raw_root):
            counts["original_rows"] += 1
            license_name = normalize_license(raw.get("license"))
            licenses[license_name or "missing"] += 1
            if license_name not in LICENSE_ALLOWLIST:
                counts["excluded_license"] += 1
                continue
            code = str(raw.get("solution") or "").strip()
            question_id = str(raw.get("question_id") or raw.get("id") or "").strip()
            if not code:
                counts["excluded_missing_code"] += 1
                continue
            if not question_id:
                counts["excluded_missing_question_id"] += 1
                continue
            try:
                target = float(raw.get("pass_rate"))
            except (TypeError, ValueError):
                target = -1.0
            if not 0.0 <= target <= 1.0:
                counts["excluded_invalid_pass_rate"] += 1
                continue
            code_hash = normalized_code_hash(code)
            row_id = hashlib.sha256(f"{question_id}\0{code_hash}\0{target:.8f}".encode()).hexdigest()
            if row_id in seen_rows:
                counts["excluded_exact_duplicate"] += 1
                continue
            seen_rows.add(row_id)
            if code_hash in seen_codes:
                counts["duplicate_code_different_record"] += 1
            seen_codes.add(code_hash)
            features = code_features(code)
            counts["syntax_invalid"] += int(features["syntax_valid"] == 0)
            record = {
                "record_id": str(raw.get("id") or row_id),
                "question_id": question_id,
                "source": str(raw.get("source") or ""),
                "dataset": str(raw.get("dataset") or ""),
                "source_split": str(raw.get("split") or ""),
                "difficulty": str(raw.get("difficulty") or ""),
                "license": license_name,
                "pass_rate": target,
                "code": code,
                "code_sha256": code_hash,
                "features": features,
            }
            pass_bins[f"{int(target * 10) / 10:.1f}–{min(1.0, int(target * 10) / 10 + .1):.1f}"] += 1
            counts["valid_rows"] += 1
            counts["python_rows"] += 1
            if len(samples) < 8:
                samples.append({key: record[key] for key in ("record_id", "question_id", "source", "dataset", "difficulty", "license", "pass_rate", "code")})
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    report = {
        "dataset_name": DATASET_NAME,
        "dataset_revision": REVISION,
        "target": "execution-derived pass_rate regression; no mapping to CodeGuard labels",
        "input_fields_used": INPUT_COLUMNS,
        "feature_inputs": ["solution code", "source", "upstream dataset", "difficulty"],
        "excluded_fields_to_prevent_leakage": ["pass_rate as feature", "QwQ critique", "generated right/wrong judgement", "R1 explanation"],
        "license_allowlist": sorted(LICENSE_ALLOWLIST),
        "license_counts_before_filtering": dict(licenses),
        "counts": dict(counts),
        "pass_rate_bins": dict(pass_bins),
        "exact_code_hash_groups": len(seen_codes),
        "near_duplicate_detection": "Not run: corpus-level semantic matching is beyond this bounded preprocessing run; question groups and exact normalized-code hashes are retained for split control.",
        "processed_file": str(output),
    }
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_path).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    Path(sample_path).parent.mkdir(parents=True, exist_ok=True)
    Path(sample_path).write_text(json.dumps(samples, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report
