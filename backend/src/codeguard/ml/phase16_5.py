"""Phase 16.5: curated synthetic claim candidates and batching; no model training."""
from __future__ import annotations

import csv
import json
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from codeguard.ml.phase16 import PHASE16_DIR, ROOT
from codeguard.ml.review import initialize_review_db, list_review_records
from codeguard.ml.research_dataset import FIELDS, LABELS, normalize

OUT = ROOT / "data" / "ml" / "phase16_5"
QUEUE = PHASE16_DIR / "review" / "review_queue.csv"
DB = PHASE16_DIR / "review" / "reviews.sqlite3"
LICENSE = "Python Software Foundation License Version 2; retain attribution and source URL"
LICENSE_URL = "https://docs.python.org/3/license.html"

# Fact rows were manually curated from official Python documentation pages.
# Each row is (fact_id, topic, URL, title, section, minimal evidence,
# supported claim, contradicted claim, insufficient-evidence claim, pool).
FACTS: list[tuple[str, str, str, str, str, str, str, str, str, str]] = [
("dict_order", "dictionaries", "https://docs.python.org/3/library/stdtypes.html", "Built-in Types", "Mapping Types - dict", "Dictionaries preserve insertion order; replacing an existing key does not change its order.", "Updating an existing dictionary key leaves that key in its insertion-order position.", "Updating an existing dictionary key moves it to the end of dictionary iteration order.", "Deleting a dictionary key and inserting that key again preserves its former insertion position.", "internal"),
("dict_get", "dictionaries", "https://docs.python.org/3/library/stdtypes.html", "Built-in Types", "Mapping Types - dict", "get(key[, default]) returns the value for key if key is in the dictionary, otherwise default; default is None when omitted.", "Calling d.get(k) for a missing key returns None when no default is supplied.", "Calling d.get(k) for a missing key raises KeyError when no default is supplied.", "Calling d.get(k) for a present key records an access timestamp.", "internal"),
("dict_views", "dictionaries", "https://docs.python.org/3/library/stdtypes.html", "Built-in Types", "Dictionary view objects", "Dictionary views are dynamic and reflect changes to the dictionary.", "A previously obtained dictionary view reflects later changes to that dictionary.", "A dictionary view is a fixed snapshot that ignores later dictionary changes.", "Dictionary views use a balanced tree internally.", "internal"),
("list_sort_none", "lists", "https://docs.python.org/3/library/stdtypes.html", "Built-in Types", "Mutable Sequence Types", "The list sort method sorts the list in place and returns None.", "list.sort() changes the list in place and returns None.", "list.sort() returns a new sorted list without changing the original list.", "If the key function raises an exception during sorting, the list is always restored to its original order.", "internal"),
("sorted_new", "lists", "https://docs.python.org/3/library/functions.html", "Built-in Functions", "sorted", "sorted(iterable, key=None, reverse=False) returns a new sorted list.", "sorted(values) returns a list containing the sorted items.", "sorted(values) sorts the original iterable in place.", "The sorted() built-in guarantees a stable ordering when two items have equal keys.", "internal"),
("slice_copy", "slicing", "https://docs.python.org/3/library/stdtypes.html", "Built-in Types", "Common Sequence Operations", "Slicing a sequence produces a new sequence of the same type.", "A slice of a list produces a new list object.", "A slice of a list is always a live view that writes through to the original list.", "Mutating a nested list reached through a list slice changes that nested object.", "internal"),
("tuple_nested_mutable", "tuples and mutability", "https://docs.python.org/3/tutorial/datastructures.html", "The Python Tutorial", "Tuples and Sequences", "Tuples are immutable, but they can contain mutable objects such as lists whose contents can change.", "A list stored inside a tuple can still have its own contents modified.", "Immutability of a tuple makes every list inside it immutable too.", "A tuple may be used as a dictionary key even when one of its elements is a list.", "internal"),
("set_unique", "sets", "https://docs.python.org/3/library/stdtypes.html", "Built-in Types", "Set Types", "A set is an unordered collection of distinct hashable objects.", "A set cannot contain two equal elements as separate members.", "A set preserves duplicate equal elements in insertion order.", "Iterating over a set always yields its members in the order they were inserted.", "internal"),
("lambda_expr", "functions", "https://docs.python.org/3/tutorial/controlflow.html", "The Python Tutorial", "Lambda Expressions", "Lambda functions can contain only expressions, not statements.", "A lambda body is an expression rather than a suite of statements.", "A lambda body may contain a sequence of assignment statements.", "A lambda expression may define keyword-only parameters after a bare star.", "internal"),
("keyword_only", "function arguments", "https://docs.python.org/3/tutorial/controlflow.html", "The Python Tutorial", "Keyword-Only Arguments", "Parameters after a bare * or after *args are keyword-only.", "A parameter following *args in a function definition must be supplied by keyword.", "A parameter following *args can always be supplied positionally.", "A function call may supply a parameter after *args as an extra positional argument.", "internal"),
("positional_only", "function arguments", "https://docs.python.org/3/tutorial/controlflow.html", "The Python Tutorial", "Positional-Only Parameters", "Parameters before / in a function definition are positional-only.", "The slash marker can designate parameters that cannot be passed by keyword.", "The slash marker designates parameters that must be passed by keyword.", "Parameters after the slash in a function definition are positional-only.", "internal"),
("annotations_runtime", "typing", "https://docs.python.org/3/library/typing.html", "Typing", "Type Hints", "The Python runtime does not enforce function and variable annotations.", "Adding a type annotation does not itself make Python reject a value of another type at runtime.", "Python automatically enforces every function annotation when the function is called.", "typing.get_type_hints can resolve annotations into evaluated Python objects.", "internal"),
("main_module", "modules and imports", "https://docs.python.org/3/library/__main__.html", "__main__ - Top-level code environment", "__main__", "A module's __name__ is set to '__main__' when it is run as the top-level program.", "The module executed as the top-level program has __name__ equal to '__main__'.", "An imported module always has __name__ equal to '__main__'.", "Importing a module under any name also executes its __main__-guarded block.", "internal"),
("json_loads", "standard library: json", "https://docs.python.org/3/library/json.html", "JSON", "Basic Usage", "json.loads deserializes a JSON document from a string or bytes-like object.", "json.loads(text) parses JSON supplied as text.", "json.loads(text) writes a JSON document to a file.", "When a JSON object repeats a name, json.loads preserves both values in the resulting dictionary.", "internal"),
("json_dumps", "standard library: json", "https://docs.python.org/3/library/json.html", "JSON", "Basic Usage", "json.dumps serializes an object to a JSON formatted str.", "json.dumps(value) returns a string containing JSON text.", "json.dumps(value) returns an open file object containing JSON text.", "json.dumps preserves Python object identity after serialization.", "internal"),
("counter_missing", "standard library: collections", "https://docs.python.org/3/library/collections.html", "Collections - Container Datatypes", "Counter objects", "A Counter returns a zero count for missing items instead of raising KeyError.", "Reading a missing key from a Counter returns zero.", "Reading a missing key from a Counter raises KeyError.", "Counter supports element-wise addition of two counters.", "internal"),
("defaultdict_factory", "standard library: collections", "https://docs.python.org/3/library/collections.html", "Collections - Container Datatypes", "defaultdict objects", "The default_factory is called without arguments to produce a default value when a missing key is accessed.", "Accessing a missing defaultdict key can call its default_factory.", "A defaultdict default_factory receives the missing key as its required argument.", "defaultdict.get(key) calls default_factory when key is missing.", "internal"),
("deque_ends", "standard library: collections", "https://docs.python.org/3/library/collections.html", "Collections - Container Datatypes", "deque objects", "Deques support thread-safe, memory-efficient appends and pops from either side.", "A deque provides append and pop operations at both ends.", "A deque only permits insertion and removal at its right end.", "A deque provides indexed access to elements in the middle with the same efficiency as either end.", "internal"),
("chain_iterables", "iteration", "https://docs.python.org/3/library/itertools.html", "Itertools", "chain", "chain returns an iterator that returns elements from the first iterable until it is exhausted, then proceeds to the next iterable.", "itertools.chain processes its input iterables in sequence.", "itertools.chain interleaves items from all inputs in round-robin order.", "itertools.chain.from_iterable takes a single iterable of iterables as its input.", "internal"),
("count_infinite", "iteration", "https://docs.python.org/3/library/itertools.html", "Itertools", "count", "count(start=0, step=1) makes an iterator that returns evenly spaced values beginning with start and has no end condition.", "itertools.count produces an iterator of successive values from its starting point.", "itertools.count stops automatically after yielding its starting value.", "itertools.count(start, step) precomputes and stores all values it will yield.", "internal"),
("partial_args", "standard library: functools", "https://docs.python.org/3/library/functools.html", "Functools", "partial objects", "partial returns a new partial object which when called behaves like func called with the positional arguments and keyword arguments supplied to partial.", "functools.partial can create a callable with some arguments pre-filled.", "functools.partial immediately invokes the wrapped function when it is created.", "A partial object exposes the stored positional arguments through its args attribute.", "internal"),
("regex_search", "regular expressions", "https://docs.python.org/3/library/re.html", "Regular Expression Operations", "search", "re.search scans through a string looking for a match anywhere; re.match checks for a match only at the beginning.", "re.search can find a match that starts after the beginning of the string.", "re.match searches every possible starting position in the string.", "Regular-expression matching is case-insensitive by default when using re.search.", "internal"),
("regex_fullmatch", "regular expressions", "https://docs.python.org/3/library/re.html", "Regular Expression Operations", "fullmatch", "re.fullmatch checks whether the whole string matches the regular expression.", "re.fullmatch requires the pattern to match the entire string.", "re.fullmatch succeeds when the pattern matches any substring.", "re.fullmatch accepts a match ending before the final character if the remaining suffix is a newline.", "internal"),
("copy_shallow", "object model", "https://docs.python.org/3/library/copy.html", "Copy", "Shallow and deep copy operations", "A shallow copy constructs a new compound object and inserts references to the objects found in the original.", "copy.copy creates a new outer compound object while retaining references to nested objects.", "copy.copy recursively duplicates every object reachable from the input.", "copy.copy recursively creates new copies of every nested object.", "internal"),
("copy_deep", "object model", "https://docs.python.org/3/library/copy.html", "Copy", "Shallow and deep copy operations", "A deep copy constructs a new compound object and then recursively inserts copies of the objects found in the original.", "copy.deepcopy recursively copies nested objects, subject to the module's documented behavior.", "copy.deepcopy only creates a new outer container and always reuses every nested reference.", "copy.deepcopy uses a memo dictionary to avoid recursive loops.", "internal"),
("suppress_specific", "exceptions and context managers", "https://docs.python.org/3/library/contextlib.html", "Contextlib", "suppress", "suppress suppresses any of the specified exceptions if they occur in the body of a with statement.", "contextlib.suppress(FileNotFoundError) is scoped to the specified exception type.", "contextlib.suppress(FileNotFoundError) suppresses every exception type.", "contextlib.suppress(FileNotFoundError) also suppresses a TypeError raised in the with body.", "external"),
("path_is_file", "standard library: pathlib", "https://docs.python.org/3/library/pathlib.html", "Pathlib", "Pure paths and concrete paths", "Path.is_file returns True if the path points to a regular file, following symlinks.", "Path.is_file() follows a symlink when checking whether its target is a regular file.", "Path.is_file() returns True only for directories.", "Path.is_file() caches every file-type result permanently on its Path instance.", "external"),
("asyncio_task", "async programming", "https://docs.python.org/3/library/asyncio-task.html", "Asyncio Tasks", "Task Object", "Tasks are used to schedule coroutines concurrently.", "asyncio tasks schedule coroutine execution within an event loop.", "Calling asyncio.create_task(coro) immediately returns the coroutine's final result without awaiting its completion.", "Task.cancel() raises CancelledError immediately in the caller before control returns.", "external"),
("subprocess_check", "processes", "https://docs.python.org/3/library/subprocess.html", "Subprocess", "run", "If check is true and the process exits with a non-zero exit code, a CalledProcessError exception will be raised.", "subprocess.run(..., check=True) raises CalledProcessError for a non-zero exit status.", "subprocess.run(..., check=True) silently treats every non-zero exit status as success.", "subprocess.run(timeout=...) returns a CompletedProcess normally if the child exceeds the timeout.", "external"),
 ("typing_cast", "typing", "https://docs.python.org/3/library/typing.html", "Typing", "Cast", "cast returns the value unchanged; it does not perform a runtime type check.", "typing.cast does not convert its argument at runtime.", "typing.cast converts its argument to the requested type at runtime.", "A static type checker must treat a value passed through typing.cast as having the requested type.", "internal"),
("temp_cleanup", "files and resource handling", "https://docs.python.org/3/library/tempfile.html", "Tempfile", "TemporaryDirectory", "TemporaryDirectory can be used as a context manager; the directory and contents are removed when the context exits.", "A TemporaryDirectory context manager removes its temporary directory on context exit.", "A TemporaryDirectory is preserved after context exit by default.", "TemporaryDirectory supports a parameter that ignores cleanup errors.", "external"),
]
LEGACY_FACT_COUNT = len(FACTS)
from codeguard.ml.phase16_6b_facts import FACTS as PHASE166B_FACTS
from codeguard.ml.phase16_7_facts import facts as phase16_7_inventory_facts
from codeguard.ml.phase16_8_facts import facts as phase16_8_inventory_facts

# This inventory is append-only. Phase 16.5 tuple positions remain unchanged;
# new facts use stable fact-key-based IDs and deliberately vary candidate count.
FACTS.extend(PHASE166B_FACTS)
FACT_FIELDS = ("fact_id","fact_key","canonical_fact","topic","source_url","source_title","section","evidence_locator","evidence_text","license","license_url","evidence_group","source_group","claim_family","source_type","retrieval_date","provenance_status","review_priority","fact_review_status")
SOURCE_FIELDS = ("source_name","source_url","page_title","section","source_type","license","license_url","retrieval_date","provenance_status","evidence_group")


def _write_csv(path: Path, fields: tuple[str,...], rows: list[dict[str,Any]]) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore"); w.writeheader(); w.writerows(rows)

def _make_fact_records() -> tuple[list[dict[str,str]],list[dict[str,str]],list[dict[str,str]]]:
    facts=[]; sources=[]; candidates=[]
    for index,item in enumerate(FACTS,1):
        fid,topic,url,title,section,evidence,supported,contradicted,ie,pool=item
        is_legacy=index <= LEGACY_FACT_COUNT
        fact_id=f"cg165-f{index:03d}" if is_legacy else fid
        evidence_group=f"page:{url}"
        priority="easy" if pool=="internal" and index<=12 else ("advanced" if pool=="external" else "intermediate")
        facts.append({"fact_id":fact_id,"fact_key":fid,"canonical_fact":supported,"topic":topic,"fact_statement":supported,"source_url":url,
            "source_title":title,"section":section,"evidence_locator":f"{title} — {section}","evidence_text":evidence,"license":LICENSE,
            "license_url":LICENSE_URL,"evidence_group":evidence_group,"source_group":evidence_group,
            "claim_family":fid,"source_type":"official_python_documentation","retrieval_date":date.today().isoformat(),
            "provenance_status":"Official Python documentation page inspected; evidence paraphrased for candidate generation; independent review pending",
            "review_priority":priority,"fact_review_status":"pending_independent_review"})
        sources.append({"source_name":"Python Software Foundation documentation","source_url":url,
            "page_title":title,"section":section,"source_type":"official Python documentation","license":LICENSE,
            "license_url":LICENSE_URL,"retrieval_date":date.today().isoformat(),
            "provenance_status":"official canonical docs.python.org page; stable /3/ URL; section recorded","evidence_group":evidence_group})
        candidate_specs=[("s",supported,"Supported"),("c",contradicted,"Contradicted"),("i",ie,"Insufficient Evidence")]
        if not is_legacy and pool == "internal":
            # Two complementary, evidence-grounded judgments per internal fact;
            # rotate the label pair so this is not a fixed three-row template.
            pairs=((0,1),(0,2),(1,2))
            candidate_specs=[candidate_specs[i] for i in pairs[(index-LEGACY_FACT_COUNT-1)%len(pairs)]]
        for suffix,claim,label in candidate_specs:
            cid=f"cg165-{index:03d}-{suffix}" if is_legacy else f"cg166b-{fid}-{suffix}"
            candidates.append({"id":cid,"claim":claim,"evidence":evidence,"label":"","data_origin":"synthetic",
                "source_name":"Python Software Foundation documentation","source_url":url,
                "source_record_id":f"python-docs:{fid}","license":LICENSE,"topic":topic,"language":"Python",
                "fact_key":fid,"evidence_group":evidence_group,
                "source_group":evidence_group,
                "provenance":"Synthetic claim candidate derived from a curated official-documentation fact; not a human annotation.",
                "verification_status":"Candidate wording requires independent evidence-only review",
                "source_title":title,"source_section":section,"claim_family":fid,
                "review_status":"pending","proposed_label":label,"gold_label":"",
                "data_origin_status":"synthetic_pending_review","dataset_partition":"external" if pool=="external" else "internal",
                "review_id":cid,"record_id":cid,"split":"unassigned","batch_id":"","review_priority":priority,"review_mode":"",
                "source_verified":"","reviewer_A_id":"","reviewer_A_label":"","reviewer_A_timestamp":"",
                "reviewer_B_id":"","reviewer_B_label":"","reviewer_B_timestamp":"",
                "adjudicator_id":"","final_adjudicated_label":"","adjudication_timestamp":""})
    return facts,sources,candidates


def _text_metrics(rows: list[dict[str,str]]) -> dict[str,Any]:
    exact=Counter(); near=[]; semantic=[]
    for i,row in enumerate(rows):
        exact[normalize(row["claim"])] += 1
        for other in rows[:i]:
            score=SequenceMatcher(None,normalize(row["claim"]),normalize(other["claim"])).ratio()
            same_fact = bool(other.get("fact_key")) and other.get("fact_key")==row.get("fact_key")
            if same_fact and _semantic_signature(row["claim"]) == _semantic_signature(other["claim"]):
                semantic.append({"id_a":other["id"],"id_b":row["id"],"fact_key":row["fact_key"]})
            if score >= .90:
                near.append({"id_a":other["id"],"id_b":row["id"],"similarity":round(score,4),
                             "same_fact":same_fact,"same_family":other["claim_family"]==row["claim_family"]})
    repeated=[text for text,n in exact.items() if n>1]
    # The two opposite label candidates for a fact are a deliberate review pair.
    # Near duplicates remain visible and are not silently called independent examples.
    return {"exact_normalized_claim_duplicates":len(repeated),"near_duplicate_pairs_ge_090":len(near),
            "same_fact_semantic_duplicates":len(semantic),"same_fact_semantic_duplicate_pairs":semantic,
            "near_duplicate_pairs":near,"repeated_normalized_claims":repeated}


_SEMANTIC_STOP_WORDS = {"a", "an", "the", "is", "are", "was", "were", "be", "been", "being"}


def _semantic_signature(claim: str) -> tuple[str, ...]:
    """Conservative same-fact signature; retain negation and meaningful operators."""
    return tuple(token for token in re.findall(r"[a-z0-9_]+", normalize(claim))
                 if token not in _SEMANTIC_STOP_WORDS)


def _quality_filter(candidates: list[dict[str,str]], existing: list[dict[str,str]]) -> tuple[list[dict[str,str]],list[dict[str,str]]]:
    """Withhold exact or >=.90 similar claim text from the human review pool."""
    kept=[]; excluded=[]
    existing_ids={r.get("id") or r.get("review_id","") for r in existing}
    seen=[(normalize(r.get("claim","")),r.get("id") or r.get("review_id",""),
           r.get("fact_key",""),_semantic_signature(r.get("claim",""))) for r in existing]
    for row in candidates:
        claim=normalize(row["claim"])
        signature=_semantic_signature(row["claim"])
        if row.get("id") in existing_ids:
            # Existing review records are immutable inputs to this builder.
            # Keep them even when the audit finds an inherited duplicate pair.
            kept.append(row)
            continue
        duplicate=None
        for prior,prior_id,prior_fact,prior_signature in seen:
            if prior_id == row.get("id"):
                # Same persisted Phase 16.5 candidate on an idempotent rerun.
                continue
            score=SequenceMatcher(None,claim,prior).ratio()
            same_fact_semantic = bool(row.get("fact_key")) and row.get("fact_key")==prior_fact and signature==prior_signature
            if claim==prior or score>=.90 or same_fact_semantic:
                duplicate=(prior_id,score,"same-fact semantic duplicate" if same_fact_semantic else "normalized exact/near duplicate"); break
        if duplicate:
            excluded.append({**row,"exclusion_reason":f"{duplicate[2]} (similarity {duplicate[1]:.4f}) of {duplicate[0]}; withheld from review queue."})
        else:
            seen.append((claim,row["id"],row.get("fact_key",""),signature)); kept.append(row)
    return kept,excluded


def _assign_batches(records: list[dict[str,str]]) -> tuple[list[dict[str,str]],list[dict[str,Any]]]:
    """Deterministically stratify internal queue into mixed-label/topic 30-item batches."""
    internal=[r for r in records if r.get("dataset_partition")=="internal"]
    external=[r for r in records if r.get("dataset_partition")=="external"]
    easy=[r for r in internal if r.get("review_priority")=="easy"]
    for row in easy: row["batch_id"]="review_batch_001"
    remaining=[r for r in internal if r not in easy]
    buckets=defaultdict(list)
    unlabeled=[]
    for row in remaining:
        proposal=row.get("proposed_label","")
        if proposal in LABELS:
            buckets[proposal].append(row)
        else:
            unlabeled.append(row)
    keys=sorted(buckets)
    for values in buckets.values(): values.sort(key=lambda r:(r.get("topic",""),r.get("fact_key",""),r["id"]))
    total_labelled=sum(len(values) for values in buckets.values())
    batch_count=max(1,(total_labelled+len(unlabeled)+39)//40)
    slots=[[] for _ in range(batch_count)]
    for key in keys:
        for index,row in enumerate(buckets[key]): slots[index % batch_count].append(row)
    for row in unlabeled:
        target=min(range(batch_count),key=lambda i:len(slots[i]))
        slots[target].append(row)
    for batch_index,group in enumerate(slots,2):
        for row in group: row["batch_id"]=f"review_batch_{batch_index:03d}"
    for row in external: row["batch_id"]="external_review_pool"
    batches=[]
    for bid in sorted({r["batch_id"] for r in records}):
        subset=[r for r in records if r["batch_id"]==bid]
        batches.append({"batch_id":bid,"count":len(subset),"partition":subset[0].get("dataset_partition","internal"),
            "proposed_label_counts":dict(Counter(r.get("proposed_label","") for r in subset)),
            "topic_count":len({r.get("topic","") for r in subset}),
            "priority":"External benchmark held separately" if bid=="external_review_pool" else ("easy introductory examples" if bid=="review_batch_001" else ("harder and varied concepts" if bid>"review_batch_002" else "varied programming concepts")),
            "review_status":"pending"})
    return records,batches


def _persist_batch_metadata(db_path: Path, records: list[dict[str,str]]) -> None:
    db=sqlite3.connect(str(db_path))
    try:
        with db:
            for record in records:
                rid=record.get("review_id") or record.get("id")
                raw=db.execute("SELECT record_json FROM review_records WHERE review_id=?",(rid,)).fetchone()
                if not raw: continue
                old=json.loads(raw[0]); old["batch_id"]=record["batch_id"]
                old["claim_family"]=record.get("claim_family",old.get("claim_family",""))
                old["fact_key"]=record.get("fact_key",old.get("fact_key",""))
                old["topic"]=record.get("topic",old.get("topic",""))
                old["source_group"]=record.get("source_group",old.get("source_group",old.get("evidence_group","")))
                db.execute("UPDATE review_records SET record_json=? WHERE review_id=?",(json.dumps(old,ensure_ascii=False),rid))
    finally: db.close()


def build_phase16_5() -> dict[str,Any]:
    OUT.mkdir(parents=True,exist_ok=True)
    facts,sources,generated_rows=_make_fact_records()
    # Load the persisted queue (not a regenerated Phase 16 builder) so existing
    # candidate IDs, reviews, and reviewer event history remain intact.
    with QUEUE.open(encoding="utf-8-sig",newline="") as f: existing=list(csv.DictReader(f))
    # Record exact/near-duplicate exclusions both against Phase 16 and within
    # the Phase 16.5 additions. The generated registry remains deterministic.
    generated_rows, quality_exclusions = _quality_filter(generated_rows,existing)
    old_ids={r["review_id"] for r in existing}
    new_rows=[r for r in generated_rows if r["review_id"] not in old_ids]
    all_rows=existing+new_rows
    all_rows,batches=_assign_batches(all_rows)
    # Keep the prior database authoritative: append absent IDs with INSERT OR IGNORE.
    all_facts={}
    persisted_inventory = OUT / "fact_inventory.csv"
    if persisted_inventory.is_file():
        with persisted_inventory.open(encoding="utf-8-sig", newline="") as f:
            for fact in csv.DictReader(f):
                key = fact.get("fact_key", "")
                if key:
                    all_facts.setdefault(key, fact)
    for row in existing:
        key=row.get("fact_key","")
        if key and key not in all_facts:
            url=row.get("source_url",""); group=row.get("evidence_group",f"page:{url}")
            section=row.get("source_section","")
            all_facts[key]={"fact_id":key,"fact_key":key,"canonical_fact":row.get("claim",""),
                "topic":row.get("topic",""),"fact_statement":row.get("claim",""),
                "source_url":url,"source_title":row.get("source_title",row.get("source_name","")),
                "section":section,"evidence_locator":f"{row.get('source_title',row.get('source_name',''))} — {section}","evidence_text":row.get("evidence",""),
                "license":row.get("license",""),"license_url":LICENSE_URL,"evidence_group":group,
                "source_group":group,"claim_family":row.get("claim_family",key),
                "source_type":"official programming documentation","retrieval_date":"2026-09-26",
                "provenance_status":"carried forward from Phase 16; source attribution retained",
                "review_priority":"existing Phase 16 candidate fact",
                "fact_review_status":"pending_independent_review"}
    for fact in facts: all_facts.setdefault(fact["fact_key"],fact)
    # Inventory-only Phase 16.7 facts are deliberately excluded from candidate
    # generation above. Merge them here so future builder runs retain them.
    for fact in phase16_7_inventory_facts(): all_facts.setdefault(fact["fact_key"], fact)
    for fact in phase16_8_inventory_facts(): all_facts.setdefault(fact["fact_key"], fact)
    complete_facts=list(all_facts.values())
    _write_csv(OUT/"fact_inventory.csv",FACT_FIELDS,complete_facts)
    source_by_url={r["source_url"]:r for r in sources}
    for fact in [*phase16_7_inventory_facts(), *phase16_8_inventory_facts()]:
        url = fact["source_url"]
        source_by_url.setdefault(url, {"source_name":"Python Software Foundation documentation",
            "source_url":url,"page_title":fact["source_title"],"section":fact["section"],
            "source_type":"official Python documentation","license":LICENSE,
            "license_url":LICENSE_URL,"retrieval_date":fact["retrieval_date"],
            "provenance_status":fact["provenance_status"],"evidence_group":fact["source_group"]})
    for row in existing:
        url=row.get("source_url","")
        if url and url not in source_by_url:
            source_by_url[url]={"source_name":row.get("source_name","Python source"),"source_url":url,
                "page_title":row.get("source_title",row.get("source_name","")),"section":row.get("source_section",""),
                "source_type":"official programming documentation","license":row.get("license",""),
                "license_url":LICENSE_URL,"retrieval_date":"2026-09-26",
                "provenance_status":"carried forward from Phase 16; independent page revision pin not recorded",
                "evidence_group":row.get("evidence_group",f"page:{url}")}
    unique_sources=source_by_url
    _write_csv(OUT/"source_inventory.csv",SOURCE_FIELDS,list(unique_sources.values()))
    _write_csv(OUT/"pending_review.csv",tuple(dict.fromkeys(list(FIELDS)+["proposed_label","dataset_partition","batch_id","review_id"])),all_rows)
    internal_new=[r for r in generated_rows if r["dataset_partition"]=="internal"]
    external_new=[r for r in generated_rows if r["dataset_partition"]=="external"]
    _write_csv(OUT/"external_review_queue.csv",("claim","evidence","proposed_label","source","source_url","fact_id","evidence_group","review_status","review_id","topic","batch_id"),[
        {"claim":r["claim"],"evidence":r["evidence"],"proposed_label":r["proposed_label"],"source":r["source_title"],
         "source_url":r["source_url"],"fact_id":r["fact_key"],"evidence_group":r["evidence_group"],
         "review_status":"pending","review_id":r["review_id"],"topic":r["topic"],"batch_id":"external_review_pool"} for r in external_new])
    _write_csv(OUT/"review_batches.csv",("batch_id","count","partition","proposed_label_counts","topic_count","priority","review_status"),[
        {**b,"proposed_label_counts":json.dumps(b["proposed_label_counts"],sort_keys=True)} for b in batches])
    exclusion_fields=tuple(dict.fromkeys([*generated_rows[0].keys(),"exclusion_reason"]))
    _write_csv(OUT/"quality_exclusions.csv",exclusion_fields,quality_exclusions)
    _write_csv(QUEUE,tuple(dict.fromkeys([*existing[0].keys(),*generated_rows[0].keys()])),all_rows)
    initialize_review_db(QUEUE,DB)
    _persist_batch_metadata(DB,all_rows)
    from codeguard.ml.review import export_review_views
    export_review_views(DB,PHASE16_DIR)
    _persist_batch_metadata(DB,all_rows)
    export_review_views(DB,PHASE16_DIR)
    # Reload queue from the DB export; it includes stable real review states.
    with QUEUE.open(encoding="utf-8-sig",newline="") as f: master=list(csv.DictReader(f))
    master_by_id={r["review_id"]:r for r in master}
    # Store batch additions in database JSON; exports may reorder field sets, so
    # the explicit batch map is also persisted as a human-readable manifest.
    _persist_batch_metadata(DB,all_rows)
    candidates=[r for r in master if r.get("dataset_partition")=="internal"]
    external=[r for r in master if r.get("dataset_partition")=="external"]
    counts=Counter(r.get("proposed_label","") for r in candidates)
    all_proposed=Counter(r.get("proposed_label","") for r in master)
    topics=Counter(r.get("topic","") for r in master)
    sources=Counter(r.get("source_url","") for r in master)
    facts_count=len({r.get("fact_key","") for r in master})
    facts_by_source: dict[str,set[str]]=defaultdict(set)
    facts_by_topic: dict[str,set[str]]=defaultdict(set)
    candidates_by_fact_group=Counter()
    for row in master:
        key=row.get("fact_key","")
        if key:
            facts_by_source[row.get("source_url","")].add(key)
            facts_by_topic[row.get("topic","")].add(key)
        candidates_by_fact_group[row.get("evidence_group","") or row.get("source_group","unknown")] += 1
    exact_near=_text_metrics(master)
    internal_urls={r.get("source_url","") for r in master if r.get("dataset_partition")=="internal"}
    external_urls={r.get("source_url","") for r in master if r.get("dataset_partition")=="external"}
    internal_facts={r.get("fact_key","") for r in master if r.get("dataset_partition")=="internal"}
    external_facts={r.get("fact_key","") for r in master if r.get("dataset_partition")=="external"}
    phase165_ids={r["review_id"] for r in generated_rows}
    stats={"previous_candidates":len(master)-sum(r.get("review_id") in phase165_ids for r in master),
        "new_candidates":sum(r.get("review_id") in phase165_ids for r in master),
        "newly_appended_candidates":len(new_rows),
        "phase16_6b_new_candidates":sum(str(r.get("review_id","")).startswith("cg166b-") for r in master),
        "phase16_6b_starting_candidates":sum(not str(r.get("review_id","")).startswith("cg166b-") for r in master),
        "phase16_6b_final_candidates":len(master),
        "phase16_6b_fact_count":len({r.get("fact_key") for r in master if str(r.get("fact_key","")).startswith("cg166b_")}),
        "phase16_6b_source_url_count":len({r.get("source_url") for r in master if str(r.get("fact_key","")).startswith("cg166b_")}),
        "phase16_6b_quality_exclusions":sum(str(r.get("id","")).startswith("cg166b-") for r in quality_exclusions),
        "phase16_6b_internal_count":sum(r.get("dataset_partition")=="internal" and str(r.get("review_id","")).startswith("cg166b-") for r in master),
        "phase16_6b_external_count":sum(r.get("dataset_partition")=="external" and str(r.get("review_id","")).startswith("cg166b-") for r in master),
        "automatically_excluded_candidates":len(quality_exclusions),"total_candidates":len(master),
        "internal_candidate_count":len(candidates),"external_candidate_count":len(external),
        "source_count":len(sources),"new_source_count":len({r["source_url"] for r in generated_rows}),
        "source_group_count":len({r.get("source_group","") for r in master if r.get("source_group")}),
        "facts_per_source":{k:len(v) for k,v in sorted(facts_by_source.items())},
        "facts_per_topic":{k:len(v) for k,v in sorted(facts_by_topic.items())},
        "candidates_per_source":dict(sorted(sources.items())),
        "candidates_per_fact_group":dict(sorted(candidates_by_fact_group.items())),
        "topic_count":len(topics),"topic_distribution":dict(sorted(topics.items())),
        "fact_count":facts_count,"claim_family_count":len({r.get("claim_family","") for r in master}),
        "proposed_label_distribution_not_gold":dict(sorted(counts.items())),
        "proposed_label_distribution_all_candidates_not_gold":dict(sorted(all_proposed.items())),
        "pending_count":sum(r.get("review_status")=="pending" for r in master),
        "reviewed_count":sum(r.get("review_status")=="reviewed" for r in master),
        "adjudicated_count":sum(r.get("review_status")=="adjudicated" for r in master),
        "verified_count":sum(bool(r.get("final_adjudicated_label")) for r in master),
        "duplicate_count":exact_near["exact_normalized_claim_duplicates"],
        "near_duplicate_count":exact_near["near_duplicate_pairs_ge_090"],
        "same_fact_semantic_duplicate_count":exact_near["same_fact_semantic_duplicates"],
        "source_concentration":dict(sources.most_common()),"topic_concentration":dict(sorted(topics.items())),
        "batch_count":len(batches),"external_reviewed":sum(r.get("review_status") in {"reviewed","adjudicated"} for r in external),
        "external_adjudicated":sum(r.get("review_status")=="adjudicated" for r in external),
        "candidate_target_minimum":1000,"candidate_target_met":len(master)>=1000,
        "external_source_fact_overlap":len(internal_facts & external_facts),
        "external_source_url_overlap":len(internal_urls & external_urls),
        "proposed_label_metrics_are_gold":False,"training_performed":False}
    (OUT/"candidate_statistics.json").write_text(json.dumps(stats,indent=2,ensure_ascii=False),encoding="utf-8")
    (OUT/"duplicate_audit.json").write_text(json.dumps(exact_near,indent=2,ensure_ascii=False),encoding="utf-8")
    (OUT/"README.md").write_text(
        "# Phase 16 candidate pool\n\nPhase 16.5 and 16.6B candidates are synthetic pending-review records. Proposed labels are not gold labels. "
        "The external pool is isolated from internal source pages. This workspace does not train a model. "
        "The human review database remains at `../phase16/review/reviews.sqlite3`; its event log is authoritative. "
        "See `docs/phases/PHASE_16_5_REPORT.md` and `docs/phases/PHASE_16_6B_REPORT.md` for methodology, statistics, limitations, and files.\n",encoding="utf-8")
    export_phase16_5_views(DB,OUT)
    return {"facts":facts,"sources":list(unique_sources.values()),"new_rows":new_rows,"all_rows":master,"batches":batches,"stats":stats}


def export_phase16_5_views(database_path: str | Path = DB, out_dir: str | Path = OUT) -> None:
    """Refresh separated review-stage exports; only adjudicated.csv has gold labels."""
    out=Path(out_dir); out.mkdir(parents=True,exist_ok=True)
    rows=list_review_records(database_path)
    fields=tuple(dict.fromkeys([*FIELDS,"proposed_label","gold_label","dataset_partition","review_id","batch_id","source_group",
        "reviewer_A_id","reviewer_A_label","reviewer_A_timestamp","reviewer_B_id","reviewer_B_label",
        "reviewer_B_timestamp","reviewer_label","reviewer_confidence","reviewer_notes","review_mode_A",
        "review_mode_B","source_verified_A","source_verified_B","adjudicator_id","adjudication_timestamp",
        "final_adjudicated_label"]))
    def view(row: dict[str,Any], *, gold: bool=False) -> dict[str,Any]:
        result={field:row.get(field,"") for field in fields}
        result["label"]=row.get("final_adjudicated_label","") if gold else ""
        result["gold_label"]=row.get("final_adjudicated_label","") if gold else ""
        result["final_adjudicated_label"]=row.get("final_adjudicated_label","") if gold else ""
        result["review_status"]=row.get("review_status","pending")
        result["reviewer_A_timestamp"]=row.get("reviewer_A_timestamp","")
        result["reviewer_B_timestamp"]=row.get("reviewer_B_timestamp","")
        result["review_mode_A"]=row.get("reviewer_A_mode","")
        result["review_mode_B"]=row.get("reviewer_B_mode","")
        result["source_verified_A"]=row.get("reviewer_A_source_verified","")
        result["source_verified_B"]=row.get("reviewer_B_source_verified","")
        result["adjudication_timestamp"]=row.get("adjudication_timestamp","")
        return result
    _write_csv(out/"candidates.csv",fields,[view(r) for r in rows])
    _write_csv(out/"pending_review.csv",fields,[view(r) for r in rows if r.get("review_status")=="pending"])
    _write_csv(out/"reviewed.csv",fields,[view(r) for r in rows if r.get("review_status")=="reviewed"])
    _write_csv(out/"adjudicated.csv",fields,[view(r,gold=True) for r in rows if r.get("review_status")=="adjudicated"])
    _write_csv(out/"rejected.csv",fields,[view(r) for r in rows if r.get("review_status")=="rejected"])
    external=[r for r in rows if r.get("dataset_partition")=="external"]
    _write_csv(out/"external_review_queue.csv",fields,[view(r) for r in external])
    batch_rows=[]
    for batch_id in sorted({r.get("batch_id","") for r in rows}):
        group=[r for r in rows if r.get("batch_id","")==batch_id]
        status_counts=Counter(r.get("review_status","pending") for r in group)
        batch_rows.append({"batch_id":batch_id,"count":len(group),
            "partition":group[0].get("dataset_partition","internal"),
            "proposed_label_counts":json.dumps(dict(Counter(r.get("proposed_label","") for r in group)),sort_keys=True),
            "topic_count":len({r.get("topic","") for r in group}),
            "priority":"External benchmark held separately" if batch_id=="external_review_pool" else ("easy introductory examples" if batch_id=="review_batch_001" else ("harder and varied concepts" if batch_id>"review_batch_002" else "varied programming concepts")),
            "pending":status_counts["pending"],"reviewed":status_counts["reviewed"],
            "disputed":status_counts["disputed"],"adjudicated":status_counts["adjudicated"],"rejected":status_counts["rejected"]})
    _write_csv(out/"review_batches.csv",("batch_id","count","partition","proposed_label_counts","topic_count","priority","pending","reviewed","disputed","adjudicated","rejected"),batch_rows)
    stats_path=out/"candidate_statistics.json"
    if stats_path.is_file():
        stats=json.loads(stats_path.read_text(encoding="utf-8"))
        all_records=list_review_records(database_path)
        reviewed=[r for r in all_records if r.get("reviewer_A_label") and r.get("reviewer_B_label")]
        agreements=sum(r["reviewer_A_label"]==r["reviewer_B_label"] for r in reviewed)
        stats.update({
            "candidate_count":len(all_records),
            "candidate_count_phase16_5":sum(str(r.get("review_id"," ")).startswith("cg165-") for r in rows),
            "pending_count":sum(r.get("review_status")=="pending" for r in all_records),
            "reviewed_count":sum(r.get("review_status")=="reviewed" for r in all_records),
            "adjudicated_count":sum(r.get("review_status")=="adjudicated" for r in all_records),
            "verified_count":sum(bool(r.get("final_adjudicated_label")) for r in all_records),
            "rejected_count":sum(r.get("review_status")=="rejected" for r in all_records),
            "agreement_count":agreements,
            "disagreement_count":len(reviewed)-agreements,
            "agreement_rate":agreements/len(reviewed) if reviewed else None,
            "external_reviewed":sum(r.get("dataset_partition")=="external" and r.get("review_status") in {"reviewed","adjudicated"} for r in all_records),
            "external_adjudicated":sum(r.get("dataset_partition")=="external" and r.get("review_status")=="adjudicated" for r in all_records),
            "external_reviewed_count":sum(r.get("dataset_partition")=="external" and r.get("review_status")=="reviewed" for r in all_records),
        })
        stats_path.write_text(json.dumps(stats,indent=2,ensure_ascii=False),encoding="utf-8")

if __name__ == "__main__":
    result=build_phase16_5(); s=result["stats"]
    print("="*60); print("PHASE 16.6B BUILD — SOURCE-FACT CANDIDATES PENDING HUMAN REVIEW"); print("="*60)
    for key in ("phase16_6b_starting_candidates","phase16_6b_new_candidates","phase16_6b_final_candidates",
                "phase16_6b_fact_count","phase16_6b_source_url_count","phase16_6b_internal_count","phase16_6b_external_count"):
        print(f"{key}: {s[key]}")
    for key in ("previous_candidates","new_candidates","total_candidates","source_count","new_source_count","topic_count","fact_count","claim_family_count"):
        print(f"{key}: {s[key]}")
    for label in ("Supported","Contradicted","Insufficient Evidence"):
        print(f"proposed_{label}: {s['proposed_label_distribution_not_gold'].get(label,0)}")
    print(f"pending_review: {s['pending_count']}; actually_reviewed: {s['reviewed_count']}; actually_adjudicated: {s['adjudicated_count']}; gold_labeled: {s['verified_count']}")
    print(f"near_duplicate_pairs_ge_090: {s['near_duplicate_count']}; external_candidates: {s['external_candidate_count']}; external_reviewed: {s['external_reviewed']}; external_adjudicated: {s['external_adjudicated']}")
    print(f"candidate_target_minimum: {s['candidate_target_minimum']}; candidate_target_met: {s['candidate_target_met']}")
    print("READY_FOR_PHASE_17: FALSE"); print("model_training: NOT RUN")
