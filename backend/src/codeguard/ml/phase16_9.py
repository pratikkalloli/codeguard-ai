"""Phase 16.9 measured-capacity, quality-gated candidate expansion.

Adds one supported, evidence-backed candidate for inventory-only facts when
the claim survives cross-dataset exact/near-duplicate checks. It never creates
contradicted or insufficient-evidence claims by template.
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from codeguard.ml.phase16 import PHASE16_DIR, ROOT
from codeguard.ml.phase16_5 import (
    DB, OUT, QUEUE, _quality_filter, _text_metrics, export_phase16_5_views,
)
from codeguard.ml.review import initialize_review_db
from codeguard.ml.research_dataset import FIELDS

CAPACITY_OUT = ROOT / "data" / "ml" / "phase16_9"
LICENSE = "Python Software Foundation License Version 2; retain attribution and source URL"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def analyze_capacity() -> dict[str, Any]:
    inventory = _read_csv(OUT / "fact_inventory.csv")
    candidates = _read_csv(OUT / "candidates.csv")
    by_fact: dict[str, list[dict[str, str]]] = {}
    for row in candidates:
        by_fact.setdefault(row.get("fact_key", ""), []).append(row)
    counts = Counter(len(rows) for rows in by_fact.values())
    labels_per_fact = Counter(len({row.get("proposed_label", "") for row in rows}) for rows in by_fact.values())
    inventory_only = [row for row in inventory if row.get("fact_key") not in by_fact]
    internal_urls = {r["source_url"] for r in candidates if r.get("dataset_partition") == "internal"}
    external_urls = {r["source_url"] for r in candidates if r.get("dataset_partition") == "external"}
    proposed = []
    for fact in inventory_only:
        partition = ("internal" if fact["source_url"] in internal_urls else
                     "external" if fact["source_url"] in external_urls else "external")
        key = fact["fact_key"]
        cid = f"cg169-{key}-s"
        proposed.append({
            "id": cid, "review_id": cid, "record_id": cid,
            "claim": fact["canonical_fact"], "fact_key": key,
            "claim_family": fact.get("claim_family", key),
            "proposed_label": "Supported", "dataset_partition": partition,
            "source_url": fact["source_url"], "topic": fact["topic"],
        })
    accepted, excluded = _quality_filter(proposed, candidates)
    return {
        "inventory_fact_count": len(inventory),
        "facts_with_existing_candidates": len(by_fact),
        "facts_without_candidates": len(inventory_only),
        "facts_observed_with_1_candidate": counts.get(1, 0),
        "facts_observed_with_2_candidates": counts.get(2, 0),
        "facts_observed_with_3_candidates": counts.get(3, 0),
        "facts_observed_with_4_or_more_candidates": sum(v for k, v in counts.items() if k >= 4),
        "facts_with_1_distinct_proposed_label": labels_per_fact.get(1, 0),
        "facts_with_2_distinct_proposed_labels": labels_per_fact.get(2, 0),
        "facts_with_3_distinct_proposed_labels": sum(v for k, v in labels_per_fact.items() if k >= 3),
        "existing_candidate_count": len(candidates),
        "new_supported_candidates_passing_dry_run": len(accepted),
        "dry_run_quality_exclusions": len(excluded),
        "measured_capacity_with_dry_run_additions": len(candidates) + len(accepted),
        "capacity_facts_exactly_1_candidate": counts.get(1, 0) + len(accepted),
        "capacity_facts_exactly_2_candidates": counts.get(2, 0),
        "capacity_facts_exactly_3_candidates": counts.get(3, 0),
        "capacity_facts_4_or_more_candidates": sum(v for k, v in counts.items() if k >= 4),
        "capacity_facts_at_least_2_candidates": sum(v for k, v in counts.items() if k >= 2),
        "capacity_facts_at_least_3_candidates": sum(v for k, v in counts.items() if k >= 3),
        "expected_internal_capacity": sum(r.get("dataset_partition") == "internal" for r in candidates) +
            sum(r.get("dataset_partition") == "internal" for r in accepted),
        "expected_external_capacity": sum(r.get("dataset_partition") == "external" for r in candidates) +
            sum(r.get("dataset_partition") == "external" for r in accepted),
        "observed_candidate_count_distribution_per_fact": {str(k): v for k, v in sorted(counts.items())},
        "inventory_only_supported_rows": accepted,
        "excluded_rows": excluded,
    }


def _candidate_row(fact: dict[str, str], partition: str) -> dict[str, str]:
    key = fact["fact_key"]
    cid = f"cg169-{key}-s"
    group = fact.get("source_group") or fact.get("evidence_group") or f"page:{fact['source_url']}"
    return {
        "id": cid, "claim": fact["canonical_fact"], "evidence": fact["evidence_text"],
        "label": "", "data_origin": "synthetic",
        "source_name": "Python Software Foundation documentation",
        "source_url": fact["source_url"], "source_record_id": f"python-docs:{key}",
        "license": fact.get("license") or LICENSE, "topic": fact["topic"], "language": "Python",
        "fact_key": key, "evidence_group": group,
        "provenance": "Synthetic candidate claim reproducing one curated source fact; not a human annotation.",
        "verification_status": "Pending independent source-backed human review",
        "source_title": fact["source_title"], "source_section": fact["section"],
        "claim_family": fact.get("claim_family", key), "review_status": "pending",
        "proposed_label": "Supported", "gold_label": "",
        "data_origin_status": "synthetic_pending_review", "dataset_partition": partition,
        "review_id": cid, "record_id": cid, "split": "unassigned",
        "batch_id": "external_review_pool" if partition == "external" else "phase16_9_internal",
        "source_group": group, "review_priority": "phase16_9_source_fact",
        "review_mode": "", "source_verified": "", "reviewer_A_id": "",
        "reviewer_A_label": "", "reviewer_A_timestamp": "", "reviewer_B_id": "",
        "reviewer_B_label": "", "reviewer_B_timestamp": "", "adjudicator_id": "",
        "final_adjudicated_label": "", "adjudication_timestamp": "",
    }


def build_phase16_9() -> dict[str, Any]:
    """Append only quality-passing, stable-ID candidates; preserve review data."""
    CAPACITY_OUT.mkdir(parents=True, exist_ok=True)
    capacity = analyze_capacity()
    capacity_snapshot = {k: v for k, v in capacity.items()
                         if k not in {"inventory_only_supported_rows", "excluded_rows"}}
    capacity_path = CAPACITY_OUT / "initial_capacity_analysis.json"
    if not capacity_path.exists():
        capacity_path.write_text(json.dumps(capacity_snapshot, indent=2), encoding="utf-8")
    initial_capacity = json.loads(capacity_path.read_text(encoding="utf-8"))
    inventory = _read_csv(OUT / "fact_inventory.csv")
    existing = _read_csv(QUEUE)
    existing_keys = {row.get("fact_key", "") for row in existing}
    existing_ids = {row.get("review_id", "") for row in existing}
    current_candidates = _read_csv(OUT / "candidates.csv")
    url_partitions: dict[str, str] = {}
    for row in current_candidates:
        url = row.get("source_url", "")
        partition = row.get("dataset_partition", "")
        if url and partition:
            url_partitions[url] = partition
    generated = []
    for fact in inventory:
        if fact.get("fact_key") in existing_keys:
            continue
        partition = url_partitions.get(fact["source_url"], "external")
        generated.append(_candidate_row(fact, partition))
    kept, excluded = _quality_filter(generated, existing)
    fieldnames = list(dict.fromkeys([*(existing[0].keys() if existing else FIELDS),
                                     *(kept[0].keys() if kept else [])]))
    combined = existing + [row for row in kept if row["review_id"] not in existing_ids]
    _write_csv(QUEUE, fieldnames, combined)
    initialize_review_db(QUEUE, DB)  # INSERT OR IGNORE; never overwrites prior review state.
    export_phase16_5_views(DB, OUT)
    master = _read_csv(OUT / "candidates.csv")
    audit = _text_metrics(master)
    internal_urls = {r["source_url"] for r in master if r.get("dataset_partition") == "internal"}
    external_urls = {r["source_url"] for r in master if r.get("dataset_partition") == "external"}
    internal_facts = {r["fact_key"] for r in master if r.get("dataset_partition") == "internal"}
    external_facts = {r["fact_key"] for r in master if r.get("dataset_partition") == "external"}
    phase16_9_present = sum(str(r.get("review_id", "")).startswith("cg169-") for r in master)
    stats = {
        "starting_candidates": initial_capacity["existing_candidate_count"], "final_candidates": len(master),
        "new_candidates_added_in_phase": phase16_9_present,
        "new_candidates_inserted_this_run": len([r for r in kept if r["review_id"] not in existing_ids]),
        "phase16_9_candidates_present": phase16_9_present,
        "internal_candidates": sum(r.get("dataset_partition") == "internal" for r in master),
        "external_candidates": sum(r.get("dataset_partition") == "external" for r in master),
        "proposed_label_distribution_not_gold": dict(Counter(r.get("proposed_label", "") for r in master)),
        "candidate_fact_keys": len({r.get("fact_key") for r in master}),
        "candidate_source_urls": len({r.get("source_url") for r in master}),
        "candidate_source_groups": len({r.get("source_group") or r.get("evidence_group") for r in master}),
        "candidate_topics": len({r.get("topic") for r in master}),
        "pending": sum(r.get("review_status") == "pending" for r in master),
        "reviewed": sum(r.get("review_status") == "reviewed" for r in master),
        "adjudicated": sum(r.get("review_status") == "adjudicated" for r in master),
        "gold_labelled": sum(bool(r.get("gold_label")) or bool(r.get("final_adjudicated_label")) for r in master),
        "exact_duplicate_count": audit["exact_normalized_claim_duplicates"],
        "near_duplicate_pairs_ge_090": audit["near_duplicate_pairs_ge_090"],
        "same_fact_semantic_duplicate_count": audit["same_fact_semantic_duplicates"],
        "new_quality_exclusions": len(excluded),
        "internal_external_url_overlap": len(internal_urls & external_urls),
        "internal_external_fact_overlap": len(internal_facts & external_facts),
        "training_performed": False,
    }
    stats["capacity_analysis"] = initial_capacity
    (CAPACITY_OUT / "capacity_and_build_statistics.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    (CAPACITY_OUT / "duplicate_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    if excluded:
        _write_csv(CAPACITY_OUT / "quality_exclusions.csv", list(dict.fromkeys([*excluded[0].keys(), "exclusion_reason"])), excluded)
    else:
        _write_csv(CAPACITY_OUT / "quality_exclusions.csv", ["id", "fact_key", "claim", "exclusion_reason"], [])
    return {"capacity": capacity, "stats": stats, "new_rows": kept, "excluded": excluded}


if __name__ == "__main__":
    result = build_phase16_9()
    print(json.dumps(result["stats"], indent=2))
