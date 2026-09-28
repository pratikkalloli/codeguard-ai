"""Build the isolated Phase 15 research dataset; never trains or touches models."""
from __future__ import annotations

import csv
import hashlib
import json
import random
import re
import unicodedata
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from codeguard.ml.final_dataset import FINAL_DIR, build_final_dataset

ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DIR = ROOT / "data" / "ml" / "research_dataset"
LABELS = {"Supported", "Contradicted", "Insufficient Evidence"}
FIELDS = ("id", "claim", "evidence", "label", "data_origin", "source_name", "source_url",
          "source_record_id", "license", "topic", "language", "fact_key", "evidence_group",
          "provenance", "verification_status", "source_title", "source_section", "claim_family",
          "review_status")
DOC = "https://docs.python.org/3/tutorial/controlflow.html"
CLASSES = "https://docs.python.org/3/tutorial/classes.html"
BUILTINS = "https://docs.python.org/3/library/functions.html"
STD = "https://docs.python.org/3/library/stdtypes.html"
DATA_MODEL = "https://docs.python.org/3/reference/datamodel.html"
LICENSE = "Python Software Foundation License Version 2; source attribution and URL retained"

# Compact, source-grounded propositions. Wording is intentionally synthetic and
# MUST be reviewed by a Python/domain expert before it can be treated as labels.
FACTS = [
 ("range_stop", "range", DOC, "The given end point is never part of the generated sequence; range(10) generates 10 values.", "Python range(10) excludes 10.", "Python range(10) includes 10.", "Control flow — range"),
 ("for_else_break", "loops", DOC, "The else clause executes after the for loop completes normally, but not when the loop is terminated by a break statement.", "A for-else suite is skipped when the loop exits with break.", "A for-else suite runs after a break exits the loop.", "Control flow — for statements"),
 ("default_once", "functions", DOC, "The default value is evaluated only once. This makes a difference when the default is a mutable object such as a list or dictionary.", "A mutable default argument is evaluated once when its function is defined.", "A mutable default argument is freshly evaluated on every function call.", "Control flow — default argument values"),
 ("fallthrough_none", "functions", DOC, "If a function definition does not include a return statement, it returns None.", "A Python function that reaches its end without return returns None.", "A Python function that reaches its end without return returns zero.", "Control flow — defining functions"),
 ("function_scope", "functions", DOC, "When a variable is used in a function, the value is looked up in the local symbol table; the local symbol table is populated from the function's parameters and variables assigned in the function body.", "A name assigned in a function body is local by default.", "A name assigned in a function body is global by default.", "Control flow — defining functions"),
 ("iterator_protocol", "iteration", CLASSES, "The for statement calls iter() on the container object. The function returns an iterator object that defines __next__(), which accesses elements one at a time. When there are no more elements, __next__() raises StopIteration.", "A for loop obtains an iterator and advances it until StopIteration.", "A for loop must index each container and does not use an iterator.", "Classes — iterators"),
 ("generator_resume", "iteration", CLASSES, "Each time next() is called on it, the generator resumes where it left off (it remembers all the data values and which statement was last executed).", "A generator resumes from its suspended state after yield.", "A generator restarts its function from the beginning after every yield.", "Classes — generators"),
 ("generator_expression", "iteration", CLASSES, "Generator expressions are more memory friendly than equivalent list comprehensions.", "A generator expression avoids eagerly building the corresponding list.", "A generator expression always builds a full list before iteration.", "Classes — generator expressions"),
 ("string_immutable", "strings", STD, "Strings are immutable sequences of Unicode code points.", "Python strings are immutable.", "Python strings are mutable.", "Built-in types — text sequence type str"),
 ("str_index", "strings", STD, "The items of a string are Unicode code points. There is no separate character type; a character is represented by a string of length 1.", "Indexing a Python string produces a string of length one.", "Indexing a Python string produces a separate character type.", "Built-in types — text sequence type str"),
 ("bool_int", "built-ins", BUILTINS, "bool is a subclass of int (see Numeric Types — int, float, complex). In many numeric contexts, False and True behave like 0 and 1, respectively.", "bool is a subclass of int in Python.", "bool is not a subclass of int in Python.", "Built-in functions — bool"),
 ("all_empty", "built-ins", BUILTINS, "Return True if all elements of the iterable are true (or if the iterable is empty).", "all([]) returns True.", "all([]) returns False.", "Built-in functions — all"),
 ("any_empty", "built-ins", BUILTINS, "Return True if any element of the iterable is true. If the iterable is empty, return False.", "any([]) returns False.", "any([]) returns True.", "Built-in functions — any"),
 ("enumerate_tuple", "built-ins", BUILTINS, "An enumerate object yields pairs containing a count (from start, which defaults to zero) and a value obtained from iterating over iterable.", "Each enumerate result is a pair containing a count and an item.", "enumerate returns only the current item and never a count.", "Built-in functions — enumerate"),
 ("range_constant_memory", "sequences", STD, "The range type represents an immutable sequence of numbers and is commonly used for looping a specific number of times. The advantage of the range type over a regular list is that a range object will always take the same (small) amount of memory, no matter the size of the range it represents.", "A range object uses a small, constant amount of memory as its represented sequence grows.", "A range object stores every represented integer in memory.", "Built-in types — range"),
]

EXTERNAL_FACTS = [
 ("datamodel_bool", "The __bool__() method should return False or True.", "Python's __bool__ method should return a Boolean value.", "Python's __bool__ method should return a string.", "Data model — emulating numeric types"),
 ("datamodel_len", "__len__() should return an integer greater than or equal to zero.", "A Python __len__ method must return a nonnegative integer.", "A Python __len__ method may return a negative integer.", "Data model — emulating container types"),
]
IE_CLAIMS = {
 "range_stop": "The range constructor accepts an arbitrary number of keyword-only arguments.",
 "for_else_break": "A for-else suite runs a finalizer in a background thread after the loop ends.",
 "default_once": "Python stores every default argument object in a function's __defaults__ tuple.",
 "fallthrough_none": "A function's implicit return value is written into a CPU register chosen by the interpreter.",
 "function_scope": "Python function locals are serialized to disk whenever the function returns.",
 "iterator_protocol": "Calling iter() on every iterator resets it to its first element.",
}

def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(text or "")).casefold()).strip()

def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

def _write(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader(); writer.writerows(rows)

def validate_rows(rows: list[dict[str, Any]]) -> None:
    seen: dict[tuple[str, str], str] = {}
    claim_labels: dict[str, set[str]] = defaultdict(set)
    for i, row in enumerate(rows):
        missing = [field for field in FIELDS if field not in row or row[field] is None or not str(row[field]).strip()]
        if missing:
            raise ValueError(f"row {i} missing required fields: {', '.join(missing)}")
        if row["label"] not in LABELS:
            raise ValueError(f"row {i} has invalid label {row['label']!r}")
        if row["data_origin"] not in {"public", "manually_verified", "synthetic"}:
            raise ValueError(f"row {i} has invalid data_origin")
        if not row["source_url"].startswith("https://") or not row["source_record_id"]:
            raise ValueError(f"row {i} has incomplete source provenance")
        if "License" not in row["license"] or not row["provenance"]:
            raise ValueError(f"row {i} has incomplete license/provenance")
        if row["label"] != "Insufficient Evidence" and not row["evidence"].strip():
            raise ValueError(f"row {i} has a factual label without evidence")
        exact = (normalize(row["claim"]), normalize(row["evidence"]))
        prior = seen.get(exact)
        if prior is not None:
            if prior != row["label"]:
                raise ValueError(f"conflicting exact duplicate labels: {row['claim']}")
            raise ValueError(f"duplicate claim/evidence row: {row['claim']}")
        seen[exact] = row["label"]
        claim_labels[normalize(row["claim"])].add(row["label"])
    conflicts = [claim for claim, labels in claim_labels.items() if len(labels) > 1]
    if conflicts:
        raise ValueError(f"normalized claims have conflicting labels: {conflicts[:5]}")

def _record(idx: int, claim: str, evidence: str, label: str, *, key: str, url: str, section: str,
            title: str, topic: str, family: str, origin: str = "synthetic", group: str | None = None,
            status: str = "Source checked; independent human expert review pending") -> dict[str, str]:
    group = group or "page:" + url
    return {"id": f"cg-rd-{idx:04d}", "claim": claim, "evidence": evidence, "label": label,
        "data_origin": origin, "source_name": "Python documentation (Python Software Foundation)",
        "source_url": url, "source_record_id": f"python-docs:{key}", "license": LICENSE,
        "topic": topic, "language": "Python", "fact_key": key, "evidence_group": group,
        "provenance": "Synthetic claim wording grounded in the linked official documentation excerpt; not a human annotation.",
        "verification_status": status, "source_title": title, "source_section": section,
        "claim_family": family, "review_status": "pending_expert_review"}

def _split(rows: list[dict[str, str]], seed: int = 15015) -> dict[str, list[dict[str, str]]]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row["evidence_group"]].append(row)
    required = LABELS
    names = list(groups)
    best = None; best_score = float("inf")
    target = {"train": .70, "validation": .15, "test": .15}
    for trial in range(50000):
        order = names.copy(); random.Random(seed + trial).shuffle(order)
        assign = random.Random(seed * 3 + trial).choices(list(target), weights=[70,15,15], k=len(order))
        candidate = {k: [] for k in target}
        for name, split_name in zip(order, assign): candidate[split_name].extend(groups[name])
        if any({r["label"] for r in candidate[k]} != required for k in candidate): continue
        score = sum(abs(len(candidate[k]) / len(rows) - target[k]) for k in target)
        if score < best_score: best, best_score = candidate, score
    if best is None: raise ValueError("Could not form three group-isolated splits with every class")
    for values in best.values(): values.sort(key=lambda r: r["id"])
    return best

def _distribution(rows: list[dict[str, str]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(r[field] for r in rows).items()))

def build_research_dataset(output_dir: str | Path = DEFAULT_DIR) -> dict[str, Any]:
    out = Path(output_dir); raw = out / "raw"; processed = out / "processed"; reports = out / "reports"
    for directory in (raw, processed, reports): directory.mkdir(parents=True, exist_ok=True)
    # Reuse the prior candidate through a temporary directory, leaving it untouched.
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        prior = build_final_dataset(output_dir=Path(tmp) / "prior")
        prior_rows = prior["records"]
    rows: list[dict[str, str]] = []; idx = 0
    label_map = {"SUPPORTED":"Supported", "CONTRADICTED":"Contradicted", "INSUFFICIENT_EVIDENCE":"Insufficient Evidence"}
    excluded_source_less = 0
    for old in prior_rows:
        # Do not turn a source-less legacy pilot record into a sourced example.
        if not old.get("source_url") or not old.get("evidence", "").strip():
            excluded_source_less += 1
            continue
        idx += 1
        url = old.get("source_url") or "https://docs.python.org/3/"
        rows.append(_record(idx, old["claim"], old.get("evidence", ""), label_map[old["label"]],
            key=old["fact_key"], url=url, section=old.get("source_section") or "Existing pilot; source excerpt unavailable",
            title=old.get("title") or "Python documentation", topic=old["topic"], family=old["fact_key"],
            status="Legacy synthetic pilot record; expert review pending"))
    fact_rows: list[dict[str, Any]] = []
    for key, topic, url, evidence, positive, negative, section in FACTS:
        title = "Python Library Reference" if "library/" in url or "library/" in url else "The Python Tutorial"
        for claim, label in ((positive,"Supported"),(negative,"Contradicted")):
            idx += 1; row = _record(idx, claim, evidence, label, key=key, url=url, section=section,
                title=title, topic=topic, family=key)
            rows.append(row); fact_rows.append({"fact_key":key,"topic":topic,"url":url,"section":section,
                "evidence":evidence,"supported_claim":positive,"contradicted_claim":negative})
    # An insufficient-evidence label is scoped to the specific unrelated excerpt,
    # never a claim that the claim is false.
    for key, topic, url, evidence, *_rest, section in FACTS[:6]:
        idx += 1
        claim = IE_CLAIMS[key]
        rows.append(_record(idx, claim, evidence, "Insufficient Evidence", key=f"out_of_scope_{key}", url=url,
            section=section, title="Python documentation excerpt", topic=topic, family=f"ie_{key}"))
    validate_rows(rows)
    # Exact/near duplicate analysis. For split safety, the full source page is a group.
    near = []
    for i, a in enumerate(rows):
        for j in range(i+1, len(rows)):
            b = rows[j]
            sim = SequenceMatcher(None, normalize(a["claim"]), normalize(b["claim"])).ratio()
            # At .90 this flags near-identical claims while avoiding false
            # cross-topic template matches such as lists vs strings mutability.
            if sim >= .90:
                near.append({"left_id":a["id"],"right_id":b["id"],"similarity":round(sim,4),
                             "same_group":a["evidence_group"] == b["evidence_group"]})
                if a["evidence_group"] != b["evidence_group"]:
                    raise ValueError(f"Near-duplicate leakage across evidence groups: {a['id']} / {b['id']}")
    splits = _split(rows)
    group_sets = {name:{r["evidence_group"] for r in values} for name,values in splits.items()}
    if group_sets["train"] & group_sets["validation"] or group_sets["train"] & group_sets["test"] or group_sets["validation"] & group_sets["test"]:
        raise ValueError("Evidence group leakage between train/validation/test")
    ext: list[dict[str,str]] = []
    external_url = DATA_MODEL
    for key,evidence,pos,neg,section in EXTERNAL_FACTS:
        for claim,label in ((pos,"Supported"),(neg,"Contradicted")):
            idx+=1; ext.append(_record(idx,claim,evidence,label,key=key,url=external_url,section=section,
                title="Python Data Model",topic="data model",family=key,
                status="Held out by documentation page; synthetic and awaiting independent review"))
    for n in range(2):
        idx+=1; ext.append(_record(idx,
            f"Python data model fact {n+1} is established by this excerpt, although it concerns a different special method.",
            EXTERNAL_FACTS[n][1], "Insufficient Evidence", key=f"external_ie_{n+1}",url=external_url,
            section=EXTERNAL_FACTS[n][4],title="Python Data Model",topic="data model",family=f"external_ie_{n+1}",
            status="Held out by documentation page; synthetic and awaiting independent review"))
    validate_rows(ext)
    internal_urls = {r["source_url"] for r in rows}
    internal_groups = {r["evidence_group"] for r in rows}
    if any(r["source_url"] in internal_urls or r["evidence_group"] in internal_groups for r in ext):
        raise ValueError("External test is not source-independent from internal data")
    _write(processed/"dataset.csv", rows)
    for name, values in splits.items(): _write(processed/f"{name}.csv", values)
    _write(processed/"external_test.csv", ext)
    (raw/"source_facts.json").write_text(json.dumps(fact_rows,indent=2,ensure_ascii=False),encoding="utf-8")
    metadata = {"dataset_name":"CodeGuard AI programming claim-evidence research dataset","version":"0.1.0",
        "seed":15015,"total_records":len(rows),"external_test_records":len(ext),"label_set":sorted(LABELS),
        "records_per_class":_distribution(rows,"label"),"records_per_topic":_distribution(rows,"topic"),
        "records_per_origin":_distribution(rows,"data_origin"),"split_sizes":{k:len(v) for k,v in splits.items()},
        "split_class_distribution":{k:_distribution(v,"label") for k,v in splits.items()},
        "external_class_distribution":_distribution(ext,"label"),"split_method":"Seeded randomized grouped holdout by complete official documentation URL; all labels required in each internal split.",
        "group_key":"evidence_group (entire source URL)","external_isolation":"Python Data Model reference page is excluded from all internal partitions.",
        "human_verified_records":0,"manual_review_required":True,"ready_for_model_training":False,
        "quality":{"exact_duplicate_count":0,"normalized_claim_label_conflicts":0,"near_duplicate_pair_count":len(near),
                   "near_duplicate_pairs":near,"all_rows_have_provenance":True,"all_records_synthetic":True,
                   "source_group_leakage":False,"external_source_overlap":False,
                   "source_less_legacy_records_excluded":excluded_source_less},
        "limitations":["All records are synthetic wording and none has independent human expert verification.",
          "No compatible programming-domain public dataset with claim, evidence and all three labels was identified for inclusion.",
          "Labels are generated from short Python documentation excerpts; contradiction pairs are controlled and may be lexically easy.",
          "Insufficient Evidence means only that the supplied excerpt does not establish the claim.",
          "External test is page-held-out but synthetic, small, and not an independent human benchmark.",
          "Source page grouping is conservative and can produce proportions unlike 70/15/15."]}
    (out/"dataset_metadata.json").write_text(json.dumps(metadata,indent=2,ensure_ascii=False),encoding="utf-8")
    sources = {"used_public_datasets":[],"used_sources":[{"name":"Python Documentation","url":"https://docs.python.org/3/",
        "publisher":"Python Software Foundation","license":"Python Software Foundation License Version 2",
        "license_url":"https://docs.python.org/3/license.html","use":"Short evidence passages and source-backed synthetic claims; URLs and sections retained.",
        "redistributed_dataset":False}],"candidates":[
        {"name":"FEVER","url":"https://fever.ai/dataset/fever.html","license":"Wikipedia terms / CC BY-SA 3.0 fallback per official notice","decision":"Excluded: Wikipedia domain; evidence references need dereferencing; licensing/share-alike obligations."},
        {"name":"SciFact","url":"https://github.com/allenai/scifact","license":"Annotations CC BY 4.0; abstract corpus ODC-By 1.0","decision":"Excluded: biomedical domain and labeled set lacks a robust insufficient-evidence class."},
        {"name":"StaQC","url":"https://huggingface.co/datasets/koutch/staqc","license":"Dataset card CC BY 4.0; original Stack Overflow posts retain revision-specific CC BY-SA terms","decision":"Excluded: code/question pairs, not claim-evidence truth labels."},
        {"name":"CoNaLa","url":"https://conala-corpus.github.io/","license":"No explicit dataset license identified on project page; Stack Overflow sourced","decision":"Excluded: intent/code pairs, no claim-evidence labels; license unclear."},
        {"name":"CodeSearchNet","url":"https://github.com/github/CodeSearchNet","license":"Repository MIT; underlying samples have per-record repository licenses","decision":"Excluded: docstring/code pairs without support/contradiction/insufficient-evidence annotations."}],
        "selection_policy":"Require programming domain, explicit claim and evidence, mappable three-way labels, usable redistribution license, and traceable record-level provenance. No source met all requirements."}
    (out/"dataset_sources.json").write_text(json.dumps(sources,indent=2,ensure_ascii=False),encoding="utf-8")
    stats={"class_distribution":metadata["records_per_class"],"topic_distribution":metadata["records_per_topic"],
        "origin_distribution":metadata["records_per_origin"],"split_sizes":metadata["split_sizes"],
        "external_class_distribution":metadata["external_class_distribution"],"human_verified_records":0}
    (out/"dataset_statistics.json").write_text(json.dumps(stats,indent=2,ensure_ascii=False),encoding="utf-8")
    quality=("# Dataset quality report\n\n"+f"- Rows: {len(rows)}; external rows: {len(ext)}\n- Synthetic: {len(rows)} internal and {len(ext)} external; human verified: 0\n"+
      f"- Exact duplicates: 0; normalized claim-label conflicts: 0; near-duplicate pairs at >=0.90 similarity: {len(near)} (kept within source-page groups).\n"+
      f"- Source URL groups are disjoint across internal splits; external URL is disjoint from internal sources.\n- Every row has source URL, record ID, license, and provenance fields.\n\n"+
      "## Readiness\n\nNOT READY for model training or reliability claims. Records require independent domain-expert review and adjudication. The held-out page is synthetic and is not an independent external benchmark.\n")
    (reports/"dataset_quality_report.md").write_text(quality,encoding="utf-8")
    (out/"dataset_card.md").write_text("# CodeGuard programming claim-evidence research dataset\n\n"+
      "## Intended use\nResearch and pipeline development after expert review. Not for production model training or performance claims yet.\n\n"+
      f"## Contents\n{len(rows)} internal synthetic examples plus {len(ext)} synthetic page-held-out examples; labels are Supported, Contradicted, Insufficient Evidence.\n\n"+
      "## Creation and review\nClaims were manually templated from short official Python documentation passages and some rows were carried over from the previous synthetic candidate. ‘Source checked’ is not ‘human verified’. Every record is pending expert review.\n\n"
      "## Limitations\nSmall, templated, lexical polarity pairs; no compatible public dataset included; not representative of naturally occurring AI explanations. Insufficient Evidence is evidence-relative. No model was trained.\n",encoding="utf-8")
    (out/"data_dictionary.md").write_text("# Data dictionary\n\n"+"\n".join(f"- `{f}`: "+{
        "id":"Stable row identifier.","claim":"Claim being checked.","evidence":"Evidence passage presented to adjudicate the claim.","label":"Evidence-relative three-way label.",
        "data_origin":"public, manually_verified, or synthetic; current records are synthetic.","source_name":"Publisher/source label.","source_url":"Canonical source page URL.",
        "source_record_id":"Stable local source proposition identifier.","license":"Applicable source license/attribution.","topic":"Programming topic.","language":"Programming language.",
        "fact_key":"Proposition key.","evidence_group":"Group used to prevent leakage across splits.","provenance":"How this record was constructed.",
        "verification_status":"Current verification/review state.","source_title":"Documentation title.","source_section":"Relevant section.","claim_family":"Related polarity or IE family.","review_status":"Expert review state."}[f] for f in FIELDS),encoding="utf-8")
    (out/"license_attribution.md").write_text("# License and attribution\n\nPython documentation is provided under the Python Software Foundation License Version 2; see [official license](https://docs.python.org/3/license.html). Source title, URL, section, and attribution are retained per row. Evidence excerpts are short and tied to those source pages. No third-party claim dataset was incorporated. FEVER, SciFact, StaQC, CoNaLa, and CodeSearchNet were evaluated and excluded for domain, label, evidence, or licensing fit; see `dataset_sources.json`.\n",encoding="utf-8")
    (raw/"README.md").write_text("No third-party raw datasets are included. `source_facts.json` contains the source-proposition manifest used by this builder; it does not contain downloaded corpora.\n",encoding="utf-8")
    # Simple, dependency-free SVG summaries are regenerated deterministically.
    _write_svg(reports/"class_distribution.svg",metadata["records_per_class"],"Records by label")
    _write_svg(reports/"source_distribution.svg",_distribution(rows,"source_url"),"Records by source page")
    result={"rows":rows,"splits":splits,"external_test":ext,"metadata":metadata,"sources":sources}
    return result

def _write_svg(path: Path, counts: dict[str,int], title: str) -> None:
    height=50+len(counts)*28; maxv=max(counts.values(),default=1)
    body=[f'<text x="12" y="22" font-size="16" font-weight="bold">{title}</text>']
    for i,(name,value) in enumerate(sorted(counts.items())):
        y=42+i*28; label=name.replace("&","&amp;").replace("<","&lt;")
        body.append(f'<text x="12" y="{y+14}" font-size="11">{label}</text><rect x="340" y="{y}" width="{int(360*value/maxv)}" height="18" fill="#3978a8"/><text x="710" y="{y+14}" font-size="11">{value}</text>')
    path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="780" height="{height}">'+''.join(body)+'</svg>',encoding="utf-8")

if __name__ == "__main__":
    result=build_research_dataset()
    print(json.dumps({"records":len(result["rows"]),"external_test":len(result["external_test"]),
      "classes":result["metadata"]["records_per_class"],"splits":result["metadata"]["split_sizes"],
      "ready":result["metadata"]["ready_for_model_training"]},indent=2))
