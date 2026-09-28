"""Build and inspect a provenance-preserving, explicitly synthetic pilot set."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import csv
import hashlib
import json
from pathlib import Path
import random
import re
from difflib import SequenceMatcher
from typing import Any

from codeguard.claim_verification import verify_claim


PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_ML_DIR = PROJECT_ROOT / "data" / "ml"
DEFAULT_CORPUS_PATH = Path(__file__).resolve().parents[1] / "corpus" / "python_docs.json"
LABELS = ("SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE")
DATASET_VERSION = "1.0.0-synthetic-pilot"
RANDOM_SEED = 42
CSV_FIELDS = (
    "claim", "evidence", "label", "data_origin", "claim_length", "evidence_length",
    "tfidf_similarity", "keyword_overlap", "fact_key", "question_context",
    "source", "title", "source_url", "source_section", "evidence_chunk_id",
    "leakage_group", "label_reason",
)

# Each positive/negative pair is derived from one of the verifier's recognized
# fact keys. The wording below is generated instructional data, not a human corpus.
RULE_CLAIM_PAIRS = {
    "list_mutability": ("Python lists are mutable.", "Python lists are immutable."),
    "tuple_mutability": ("Python tuples are immutable.", "Python tuples are mutable."),
    "dict_insertion_order": (
        "Python dictionaries preserve insertion order.",
        "Python dictionaries do not preserve insertion order.",
    ),
    "set_insertion_order": ("Python sets are unordered.", "Python sets preserve insertion order."),
    "sorted_stability": ("Python sorted is stable.", "Python sorted is unstable."),
}

# The curated corpus does not contain propositions about these topics. These
# are labeled only as not established by this small corpus, not as false claims.
OUT_OF_SCOPE_CLAIMS = (
    "An exhausted Python generator can be restarted to yield its values again.",
    "Python strings can be modified in place after creation.",
    "Python floating point values always represent decimal fractions exactly.",
    "Python functions are memoized automatically after their first call.",
    "Every Python dictionary operation is thread safe in every implementation.",
)


def _normalized(text: str) -> str:
    return re.sub(r"\W+", " ", (text or "").casefold()).strip()


def _lexical_overlap(claim: str, evidence: str) -> float:
    claim_terms = set(_normalized(claim).split())
    evidence_terms = set(_normalized(evidence).split())
    if not claim_terms:
        return 0.0
    return len(claim_terms & evidence_terms) / len(claim_terms)


def _row(claim: str, result: Any, label: str, *, fact_key: str, leakage_group: str, reason: str) -> dict[str, Any]:
    evidence = result.evidence_text or ""
    return {
        "claim": claim,
        "evidence": evidence,
        "label": label,
        "data_origin": "synthetic",
        "claim_length": len(claim.split()),
        "evidence_length": len(evidence.split()),
        "tfidf_similarity": result.retrieval_score,
        "keyword_overlap": round(_lexical_overlap(claim, evidence), 6),
        "fact_key": fact_key,
        "question_context": f"Classify the claim using this Python documentation passage ({result.title or 'no passage retrieved'}).",
        "source": result.source,
        "title": result.title,
        "source_url": result.source_url,
        "source_section": "",
        "evidence_chunk_id": result.evidence_chunk_id,
        "leakage_group": leakage_group,
        "label_reason": reason,
    }


def validate_records(records: list[dict[str, Any]]) -> list[str]:
    """Return validation errors without silently changing submitted records."""
    errors: list[str] = []
    for index, record in enumerate(records):
        prefix = f"record {index}"
        for field in ("claim", "label", "data_origin"):
            if not isinstance(record.get(field), str) or not record[field].strip():
                errors.append(f"{prefix}: {field} must be a non-empty string")
        if record.get("label") not in LABELS:
            errors.append(f"{prefix}: unsupported label {record.get('label')!r}")
        if not isinstance(record.get("evidence"), str) or (not record["evidence"].strip() and record.get("label") != "INSUFFICIENT_EVIDENCE"):
            errors.append(f"{prefix}: evidence must be present except for insufficient-evidence records with no retrieved passage")
        if record.get("data_origin") not in {"synthetic", "manually_verified"}:
            errors.append(f"{prefix}: unsupported data_origin {record.get('data_origin')!r}")
        if not str(record.get("leakage_group", "")).strip():
            errors.append(f"{prefix}: leakage_group is required")
    return errors


def remove_exact_duplicates(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Deduplicate normalized claim/evidence pairs; reject conflicting labels."""
    unique: list[dict[str, Any]] = []
    seen: dict[tuple[str, str], str] = {}
    removed = 0
    for record in records:
        key = (_normalized(record.get("claim", "")), _normalized(record.get("evidence", "")))
        label = record.get("label", "")
        if key in seen:
            if seen[key] != label:
                raise ValueError("Exact claim/evidence duplicate has conflicting labels.")
            removed += 1
            continue
        seen[key] = label
        unique.append(dict(record))
    return unique, removed


def detect_near_duplicates(
    records: list[dict[str, Any]], *, claim_threshold: float = 0.92, evidence_threshold: float = 0.90
) -> list[dict[str, Any]]:
    """Find likely paraphrase leakage candidates using transparent string similarity."""
    matches = []
    for left in range(len(records)):
        for right in range(left + 1, len(records)):
            claim_score = SequenceMatcher(None, _normalized(records[left]["claim"]), _normalized(records[right]["claim"])).ratio()
            evidence_score = SequenceMatcher(None, _normalized(records[left]["evidence"]), _normalized(records[right]["evidence"])).ratio()
            if claim_score >= claim_threshold and evidence_score >= evidence_threshold:
                matches.append({"left_index": left, "right_index": right, "claim_similarity": round(claim_score, 4), "evidence_similarity": round(evidence_score, 4)})
    return matches


def split_by_leakage_group(records: list[dict[str, Any]], seed: int = RANDOM_SEED) -> dict[str, list[dict[str, Any]]]:
    """Create deterministic group-disjoint splits; small data forces 60/20/20."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        groups.setdefault(record["leakage_group"], []).append(record)
    # Hold out one supported/contradicted proposition pair and one insufficient
    # topic group each, ensuring all labels exist in validation and test.
    fact_groups = sorted(group for group, rows in groups.items() if any(row["label"] in {"SUPPORTED", "CONTRADICTED"} for row in rows))
    insufficient_groups = sorted(group for group, rows in groups.items() if all(row["label"] == "INSUFFICIENT_EVIDENCE" for row in rows))
    rng = random.Random(seed)
    rng.shuffle(fact_groups)
    rng.shuffle(insufficient_groups)
    if len(fact_groups) < 3 or len(insufficient_groups) < 3:
        raise ValueError("At least three independent groups of recognized facts and out-of-scope topics are required for leakage-safe train/validation/test splits.")
    assignment: dict[str, str] = {}
    for ordered in (fact_groups, insufficient_groups):
        for group in ordered[:-2]:
            assignment[group] = "train"
        assignment[ordered[-2]] = "validation"
        assignment[ordered[-1]] = "test"
    split = {name: [] for name in ("train", "validation", "test")}
    for group, rows in groups.items():
        split[assignment[group]].extend(rows)
    for rows in split.values():
        rows.sort(key=lambda record: (record["leakage_group"], record["claim"]))
    seen_labels = [set(row["label"] for row in split[name]) for name in split]
    if any(set(LABELS) - labels for labels in seen_labels):
        raise ValueError("Grouped split did not preserve every class in each partition.")
    return split


def class_distribution(records: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(record["label"] for record in records)
    return {label: counts.get(label, 0) for label in LABELS}


def analyze_dataset(records: list[dict[str, Any]], duplicate_count: int = 0) -> dict[str, Any]:
    return {
        "total_records": len(records),
        "class_distribution": class_distribution(records),
        "data_origin_distribution": dict(Counter(row.get("data_origin", "missing") for row in records)),
        "missing_values": {field: sum(row.get(field) in (None, "") for row in records) for field in CSV_FIELDS},
        "exact_duplicate_count_removed": duplicate_count,
        "near_duplicate_pairs_detected": detect_near_duplicates(records),
        "average_claim_length_words": round(sum(len(row["claim"].split()) for row in records) / len(records), 3) if records else None,
        "average_evidence_length_words": round(sum(len(row["evidence"].split()) for row in records) / len(records), 3) if records else None,
    }


def save_records(records: list[dict[str, Any]], path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)


def load_records(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", newline="", encoding="utf-8") as handle:
        records = list(csv.DictReader(handle))
    errors = validate_records(records)
    if errors:
        raise ValueError("Invalid dataset: " + "; ".join(errors[:5]))
    return records


def save_dataset_version(records: list[dict[str, Any]], metadata: dict[str, Any], version: str, base_dir: str | Path = DEFAULT_ML_DIR, splits: dict[str, list[dict[str, Any]]] | None = None) -> Path:
    """Save an immutable named CSV/metadata snapshot under data/ml/versions."""
    if not re.fullmatch(r"[A-Za-z0-9._-]+", version):
        raise ValueError("Dataset version may contain only letters, digits, dot, underscore, and hyphen.")
    errors = validate_records(records)
    if errors:
        raise ValueError("Cannot snapshot an invalid dataset: " + "; ".join(errors[:5]))
    target = Path(base_dir) / "versions" / version
    if target.exists():
        raise FileExistsError(f"Dataset version already exists: {version}")
    target.mkdir(parents=True)
    save_records(records, target / "claims.csv")
    for name, rows in (splits or {}).items():
        if name not in {"train", "validation", "test"}:
            raise ValueError(f"Unsupported dataset split name: {name}")
        save_records(rows, target / f"{name}.csv")
    (target / "dataset_metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    return target


def load_dataset_version(version: str, base_dir: str | Path = DEFAULT_ML_DIR) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9._-]+", version):
        raise ValueError("Invalid dataset version name.")
    target = Path(base_dir) / "versions" / version
    records = load_records(target / "claims.csv")
    metadata = json.loads((target / "dataset_metadata.json").read_text(encoding="utf-8"))
    if metadata.get("dataset_version") != version:
        raise ValueError("Dataset version metadata does not match its directory name.")
    return {"records": records, "metadata": metadata}


def _corpus(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_dataset(output_dir: str | Path = DEFAULT_ML_DIR, corpus_path: str | Path = DEFAULT_CORPUS_PATH) -> dict[str, Any]:
    """Build samples from explicit rule outcomes; all generated claims are synthetic."""
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    corpus_path = Path(corpus_path)
    corpus = _corpus(corpus_path)
    records: list[dict[str, Any]] = []
    for fact_key, (supported_claim, contradicted_claim) in RULE_CLAIM_PAIRS.items():
        for claim, expected_label in ((supported_claim, "SUPPORTED"), (contradicted_claim, "CONTRADICTED")):
            result = verify_claim(claim)
            actual = result.status.upper().replace(" ", "_")
            if actual != expected_label:
                raise ValueError(f"The existing verifier returned {result.status!r} for synthetic {fact_key} example; refusing to create an inconsistent label.")
            source_doc_id = result.evidence_chunk_id.split("#", 1)[0]
            source = next((row for row in corpus if row["doc_id"] == source_doc_id), {})
            record = _row(
                claim, result, actual, fact_key=fact_key, leakage_group=f"rule:{fact_key}",
                reason="Synthetic claim wording checked against the existing proposition rule and its retrieved curated corpus fact.",
            )
            record["source_section"] = source.get("section", "")
            records.append(record)
    for index, claim in enumerate(OUT_OF_SCOPE_CLAIMS, start=1):
        result = verify_claim(claim)
        if result.status != "Insufficient evidence":
            raise ValueError("An out-of-scope synthetic example was unexpectedly rule-verifiable; refusing an unsupported insufficient-evidence label.")
        source_doc_id = result.evidence_chunk_id.split("#", 1)[0]
        source = next((row for row in corpus if row["doc_id"] == source_doc_id), {})
        record = _row(
            claim, result, "INSUFFICIENT_EVIDENCE", fact_key="", leakage_group=f"out-of-scope:{index}",
            reason="Synthetic out-of-scope topic; current corpus and explicit verifier rules do not establish this claim. This label does not mean false.",
        )
        record["source_section"] = source.get("section", "")
        records.append(record)

    records, duplicates_removed = remove_exact_duplicates(records)
    errors = validate_records(records)
    if errors:
        raise ValueError("Dataset validation failed: " + "; ".join(errors))
    splits = split_by_leakage_group(records)
    for pair in detect_near_duplicates(records):
        left = records[pair["left_index"]]
        right = records[pair["right_index"]]
        left_split = next(name for name, rows in splits.items() if left in rows)
        right_split = next(name for name, rows in splits.items() if right in rows)
        if left_split != right_split:
            raise ValueError("Detected near-duplicate claim/evidence examples crossed a data split.")
    save_records(records, target / "claims.csv")
    for name, rows in splits.items():
        save_records(rows, target / f"{name}.csv")
    corpus_hash = hashlib.sha256(corpus_path.read_bytes()).hexdigest()
    metadata = {
        "dataset_version": DATASET_VERSION + "-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"),
        "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "random_seed": RANDOM_SEED,
        "total_samples": len(records),
        "samples_per_class": class_distribution(records),
        "data_origins": dict(Counter(row["data_origin"] for row in records)),
        "source_corpus_sha256": corpus_hash,
        "source_corpus_records": len(corpus),
        "label_method": "synthetic templates checked against existing explicit proposition rules; insufficient labels only for topics absent from the current corpus/rules",
        "sampling_method": "One positive and one polarity-conflicting claim for each of the five recognized propositions, plus one independent corpus-out-of-scope topic example for each of five distinct topics. The resulting equal counts are a consequence of concept coverage, not a target class balance or population estimate.",
        "split_strategy": "group-disjoint by proposition or out-of-scope topic; actual proportions 60/20/20 because only five independent groups per label are available",
        "split_samples": {name: len(rows) for name, rows in splits.items()},
        "split_class_distribution": {name: class_distribution(rows) for name, rows in splits.items()},
        "feature_descriptions": {
            "tfidf_text": "Word unigram/bigram TF-IDF over claim concatenated with retrieved evidence; no labels included.",
            "claim_length": "Number of whitespace-delimited words in claim.",
            "evidence_length": "Number of whitespace-delimited words in evidence.",
            "keyword_overlap": "Claim token intersection divided by claim token count.",
            "tfidf_similarity": "Retrieved lexical similarity score from the existing local retrieval index when available.",
        },
        "analysis": analyze_dataset(records, duplicates_removed),
        "limitations": [
            "All records are synthetic; none are human-labeled or independent real-world examples.",
            "Only five independent rule groups and five out-of-scope topics exist; held-out test contains only three records.",
            "Metrics are a pipeline demonstration and must not be generalized to real explanation claims.",
            "Dataset evidence derives from the small existing paraphrased Python documentation corpus.",
        ],
    }
    (target / "dataset_metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    save_dataset_version(records, metadata, metadata["dataset_version"], target, splits)
    return {"records": records, "splits": splits, "metadata": metadata}
