"""Separate local human-review persistence for Phase 16; never used by inference."""
from __future__ import annotations

import csv
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from codeguard.ml.phase16 import PHASE16_DIR, write_csv
from codeguard.ml.research_dataset import FIELDS as CANONICAL_FIELDS, LABELS

REVIEW_STATUSES = {"pending", "reviewed", "disputed", "adjudicated", "rejected"}
DECISIONS = LABELS | {"Reject", "Needs adjudication"}
SLOTS = {"A", "B"}
QUALITY_FLAGS = {"bad_evidence", "incorrect_source", "ambiguous_claim", "duplicate",
                 "malformed_candidate", "insufficient_provenance", "other_quality_issue"}
QUEUE_FIELDS = (
    "review_id", "record_id", "dataset_partition", "claim", "evidence", "proposed_label",
    "reviewer_label", "reviewer_confidence", "reviewer_notes", "source_url", "source_title",
    "fact_key", "evidence_group", "data_origin", "review_status", "adjudication_status",
    "reviewer_A_label", "reviewer_A_id", "reviewer_A_confidence", "reviewer_A_notes",
    "reviewer_B_label", "reviewer_B_id", "reviewer_B_confidence", "reviewer_B_notes",
    "final_adjudicated_label", "adjudicator_id", "adjudicator_notes", "priority_rank", "priority_reason",
)

def _connect(path: str | Path) -> sqlite3.Connection:
    db = sqlite3.connect(str(path), timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    return db

def initialize_review_db(queue_csv: str | Path, database_path: str | Path) -> None:
    queue_csv, database_path = Path(queue_csv), Path(database_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    if not queue_csv.is_file():
        raise FileNotFoundError(f"Review queue is missing: {queue_csv}")
    with queue_csv.open(encoding="utf-8", newline="") as handle:
        source_rows = list(csv.DictReader(handle))
    db = _connect(database_path)
    try:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS review_records (
            review_id TEXT PRIMARY KEY,
            record_json TEXT NOT NULL,
            reviewer_a_decision TEXT NOT NULL DEFAULT '', reviewer_a_id TEXT NOT NULL DEFAULT '',
            reviewer_a_confidence INTEGER, reviewer_a_notes TEXT NOT NULL DEFAULT '',
            reviewer_b_decision TEXT NOT NULL DEFAULT '', reviewer_b_id TEXT NOT NULL DEFAULT '',
            reviewer_b_confidence INTEGER, reviewer_b_notes TEXT NOT NULL DEFAULT '',
            review_status TEXT NOT NULL DEFAULT 'pending', adjudication_status TEXT NOT NULL DEFAULT 'pending',
            verified_label TEXT NOT NULL DEFAULT '', final_adjudicated_label TEXT NOT NULL DEFAULT '',
            adjudicator_id TEXT NOT NULL DEFAULT '', adjudicator_notes TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS review_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            review_id TEXT NOT NULL REFERENCES review_records(review_id),
            reviewer_slot TEXT NOT NULL, reviewer_id TEXT NOT NULL, decision TEXT NOT NULL,
            confidence INTEGER, notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL,
            review_mode TEXT NOT NULL DEFAULT 'evidence_only', source_verified INTEGER NOT NULL DEFAULT 0,
            quality_flags TEXT NOT NULL DEFAULT '[]'
        );
        CREATE TABLE IF NOT EXISTS adjudication_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            review_id TEXT NOT NULL REFERENCES review_records(review_id),
            adjudicator_id TEXT NOT NULL, decision TEXT NOT NULL, notes TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """)
        event_columns={row[1] for row in db.execute("PRAGMA table_info(review_events)")}
        if "review_mode" not in event_columns:
            db.execute("ALTER TABLE review_events ADD COLUMN review_mode TEXT NOT NULL DEFAULT 'evidence_only'")
        if "source_verified" not in event_columns:
            db.execute("ALTER TABLE review_events ADD COLUMN source_verified INTEGER NOT NULL DEFAULT 0")
        if "quality_flags" not in event_columns:
            db.execute("ALTER TABLE review_events ADD COLUMN quality_flags TEXT NOT NULL DEFAULT '[]'")
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with db:
            for row in source_rows:
                review_id = str(row.get("review_id", "")).strip()
                if not review_id:
                    raise ValueError("Every review queue row needs a review_id")
                db.execute("INSERT OR IGNORE INTO review_records(review_id, record_json, updated_at) VALUES (?, ?, ?)",
                           (review_id, json.dumps(row, ensure_ascii=False), now))
    finally:
        db.close()
    export_review_views(database_path, queue_csv.parent.parent)

def review_state(a: str, b: str) -> tuple[str, str, str]:
    """Return (review_status, adjudication_status, verified_label)."""
    a, b = a or "", b or ""
    if not a and not b:
        return "pending", "pending", ""
    if "Needs adjudication" in {a, b}:
        return "disputed", "disagreement", ""
    if not a or not b:
        return "pending", "awaiting_second_review", ""
    if a == b == "Reject":
        return "rejected", "rejected_by_reviewers", ""
    if a == b and a in LABELS:
        # Agreement is a review outcome, not a final gold label. A separate
        # independent adjudication is required before exporting gold data.
        return "reviewed", "agreement_pending_adjudication", ""
    return "disputed", "disagreement", ""

def _validate_reviewer_input(decision: str, confidence: int, notes: str, reviewer_id: str) -> None:
    if decision not in DECISIONS:
        raise ValueError("Choose a canonical label, Reject, or Needs adjudication")
    if not isinstance(confidence, int) or isinstance(confidence, bool) or confidence < 1 or confidence > 5:
        raise ValueError("Confidence must be an integer from 1 to 5")
    if not reviewer_id.strip():
        raise ValueError("Enter your real reviewer identifier; do not use a generated identity")
    if decision in {"Reject", "Needs adjudication"} and not notes.strip():
        raise ValueError("Add notes explaining a rejection or adjudication request")

def _get_row(db: sqlite3.Connection, review_id: str) -> sqlite3.Row:
    row = db.execute("SELECT * FROM review_records WHERE review_id=?", (review_id,)).fetchone()
    if row is None:
        raise KeyError(f"Unknown review ID: {review_id}")
    return row

def save_independent_review(database_path: str | Path, review_id: str, slot: str, *,
                            decision: str, confidence: int, notes: str, reviewer_id: str,
                            review_mode: str = "evidence_only", source_verified: bool = False,
                            quality_flags: list[str] | tuple[str, ...] = ()) -> dict[str, Any]:
    slot = slot.upper()
    if slot not in SLOTS:
        raise ValueError("Reviewer slot must be A or B")
    _validate_reviewer_input(decision, confidence, notes, reviewer_id)
    if review_mode not in {"evidence_only", "source_verified"}:
        raise ValueError("Review mode must be evidence_only or source_verified")
    if not isinstance(source_verified, bool):
        raise ValueError("source_verified must be a boolean")
    if source_verified and review_mode != "source_verified":
        raise ValueError("Source verification flag requires source_verified review mode")
    if isinstance(quality_flags, str) or not set(quality_flags).issubset(QUALITY_FLAGS):
        raise ValueError("Choose quality flags from the supported review issue list")
    db = _connect(database_path)
    try:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with db:
            row = _get_row(db, review_id)
            if row["review_status"] in {"adjudicated", "rejected"}:
                raise ValueError("Final adjudicated/rejected records are immutable; create a reviewed dataset revision to reopen")
            other = "B" if slot == "A" else "A"
            if row[f"reviewer_{slot.lower()}_decision"]:
                raise ValueError(f"Reviewer {slot} has already submitted; create a new review revision to amend it")
            other_id = row[f"reviewer_{other.lower()}_id"]
            if other_id and other_id.casefold() == reviewer_id.strip().casefold():
                raise ValueError("Reviewer A and Reviewer B must be different real people/identifiers")
            column = slot.lower()
            db.execute(f"UPDATE review_records SET reviewer_{column}_decision=?, reviewer_{column}_id=?, reviewer_{column}_confidence=?, reviewer_{column}_notes=?, updated_at=? WHERE review_id=?",
                       (decision, reviewer_id.strip(), confidence, notes.strip(), now, review_id))
            db.execute("INSERT INTO review_events(review_id, reviewer_slot, reviewer_id, decision, confidence, notes, created_at, review_mode, source_verified, quality_flags) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       (review_id, slot, reviewer_id.strip(), decision, confidence, notes.strip(), now, review_mode,
                        int(source_verified), json.dumps(sorted(set(quality_flags)))))
            row = _get_row(db, review_id)
            status, adjudication, verified = review_state(row["reviewer_a_decision"], row["reviewer_b_decision"])
            db.execute("UPDATE review_records SET review_status=?, adjudication_status=?, verified_label=?, final_adjudicated_label='', adjudicator_id='', adjudicator_notes='' WHERE review_id=?",
                       (status, adjudication, verified, review_id))
        result=get_review_record(database_path, review_id)
        export_review_views(database_path, Path(database_path).parent.parent)
        return result
    finally:
        db.close()

def save_adjudication(database_path: str | Path, review_id: str, *, decision: str,
                      notes: str, adjudicator_id: str) -> dict[str, Any]:
    if decision not in (LABELS | {"Reject"}):
        raise ValueError("Adjudication must choose a canonical label or Reject")
    if not notes.strip():
        raise ValueError("Adjudication notes are required")
    if not adjudicator_id.strip():
        raise ValueError("Enter the real adjudicator identifier")
    db = _connect(database_path)
    try:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with db:
            row = _get_row(db, review_id)
            if row["review_status"] not in {"disputed", "reviewed"}:
                raise ValueError("Only independently reviewed or disputed records can be adjudicated")
            reviewer_ids = {row["reviewer_a_id"].casefold(), row["reviewer_b_id"].casefold()} - {""}
            if adjudicator_id.strip().casefold() in reviewer_ids:
                raise ValueError("The adjudicator must be independent from the two reviewers")
            final_label = "" if decision == "Reject" else decision
            final_status = "rejected" if decision == "Reject" else "adjudicated"
            adjudication_status = "rejected_by_adjudicator" if decision == "Reject" else "resolved"
            db.execute("UPDATE review_records SET review_status=?, adjudication_status=?, verified_label=?, final_adjudicated_label=?, adjudicator_id=?, adjudicator_notes=?, updated_at=? WHERE review_id=?",
                       (final_status, adjudication_status, final_label, final_label, adjudicator_id.strip(), notes.strip(), now, review_id))
            db.execute("INSERT INTO adjudication_events(review_id, adjudicator_id, decision, notes, created_at) VALUES (?, ?, ?, ?, ?)",
                       (review_id, adjudicator_id.strip(), decision, notes.strip(), now))
        result=get_review_record(database_path, review_id)
        export_review_views(database_path, Path(database_path).parent.parent)
        return result
    finally:
        db.close()

def get_review_record(database_path: str | Path, review_id: str) -> dict[str, Any]:
    db = _connect(database_path)
    try:
        row = _get_row(db, review_id)
        result = json.loads(row["record_json"])
        a=row["reviewer_a_decision"]; b=row["reviewer_b_decision"]
        latest=a if a and not b else b if b and not a else a if a==b else ""
        latest_confidence=row["reviewer_a_confidence"] if a and not b else row["reviewer_b_confidence"] if b and not a else row["reviewer_a_confidence"] if a==b else ""
        latest_notes=row["reviewer_a_notes"] if a and not b else row["reviewer_b_notes"] if b and not a else row["reviewer_a_notes"] if a==b else ""
        result.update({"review_status":row["review_status"],"adjudication_status":row["adjudication_status"],
            "reviewer_A_label":row["reviewer_a_decision"],"reviewer_A_id":row["reviewer_a_id"],
            "reviewer_A_confidence":row["reviewer_a_confidence"] if row["reviewer_a_confidence"] is not None else "",
            "reviewer_A_notes":row["reviewer_a_notes"],"reviewer_B_label":row["reviewer_b_decision"],
            "reviewer_B_id":row["reviewer_b_id"],
            "reviewer_B_confidence":row["reviewer_b_confidence"] if row["reviewer_b_confidence"] is not None else "",
            "reviewer_B_notes":row["reviewer_b_notes"],"reviewer_label":latest,
            "reviewer_confidence":latest_confidence if latest_confidence is not None else "",
            "reviewer_notes":latest_notes,"verified_label":row["verified_label"],
            "final_adjudicated_label":row["final_adjudicated_label"],"adjudicator_id":row["adjudicator_id"],
            "adjudicator_notes":row["adjudicator_notes"]})
        for slot in ("A","B"):
            event=db.execute("SELECT created_at, review_mode, source_verified, quality_flags FROM review_events WHERE review_id=? AND reviewer_slot=? ORDER BY event_id DESC LIMIT 1",(review_id,slot)).fetchone()
            result[f"reviewer_{slot}_timestamp"]=event["created_at"] if event else ""
            result[f"reviewer_{slot}_mode"]=event["review_mode"] if event else ""
            result[f"reviewer_{slot}_source_verified"]=bool(event["source_verified"]) if event else False
            result[f"reviewer_{slot}_quality_flags"]=json.loads(event["quality_flags"] or "[]") if event else []
        adjudication=db.execute("SELECT created_at FROM adjudication_events WHERE review_id=? ORDER BY event_id DESC LIMIT 1",(review_id,)).fetchone()
        result["adjudication_timestamp"]=adjudication["created_at"] if adjudication else ""
        return result
    finally:
        db.close()

def list_review_records(database_path: str | Path, *, statuses: set[str] | None = None,
                        partition: str | None = None, batch_id: str | None = None) -> list[dict[str, Any]]:
    if statuses is not None and not statuses.issubset(REVIEW_STATUSES):
        raise ValueError("Invalid review status filter")
    db = _connect(database_path)
    try:
        rows = db.execute("SELECT * FROM review_records").fetchall()
        result=[]
        for row in rows:
            item=json.loads(row["record_json"])
            if statuses is not None and row["review_status"] not in statuses: continue
            if partition is not None and item.get("dataset_partition") != partition: continue
            if batch_id is not None and item.get("batch_id", "") != batch_id: continue
            a=row["reviewer_a_decision"]; b=row["reviewer_b_decision"]
            latest=a if a and not b else b if b and not a else a if a==b else ""
            latest_confidence=row["reviewer_a_confidence"] if a and not b else row["reviewer_b_confidence"] if b and not a else row["reviewer_a_confidence"] if a==b else ""
            latest_notes=row["reviewer_a_notes"] if a and not b else row["reviewer_b_notes"] if b and not a else row["reviewer_a_notes"] if a==b else ""
            item.update({"review_status":row["review_status"],"adjudication_status":row["adjudication_status"],
                "reviewer_A_label":row["reviewer_a_decision"],"reviewer_A_id":row["reviewer_a_id"],
                "reviewer_A_confidence":row["reviewer_a_confidence"] if row["reviewer_a_confidence"] is not None else "",
                "reviewer_A_notes":row["reviewer_a_notes"],"reviewer_B_label":row["reviewer_b_decision"],
                "reviewer_B_id":row["reviewer_b_id"],
                "reviewer_B_confidence":row["reviewer_b_confidence"] if row["reviewer_b_confidence"] is not None else "",
                "reviewer_B_notes":row["reviewer_b_notes"],"reviewer_label":latest,
                "reviewer_confidence":latest_confidence if latest_confidence is not None else "",
                "reviewer_notes":latest_notes,"verified_label":row["verified_label"],
                "final_adjudicated_label":row["final_adjudicated_label"],"adjudicator_id":row["adjudicator_id"],
                "adjudicator_notes":row["adjudicator_notes"]})
            for slot in ("A","B"):
                event=db.execute("SELECT created_at, review_mode, source_verified, quality_flags FROM review_events WHERE review_id=? AND reviewer_slot=? ORDER BY event_id DESC LIMIT 1",(row["review_id"],slot)).fetchone()
                item[f"reviewer_{slot}_timestamp"]=event["created_at"] if event else ""
                item[f"reviewer_{slot}_mode"]=event["review_mode"] if event else ""
                item[f"reviewer_{slot}_source_verified"]=bool(event["source_verified"]) if event else False
                item[f"reviewer_{slot}_quality_flags"]=json.loads(event["quality_flags"] or "[]") if event else []
            adjudication=db.execute("SELECT created_at FROM adjudication_events WHERE review_id=? ORDER BY event_id DESC LIMIT 1",(row["review_id"],)).fetchone()
            item["adjudication_timestamp"]=adjudication["created_at"] if adjudication else ""
            result.append(item)
        result.sort(key=lambda r:(int(r.get("priority_rank") or 99),r.get("fact_key",""),r["review_id"]))
        return result
    finally:
        db.close()

def review_counts(database_path: str | Path) -> dict[str, Any]:
    items=list_review_records(database_path)
    reviewed=[r for r in items if r.get("reviewer_A_label") and r.get("reviewer_B_label")]
    agreements=sum(r["reviewer_A_label"]==r["reviewer_B_label"] for r in reviewed)
    disagreements=len(reviewed)-agreements
    return {"total":len(items),"pending":sum(r["review_status"]=="pending" for r in items),
        "reviewed":sum(r["review_status"]=="reviewed" for r in items),
        "disputed":sum(r["review_status"]=="disputed" for r in items),
        "adjudicated":sum(r["review_status"]=="adjudicated" for r in items),
        "rejected":sum(r["review_status"]=="rejected" for r in items),
        "verified_label_count":sum(bool(r.get("final_adjudicated_label")) for r in items),
        "external_pending":sum(r.get("dataset_partition")=="external" and r["review_status"]=="pending" for r in items),
        "agreement_count":agreements,"disagreement_count":disagreements,
        "agreement_rate":agreements/len(reviewed) if reviewed else None}

def export_review_views(database_path: str | Path, phase_dir: str | Path = PHASE16_DIR) -> None:
    phase_dir=Path(phase_dir)
    records=list_review_records(database_path)
    if not records: return
    write_csv(phase_dir/"review"/"review_queue.csv",tuple(records[0].keys()),records)
    internal=[r for r in records if r.get("dataset_partition")=="internal"]
    adjudicated=[r for r in records if r["review_status"]=="adjudicated" and r.get("final_adjudicated_label") in LABELS]
    reviewed=[r for r in internal if r["review_status"]=="reviewed"]
    pending=[r for r in internal if r["review_status"]=="pending"]
    disputed=[r for r in internal if r["review_status"]=="disputed"]
    rejected=[r for r in internal if r["review_status"]=="rejected"]
    verified_fields=tuple(CANONICAL_FIELDS)+("proposed_label","split","origin_bucket","review_status","verified_label","final_adjudicated_label")
    pending_fields=tuple(field for field in CANONICAL_FIELDS if field!="label")+("proposed_label","split","origin_bucket","review_status","final_adjudicated_label")
    def as_pending(r: dict[str,Any]) -> dict[str,Any]:
        base={field:r.get(field,"") for field in CANONICAL_FIELDS if field!="label"}
        return {**base,"proposed_label":r.get("proposed_label",""),"split":r.get("split",""),"origin_bucket":"synthetic_pending_review",
                "review_status":r["review_status"],"final_adjudicated_label":r.get("final_adjudicated_label","")}
    # Compatibility path only: no record may be treated as gold outside the
    # explicitly named adjudicated.csv export.
    write_csv(phase_dir/"processed"/"verified.csv",verified_fields,[])
    write_csv(phase_dir/"processed"/"pending_review.csv",pending_fields,[as_pending(r) for r in pending])
    write_csv(phase_dir/"processed"/"rejected.csv",pending_fields,[as_pending(r) for r in rejected])
    reviewed_fields=tuple(field for field in CANONICAL_FIELDS if field!="label")+("proposed_label","review_status","reviewer_label","reviewer_A_id","reviewer_B_id")
    write_csv(phase_dir/"processed"/"reviewed.csv",reviewed_fields,[
        {**{field:r.get(field,"") for field in CANONICAL_FIELDS if field!="label"},
         "proposed_label":r.get("proposed_label",""),"review_status":r["review_status"],
         "reviewer_label":r.get("reviewer_label",""),"reviewer_A_id":r.get("reviewer_A_id",""),
         "reviewer_B_id":r.get("reviewer_B_id","")} for r in reviewed])
    write_csv(phase_dir/"processed"/"disputed.csv",pending_fields,[as_pending(r) for r in disputed])
    adjudicated_fields=tuple(CANONICAL_FIELDS)+("proposed_label","dataset_partition","review_status","gold_label","adjudicator_id","adjudicator_notes")
    write_csv(phase_dir/"processed"/"adjudicated.csv",adjudicated_fields,[
        {**{field:r.get(field,"") for field in CANONICAL_FIELDS},
         "label":r.get("final_adjudicated_label",""),"proposed_label":r.get("proposed_label",""),
         "dataset_partition":r.get("dataset_partition","internal"),
         "review_status":"adjudicated","gold_label":r.get("final_adjudicated_label",""),
         "adjudicator_id":r.get("adjudicator_id",""),"adjudicator_notes":r.get("adjudicator_notes","")}
        for r in adjudicated])
    external=[r for r in records if r.get("dataset_partition")=="external"]
    external_fields=("record_id","claim","evidence","gold_label","source_name","source_url","fact_key",
        "evidence_group","review_status","data_origin","license","provenance","source_title","source_section","topic")
    write_csv(phase_dir/"external"/"external_test.csv",external_fields,[
        {"record_id":r["record_id"],"claim":r["claim"],"evidence":r["evidence"],
         "gold_label":"","source_name":r["source_name"],"source_url":r["source_url"],
         "fact_key":r["fact_key"],"evidence_group":r["evidence_group"],"review_status":r["review_status"],
         "data_origin":"synthetic_reviewed" if r["review_status"] in {"reviewed","adjudicated"} else "synthetic_pending_review",
         "license":r["license"],"provenance":r["provenance"],"source_title":r["source_title"],
         "source_section":r["source_section"],"topic":r["topic"]}
        for r in external])
    summary={"counts":review_counts(database_path),"origin_composition":{
        "public_verified":0,"manually_verified":0,
        "synthetic_pending_review":sum(str(r.get("data_origin","")).startswith("synthetic") and r["review_status"] not in {"reviewed","adjudicated","rejected"} for r in records),
        "synthetic_reviewed":sum(str(r.get("data_origin","")).startswith("synthetic") and r["review_status"] in {"reviewed","adjudicated"} for r in records)},
        "review_states_are_human_supplied":True}
    (phase_dir/"review"/"review_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    # Phase 16.5 exports are refreshed after every actual review/adjudication
    # event. Import locally to keep this module's dependency graph acyclic.
    phase165_dir=phase_dir.parent/"phase16_5"
    if (phase165_dir/"candidate_statistics.json").is_file():
        from codeguard.ml.phase16_5 import export_phase16_5_views
        export_phase16_5_views(database_path,phase165_dir)
