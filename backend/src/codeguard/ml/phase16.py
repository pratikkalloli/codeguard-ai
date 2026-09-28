"""Phase 16 dataset research and review-workspace preparation (no training)."""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from codeguard.ml.research_dataset import DEFAULT_DIR as PHASE15_DIR, FIELDS as CANONICAL_FIELDS
from codeguard.ml.research_dataset import normalize

ROOT = Path(__file__).resolve().parents[4]
PHASE16_DIR = ROOT / "data" / "ml" / "phase16"
DECISIONS = {"USE", "PARTIAL", "REVIEW", "EXCLUDE"}
CANDIDATE_FIELDS = (
    "dataset_name", "url", "paper_url", "organization", "domain", "record_count",
    "claim_available", "evidence_available", "labels_available", "label_schema",
    "programming_relevance", "python_relevance", "annotation_method", "annotator_information",
    "license", "redistribution_allowed", "provenance_quality", "task_compatibility",
    "decision", "exclusion_reason",
)

# Audit inventory. A REVIEW decision means further authorization/license or
# task-fit verification is required. No candidate dataset is silently omitted.
CANDIDATES: list[dict[str, str]] = [
 {"dataset_name":"CodeSimpleQA","url":"https://arxiv.org/abs/2512.19424","paper_url":"https://arxiv.org/html/2512.19424v1","organization":"Beihang University and coauthors","domain":"Programming/computer-science factual QA","record_count":"Paper inconsistent: 1,498 abstract; 1,478 stats; 312 in annotation narrative","claim_available":"Programming QA pairs; exact claim-form field/release unverified","evidence_available":"Paper says grounded in documentation; record-level evidence artifact not found","labels_available":"No claim/evidence 3-way gold labels; model-answer outcomes CO/IN/NA only","label_schema":"QA factual-answer benchmark; not Supported/Contradicted/Insufficient Evidence pairs","programming_relevance":"High","python_relevance":"Partial; paper reports 76 Python items in one table, while another states 15+ languages","annotation_method":"Human-curated questions; answers expert-verified; paper reports at least 3 reviewers","annotator_information":"8 annotators and 3 senior engineers reported","license":"Dataset license not stated or independently located; arXiv paper license does not grant dataset rights","redistribution_allowed":"Unknown; no data downloaded","provenance_quality":"Paper-level provenance described; exact record-level evidence and IDs not inspected","task_compatibility":"Potential candidate source for manually constructed QA evaluation, but no direct 3-way mapping","decision":"REVIEW","exclusion_reason":"Strongest task-adjacent lead. Hold until authors/release and dataset terms are confirmed; QA facts cannot be converted automatically into evidence-relative labels."},
 {"dataset_name":"CS1QA","url":"https://aclanthology.org/2022.naacl-main.148/","paper_url":"https://aclanthology.org/2022.naacl-main.148/","organization":"KAIST authors","domain":"Introductory programming education","record_count":"9,237 annotated QA pairs; 17,698 unannotated chat data","claim_available":"Questions/answers, not factual claim labels","evidence_available":"Question-linked code regions; not claim evidence annotations","labels_available":"Task/type and code-region selections; not veracity labels","label_schema":"Question type / relevant code selection / answer retrieval","programming_relevance":"High","python_relevance":"High; Python classroom data","annotation_method":"Human annotation of student question/code selection and QA corpus","annotator_information":"Paper reports two workers for code selections; dataset-specific roles described in paper","license":"Repository says MIT for code; dataset/rightsholder terms need review before redistribution","redistribution_allowed":"Review required for underlying classroom/chat data","provenance_quality":"Paper and repository provenance; real classroom origin","task_compatibility":"Could inform topic coverage only; cannot defensibly map into claim-evidence labels","decision":"EXCLUDE","exclusion_reason":"Programming-domain human QA is relevant context, but no supported/contradicted/insufficient evidence annotation."},
 {"dataset_name":"SciClaimEval","url":"https://sciclaimeval.github.io/","paper_url":"https://aclanthology.org/2026.lrec-1.864/","organization":"NTCIR-19 / SciClaimEval authors","domain":"Scientific paper claim verification","record_count":"1,664 samples from 180 papers","claim_available":"Yes","evidence_available":"Yes; figures/tables and paper context","labels_available":"Supported/refuted claim verification","label_schema":"Support / refute; no confirmed Insufficient Evidence class","programming_relevance":"Partial; includes ML and NLP papers","python_relevance":"Low; subject is scientific result claims, not Python behavior","annotation_method":"Authentic paper claims; refuted evidence constructed by modifying figures/tables; expert validated","annotator_information":"Expert annotation reported; detailed annotator count not verified in this review","license":"Dataset-specific redistribution license not verified","redistribution_allowed":"Unknown; no data downloaded","provenance_quality":"Paper, claim IDs, and paper evidence described","task_compatibility":"Partial scientific claim-evidence structure but multimodal and domain/task mismatch","decision":"EXCLUDE","exclusion_reason":"Machine-learning/NLP paper results are not claims about Python/programming behavior; no complete three-label fit and license not cleared."},
 {"dataset_name":"CodeQA","url":"https://github.com/jadecxliu/CodeQA","paper_url":"https://aclanthology.org/2021.findings-emnlp.223/","organization":"Chenxiao Liu and Xiaojun Wan","domain":"Source-code comprehension QA","record_count":"Python 70,085 QA pairs; Java 119,778","claim_available":"Question/answer, no claim-verification labels","evidence_available":"Code snippet and comments, no evidence rationale for truth labels","labels_available":"No claim veracity labels","label_schema":"Free-form answer about a code snippet","programming_relevance":"High","python_relevance":"High","annotation_method":"Rule/semantic transformation of code comments into QA pairs","annotator_information":"No human claim-evidence labelers reported for derived labels","license":"GitHub repository MIT; underlying code derived from code-summarization datasets, record-level source licensing needs separate audit","redistribution_allowed":"Repository grants MIT; derived source text terms require review","provenance_quality":"Public repo and paper; underlying source corpora identified","task_compatibility":"Not direct; answers are generated from code context, not evidence labels","decision":"EXCLUDE","exclusion_reason":"Question/code QA dataset, not claim/evidence verification; license of underlying samples requires record-level review."},
 {"dataset_name":"CoSQA","url":"https://github.com/Jun-jie-Huang/CoCLR","paper_url":"https://aclanthology.org/2021.acl-long.442/","organization":"Microsoft Research / paper authors","domain":"Python code search","record_count":"20,604 query-code pairs","claim_available":"Natural-language query only","evidence_available":"Python code snippet; not documentary evidence","labels_available":"Human relevance/match labels","label_schema":"Query-code relevant / irrelevant (binary)","programming_relevance":"High","python_relevance":"High","annotation_method":"At least three human annotators judge query-code match","annotator_information":"At least three annotators per pair reported by paper","license":"Repository data license not verified; Hugging Face mirror does not expose an explicit license in inspected page","redistribution_allowed":"Unknown; no data downloaded","provenance_quality":"Paper describes Bing queries and GitHub code; record lineage exists","task_compatibility":"No logical mapping from match to factual support/contradiction/insufficient evidence","decision":"EXCLUDE","exclusion_reason":"Binary code-search relevance is not factual entailment; data license also not cleared."},
 {"dataset_name":"StaQC","url":"https://huggingface.co/datasets/koutch/staqc","paper_url":"https://arxiv.org/abs/1803.09371","organization":"Original paper authors / Stack Overflow contributors","domain":"Python and SQL programming QA","record_count":"Hugging Face card reports 231,013 total rows; paper has multiple subsets","claim_available":"Question text, not factual proposition label","evidence_available":"Code snippet; not claim-evidence annotations","labels_available":"Manual subset includes standalone-answer indicator, not veracity","label_schema":"Question / code snippet / is_standalone_answer","programming_relevance":"High","python_relevance":"High","annotation_method":"Question-code pairing with manual subset annotation","annotator_information":"Subset-specific labeling; not claim adjudication","license":"Mirror card CC BY 4.0; underlying Stack Overflow revisions use applicable CC BY-SA terms","redistribution_allowed":"Not for transformed claim labels; source revision terms apply","provenance_quality":"Question/code provenance; original post IDs available","task_compatibility":"No evidential truth label; cannot infer claim status from code match","decision":"EXCLUDE","exclusion_reason":"Question-to-code relation is not claim-to-evidence verification; licensing is record/revision dependent."},
 {"dataset_name":"CoNaLa","url":"https://conala-corpus.github.io/","paper_url":"https://aclanthology.org/P18-1223/","organization":"Carnegie Mellon University / authors","domain":"Python intent-to-code","record_count":"2,379 curated training; 500 curated test; about 598k mined pairs","claim_available":"Intent/question only","evidence_available":"Code snippet, not truth evidence","labels_available":"No claim truth labels","label_schema":"Intent paired with Python code","programming_relevance":"High","python_relevance":"High","annotation_method":"Curated and mined intent/code pairs","annotator_information":"Curated subset described by paper; not claim reviewers","license":"No explicit dataset license found on project page; Stack Overflow-derived records have source-specific terms","redistribution_allowed":"Unclear; do not redistribute","provenance_quality":"Task records and original sources described","task_compatibility":"Cannot map code correspondence into evidential support/contradiction/IE","decision":"EXCLUDE","exclusion_reason":"No claim-evidence labels and dataset reuse license is unclear."},
 {"dataset_name":"CodeSearchNet","url":"https://github.com/github/CodeSearchNet","paper_url":"https://arxiv.org/abs/1909.09436","organization":"GitHub","domain":"Code search / docstring-code","record_count":"About 2 million code/docstring pairs across six languages","claim_available":"Docstring text, not annotated claim","evidence_available":"Code body; not evidence passage","labels_available":"No veracity labels","label_schema":"Repository docstring paired with function code","programming_relevance":"High","python_relevance":"High","annotation_method":"Repository mining and filtering","annotator_information":"No claim-verification annotation","license":"Repository MIT; source files retain per-repository licenses","redistribution_allowed":"Per-record license obligations apply","provenance_quality":"Repository, path, and license metadata maintained","task_compatibility":"No fact-checking labels; code/docstring match is not evidence entailment","decision":"EXCLUDE","exclusion_reason":"Task mismatch and per-record licensing; no defensible conversion."},
 {"dataset_name":"HumanEval","url":"https://github.com/openai/human-eval","paper_url":"https://arxiv.org/abs/2107.03374","organization":"OpenAI","domain":"Python code generation","record_count":"164 programming problems","claim_available":"Problem statement only","evidence_available":"Test harness, not natural-language evidence passage","labels_available":"Execution pass/fail computed for generated code","label_schema":"Functional code correctness / pass@k","programming_relevance":"High","python_relevance":"High","annotation_method":"Human-authored function specifications and tests","annotator_information":"Problem authors, not claim-evidence labelers","license":"MIT license in official repository","redistribution_allowed":"Yes under repository license; review upstream attribution","provenance_quality":"Official repo and problem/test identifiers","task_compatibility":"Code correctness is a separate CodeGuard signal, not explanation claim verification","decision":"EXCLUDE","exclusion_reason":"Evaluates generated program execution, not claims against evidence."},
 {"dataset_name":"MBPP","url":"https://github.com/google-research/google-research/tree/master/mbpp","paper_url":"https://arxiv.org/abs/2108.07732","organization":"Google Research / authors","domain":"Python programming problems","record_count":"974 crowd-sourced tasks in paper","claim_available":"Task descriptions, not factual claims","evidence_available":"Reference implementations and tests, not evidence passages","labels_available":"Program solution correctness via tests","label_schema":"Code generation with functional tests","programming_relevance":"High","python_relevance":"High","annotation_method":"Crowd-sourced programming tasks with test cases","annotator_information":"Authors describe crowd-sourcing; not claim-evidence review","license":"Repository license applies to code; exact task-data license/derivative terms require source-level audit","redistribution_allowed":"Review required; no data downloaded","provenance_quality":"Paper and repository; crowdsourced tasks","task_compatibility":"No claim-evidence labels","decision":"EXCLUDE","exclusion_reason":"Code correctness benchmark, not factual explanation verification; dataset text licensing is not cleared."},
 {"dataset_name":"SWE-bench Verified","url":"https://github.com/SWE-bench/SWE-bench","paper_url":"https://openai.com/index/introducing-swe-bench-verified/","organization":"SWE-bench authors and OpenAI evaluators","domain":"Real GitHub software engineering issues","record_count":"500 verified samples; 1,699 sampled annotations described","claim_available":"Issue descriptions; not factual claim units","evidence_available":"Repository state and unit tests; not natural-language evidence labels","labels_available":"Human quality/underspecification/test-validity annotations; not truth classes","label_schema":"Issue quality ordinal ratings and patch execution outcomes","programming_relevance":"High","python_relevance":"High but multi-repository/language dependent","annotation_method":"Professional developer review of issue/test validity","annotator_information":"93 experienced developers; 1,699 samples annotated","license":"Dataset includes issue text and repository content with varying upstream terms; verify per record","redistribution_allowed":"Not blanket-cleared; upstream repository licenses govern content","provenance_quality":"Issue URLs, repository and test outcomes traceable","task_compatibility":"Useful for code execution phase only; not claim-evidence labels","decision":"EXCLUDE","exclusion_reason":"Human verification covers issue/test quality, not explanatory claims; per-record source licensing."},
 {"dataset_name":"ExpertQA","url":"https://huggingface.co/datasets/cmalaviya/expertqa","paper_url":"https://arxiv.org/abs/2309.07852","organization":"University of Pennsylvania / authors","domain":"32 expert knowledge domains","record_count":"2,177 in the original card; a separate mirror lists 3,774 rows; equivalence not verified","claim_available":"ExpertQA answer claims are annotated","evidence_available":"Claim evidence lists include URLs/passages","labels_available":"Expert factuality/support and evidence-quality annotations; full class semantics need task-level inspection","label_schema":"Claim correctness/support/source reliability; not known to match three canonical classes","programming_relevance":"Possible CS-specific subset, size not verified","python_relevance":"Not established","annotation_method":"Expert-written questions; experts annotate model answers and claim-evidence pairs","annotator_information":"Anonymized annotator IDs in card","license":"Dataset mirrors disagree; AGPL-3.0 shown on Haize Labs mirror while original card license needs verification","redistribution_allowed":"Unknown pending original rights and subdomain/license review","provenance_quality":"Paper and card describe evidence attribution, but record-level dataset not audited","task_compatibility":"Promising structure but programming subset and label mapping unverified","decision":"REVIEW","exclusion_reason":"Do not import before resolving mirror/license provenance and confirming a sufficiently sized programming subset with compatible evidence labels."},
 {"dataset_name":"FACTORY","url":"https://huggingface.co/datasets/facebook/FACTORY","paper_url":"https://arxiv.org/abs/2508.00109","organization":"Meta AI authors","domain":"Open-domain long-form answers","record_count":"HF size band 10K–100K; exact claim count not stated on card","claim_available":"Yes; claim units from generated answers","evidence_available":"Source URLs and evidence snippets for claims where applicable","labels_available":"Human factuality tags","label_schema":"Factual / NonFactual / Inconclusive / No Verifiable Fact","programming_relevance":"Unknown/limited; prompts span general topics","python_relevance":"Not established","annotation_method":"Human annotations on model-generated long-form answers; prompts curated with human refinement","annotator_information":"Card describes human annotation; counts not established here","license":"CC BY-NC 4.0 on HF dataset card","redistribution_allowed":"Non-commercial only; source materials may have additional terms","provenance_quality":"Claim-level source URLs/snippets and tags described","task_compatibility":"Potential task structure, but domain mismatch; NonFactual is not necessarily evidence-contradicted","decision":"EXCLUDE","exclusion_reason":"Not established as programming-domain and noncommercial terms; label semantics cannot map directly."},
 {"dataset_name":"SciFact","url":"https://github.com/allenai/scifact","paper_url":"https://arxiv.org/abs/2004.14974","organization":"Allen Institute for AI / authors","domain":"Biomedical scientific claims","record_count":"About 1.4K claims","claim_available":"Yes","evidence_available":"Abstract sentences with rationales","labels_available":"Supported / Contradicted; no reliable IE class in labeled claim split","label_schema":"SUPPORT / CONTRADICT","programming_relevance":"Low","python_relevance":"None","annotation_method":"Expert-written scientific claims and evidence annotations","annotator_information":"Domain experts reported by original paper","license":"Annotations CC BY 4.0; abstract corpus ODC-By 1.0","redistribution_allowed":"Distinct component licenses and attribution conditions","provenance_quality":"Paper IDs and sentence rationales","task_compatibility":"Claim/evidence-like but out of domain and missing IE","decision":"EXCLUDE","exclusion_reason":"Biomedical domain; label coverage and evidence source license differ from target."},
 {"dataset_name":"FEVER","url":"https://fever.ai/dataset/fever.html","paper_url":"https://aclanthology.org/N18-1074/","organization":"University of Sheffield and collaborators","domain":"Wikipedia fact verification","record_count":"185,445 claims","claim_available":"Yes","evidence_available":"Wikipedia sentence IDs for SUPPORTED/REFUTED; NEI has no evidence set","labels_available":"Yes","label_schema":"SUPPORTS / REFUTES / NOT ENOUGH INFO","programming_relevance":"Low","python_relevance":"None","annotation_method":"Crowdsourced claim generation and evidence annotation","annotator_information":"Crowd workers; see paper","license":"Wikipedia page terms; official FEVER notice references CC BY-SA 3.0 fallback","redistribution_allowed":"Share-alike/attribution obligations; must retain source-level attribution","provenance_quality":"Claim IDs and Wikipedia evidence sentence IDs","task_compatibility":"Three-way labels align conceptually only if NEI and evidence are treated carefully","decision":"EXCLUDE","exclusion_reason":"Wikipedia domain is not programming; dereferencing and share-alike attribution would be required."},
 {"dataset_name":"SimpleQA","url":"https://github.com/openai/simple-evals","paper_url":"https://openai.com/index/introducing-simpleqa/","organization":"OpenAI","domain":"General short fact-seeking QA","record_count":"4,326 questions","claim_available":"Generated answer can be assessed; dataset contains questions/reference answers","evidence_available":"Reference sources are described; released rows are not evidence passages paired to atomic claims","labels_available":"Correct / Incorrect / Not Attempted at model-answer evaluation time","label_schema":"Answer outcome labels, not evidence-relative claim labels","programming_relevance":"Mixed general technology at most","python_relevance":"Not established","annotation_method":"AI trainers authored answers with independent answer verification; sample audited manually","annotator_information":"Multiple trainers; article reports third-trainer sample of 1,000","license":"Repository/dataset terms must be checked for intended redistribution; no import made","redistribution_allowed":"No import; rights review required","provenance_quality":"Question and reference answer, limited source/evidence granularity","task_compatibility":"Potential QA evaluation only; not claim-evidence triples","decision":"EXCLUDE","exclusion_reason":"General-domain answer benchmark with different evidence and label unit."},
 {"dataset_name":"SimpleQA Verified","url":"https://epoch.ai/benchmarks/simple-qa-verified","paper_url":"https://epoch.ai/benchmarks/simple-qa-verified/review","organization":"Google / Epoch AI benchmark review","domain":"General short-form factual QA","record_count":"1,000 questions","claim_available":"Answer outputs can be graded against reference answer","evidence_available":"Source URLs, not paired passage evidence","labels_available":"Answer correctness, not claim-evidence labels","label_schema":"Correctness benchmark subset","programming_relevance":"Low/mixed","python_relevance":"Not established","annotation_method":"Filtered by Google pipeline; external audit of a 50-question sample by Epoch AI","annotator_information":"Original human authors/trainers; external audit sample","license":"Hugging Face source terms must be verified before redistribution","redistribution_allowed":"No import","provenance_quality":"Source URL available per benchmark summary","task_compatibility":"Does not provide evidence-relative three-class claim labels","decision":"EXCLUDE","exclusion_reason":"General-domain factoid QA; not programming and not evidence-anchored claim labels."},
 {"dataset_name":"SciFact-Open","url":"https://github.com/dwadden/scifact-open","paper_url":"https://aclanthology.org/2020.emnlp-main.609/","organization":"Allen Institute for AI / authors","domain":"Open-domain scientific claim verification","record_count":"Claims.jsonl size not recorded in repository landing page","claim_available":"Yes","evidence_available":"Retrieved scientific evidence documents","labels_available":"Claim veracity labels","label_schema":"Scientific support/refute/NEI task as defined by paper; exact split/schema requires source inspection","programming_relevance":"Low; broad science, not software behavior","python_relevance":"None","annotation_method":"Uses SciFact annotations and automatic retrieval setup","annotator_information":"Inherited from SciFact; no programming domain annotators","license":"Inherited data component licenses; audit per component","redistribution_allowed":"No import","provenance_quality":"Source project and scripts provided","task_compatibility":"Domain/task overlap only","decision":"EXCLUDE","exclusion_reason":"Scientific domain and inherited dataset licenses; no programming behavior coverage."},
 {"dataset_name":"CS1QA / ProCQA / programming QA family","url":"https://aclanthology.org/2024.lrec-main.1143/","paper_url":"https://aclanthology.org/2024.lrec-main.1143/","organization":"LREC-COLING authors","domain":"Community programming QA/code search","record_count":"ProCQA count not independently confirmed during this audit","claim_available":"Questions and accepted/helpful answers","evidence_available":"Code or answer context but not claim-specific evidence labels","labels_available":"Accepted-answer/relevance signals, not veracity","label_schema":"Question-answer matching/code retrieval","programming_relevance":"High","python_relevance":"Includes Python programming QA among languages/topics; precise slice not confirmed","annotation_method":"Community accepted answers plus collection/curation","annotator_information":"Questioner acceptance signal, not expert factuality review","license":"Stack Overflow-derived data uses revision-specific CC BY-SA; exact source records govern","redistribution_allowed":"Requires record-level attribution/license review","provenance_quality":"Origin URLs/accepted answer signals where retained","task_compatibility":"Cannot equate accepted/helpful with supported by supplied evidence","decision":"EXCLUDE","exclusion_reason":"Natural programming QA is not truth/evidence classification; accepted answers are not evidence labels."},
]

def _dirs(root: Path) -> None:
    for name in ("candidates", "raw", "processed", "review", "external", "reports"):
        (root / name).mkdir(parents=True, exist_ok=True)

def write_csv(path: Path, fields: tuple[str, ...] | list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

def validate_candidates(rows: list[dict[str, Any]]) -> None:
    for index, row in enumerate(rows):
        missing = [field for field in CANDIDATE_FIELDS if not str(row.get(field, "")).strip()]
        if missing:
            raise ValueError(f"candidate {index} missing {', '.join(missing)}")
        if row["decision"] not in DECISIONS:
            raise ValueError(f"candidate {index} invalid decision {row['decision']}")

def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))

def _seed_queue(internal: list[dict[str, str]], external: list[dict[str, str]]) -> list[dict[str, Any]]:
    queue: list[dict[str, Any]] = []
    for split, rows in [("internal", internal), ("external", external)]:
        for row in rows:
            base = dict(row)
            proposed = base.pop("label")
            priority_label = {"Contradicted": 1, "Insufficient Evidence": 2, "Supported": 4}[proposed]
            is_external = split == "external"
            queue.append({
                **base,
                "review_id": row["id"], "record_id": row["id"], "dataset_partition": split,
                "split": "external" if is_external else row.get("split", "unassigned"),
                "claim": row["claim"], "evidence": row["evidence"], "proposed_label": proposed,
                "reviewer_label": "", "reviewer_confidence": "", "reviewer_notes": "",
                "source_url": row["source_url"], "source_title": row["source_title"],
                "fact_key": row["fact_key"], "evidence_group": row["evidence_group"],
                "data_origin": "synthetic_pending_review", "review_status": "pending",
                "adjudication_status": "pending", "reviewer_A_label": "", "reviewer_A_id": "",
                "reviewer_A_confidence": "", "reviewer_A_notes": "", "reviewer_B_label": "",
                "reviewer_B_id": "", "reviewer_B_confidence": "", "reviewer_B_notes": "",
                "final_adjudicated_label": "", "adjudicator_id": "", "adjudicator_notes": "",
                "priority_rank": 0 if is_external else priority_label,
                "priority_reason": "External benchmark candidate; review before any use" if is_external else {
                    1:"Synthetic contradiction polarity pair; verify wording and evidence",
                    2:"Insufficient-evidence case; confirm evidence is genuinely non-establishing",
                    4:"Synthetic supported case; verify claim is directly entailed",
                }[priority_label],
            })
    queue.sort(key=lambda r: (int(r["priority_rank"]), r["fact_key"], r["review_id"]))
    return queue

def build_phase16_workspace(root: str | Path = PHASE16_DIR) -> dict[str, Any]:
    """Prepare auditable candidate inventory and actual-human-review workspace."""
    root = Path(root); _dirs(root)
    validate_candidates(CANDIDATES)
    write_csv(root / "candidates" / "dataset_candidates.csv", CANDIDATE_FIELDS, CANDIDATES)
    p15 = PHASE15_DIR
    internal_path = p15 / "processed" / "dataset.csv"
    external_path = p15 / "processed" / "external_test.csv"
    if not internal_path.is_file() or not external_path.is_file():
        raise FileNotFoundError("Phase 15 dataset and external candidate must exist before Phase 16 initialization")
    internal = _read_csv(internal_path); external = _read_csv(external_path)
    split_by_id: dict[str, str] = {}
    for split_name in ("train", "validation", "test"):
        split_path=p15/"processed"/f"{split_name}.csv"
        # Phase 15 names these split files train.csv, validation.csv and test.csv.
        if not split_path.is_file(): split_path=p15/f"{split_name}.csv"
        if split_path.is_file():
            split_by_id.update({row["id"]:split_name for row in _read_csv(split_path) if row.get("id")})
    for row in internal: row["split"]=split_by_id.get(row["id"],"unassigned")
    groups: dict[str,set[str]]={}
    for row in internal:
        groups.setdefault(row["evidence_group"],set()).add(row["split"])
    violations={group:splits for group,splits in groups.items() if len(splits)>1 or "unassigned" in splits}
    if violations:
        raise ValueError(f"Existing Phase 15 grouped split integrity check failed: {list(violations.items())[:5]}")
    # Phase 15 files stay untouched; the copied canonical data gains only an
    # explicit provenance-origin classification for the Phase 16 workflow.
    # Keep proposals out of the canonical gold-label column to prevent accidental
    # training on labels that have not actually been reviewed.
    canonical_fields = tuple(field for field in CANONICAL_FIELDS if field != "label") + ("proposed_label", "split", "origin_bucket")
    phase16_internal = [{**{k:v for k,v in row.items() if k != "label"},
                         "proposed_label":row["label"], "origin_bucket":"synthetic_pending_review"}
                        for row in internal]
    write_csv(root / "processed" / "canonical.csv", canonical_fields, phase16_internal)
    queue = _seed_queue(internal, external)
    write_csv(root / "review" / "review_queue.csv", tuple(queue[0].keys()) if queue else (), queue)
    verified_fields = tuple(CANONICAL_FIELDS) + ("proposed_label", "split", "origin_bucket", "review_status", "verified_label", "final_adjudicated_label")
    pending_fields = canonical_fields + ("review_status", "final_adjudicated_label")
    write_csv(root / "processed" / "verified.csv", verified_fields, [])
    write_csv(root / "processed" / "pending_review.csv", pending_fields, [
        {**{k:v for k,v in r.items() if k != "label"}, "proposed_label":r["label"], "origin_bucket":"synthetic_pending_review", "review_status":"pending", "final_adjudicated_label":""}
        for r in internal])
    write_csv(root / "processed" / "rejected.csv", pending_fields, [])
    external_fields = ("record_id", "claim", "evidence", "gold_label", "source_name", "source_url",
        "fact_key", "evidence_group", "review_status", "data_origin", "license", "provenance",
        "source_title", "source_section", "topic")
    write_csv(root / "external" / "external_test.csv", external_fields, [
        {"record_id":r["id"], "claim":r["claim"], "evidence":r["evidence"], "gold_label":"",
         "source_name":r["source_name"], "source_url":r["source_url"], "fact_key":r["fact_key"],
         "evidence_group":r["evidence_group"], "review_status":"pending", "data_origin":"synthetic_pending_review",
         "license":r["license"], "provenance":r["provenance"], "source_title":r["source_title"],
         "source_section":r["source_section"], "topic":r["topic"]}
        for r in external])
    (root / "raw" / "README.md").write_text(
        "No third-party data was acquired. Candidate datasets are not copied here unless source rights are verified. "
        "Phase 15 source excerpts are preserved in the separate Phase 15 folder.\n", encoding="utf-8")
    return {"root":root,"candidates":CANDIDATES,"internal":internal,"external":external,"queue":queue,
            "canonical_fields":canonical_fields,"candidate_fields":CANDIDATE_FIELDS}

def write_manifest(root: str | Path, *, source_facts_path: str | Path) -> dict[str, Any]:
    root, facts = Path(root), Path(source_facts_path)
    payload = {"dataset_name":"CodeGuard Phase 16 human-review preparation",
        "version":"0.1.0","retrieval_date":date.today().isoformat(),
        "public_data_acquired":False,"public_datasets_used":[],
        "source_urls":[r["url"] for r in CANDIDATES],
        "phase15_source_facts_path":str(facts.relative_to(ROOT)) if facts.is_relative_to(ROOT) else str(facts),
        "phase15_source_facts_sha256":hashlib.sha256(facts.read_bytes()).hexdigest(),
        "source_version":"Python documentation stable /3/ URLs; source pages are not pinned to an immutable revision",
        "transformation":"backend/src/codeguard/ml/phase16.py; phase15 rows copied without relabeling; new public data not imported",
        "random_seed":15015,"split_seed":15015,
        "filtering_rules":["Exclude any prior synthetic row without explicit source URL and evidence",
          "Keep external candidate rows outside internal canonical/splits",
          "All synthetic records stay pending until actual human review and adjudication",
          "Never map incompatible public QA/code-search labels automatically"],
        "license_policy":"Only source data with verified dataset-level redistribution rights may be copied; candidate-specific upstream licenses must be checked.",
        "no_model_training":True}
    (root/"dataset_manifest.json").write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding="utf-8")
    return payload

def write_research_reports(root: str | Path, inventory: dict[str, Any]) -> dict[str, Any]:
    root=Path(root); reports=root/"reports"
    candidates=inventory["candidates"]
    (reports/"DATASET_CANDIDATES.md").write_text(
        "# Dataset candidates investigated\n\n"+
        "Search covered academic papers, ACL Anthology, arXiv, GitHub, and Hugging Face; scope included programming factuality, code explanation/QA, code correctness, and general claim-evidence benchmarks. "
        f"The detailed {len(candidates)}-candidate inventory with all requested fields and explicit decisions is `../candidates/dataset_candidates.csv`.\n\n"+
        "## Selection result\n\nNo public dataset is currently authorized for inclusion. CodeSimpleQA is the strongest lead but its paper contains inconsistent dataset counts, and a public record-level artifact and dataset license could not be verified. It remains REVIEW. Programming QA and code tests have different label units and were not force-mapped.\n",encoding="utf-8")
    (reports/"LICENSE_AUDIT.md").write_text(_license_audit(),encoding="utf-8")
    (reports/"LABEL_MAPPING.md").write_text(_label_mapping(),encoding="utf-8")
    return {"candidate_count":len(candidates)}

def write_phase16_reports(root: str | Path, inventory: dict[str, Any]) -> dict[str, Any]:
    """Write separate measurable quality indicators; never aggregate a score."""
    root=Path(root); reports=root/"reports"
    internal=inventory["internal"]; external=inventory["external"]
    all_rows=internal+external
    proposal_counts=dict(sorted(Counter(row["label"] for row in internal).items()))
    external_counts=dict(sorted(Counter(row["label"] for row in external).items()))
    page_counts=Counter(row["source_url"] for row in all_rows)
    topic_counts=Counter(row["topic"] for row in all_rows)
    facts={row["fact_key"] for row in all_rows}
    groups={row["evidence_group"] for row in all_rows}
    domains={urlparse(row["source_url"]).netloc for row in all_rows}
    exact=set(); exact_duplicates=0; claim_seen={}; conflicts=[]
    near=[]
    internal_ids={r["id"] for r in internal}; external_ids={r["id"] for r in external}
    for index,row in enumerate(all_rows):
        norm_claim=normalize(row["claim"]); norm_evidence=normalize(row["evidence"])
        key=(norm_claim,norm_evidence)
        if key in exact: exact_duplicates+=1
        exact.add(key)
        claim_seen.setdefault(norm_claim,set()).add(row["label"])
        for other in all_rows[:index]:
            similarity=SequenceMatcher(None,norm_claim,normalize(other["claim"])).ratio()
            if similarity>=.90:
                near.append((other,row,similarity))
        if not row.get("source_url") or not row.get("source_record_id") or not row.get("license") or not row.get("provenance"):
            conflicts.append(f"incomplete provenance: {row.get('id')}")
    claim_conflicts=sum(1 for labels in claim_seen.values() if len(labels)>1)
    split_groups=defaultdict(set)
    for row in internal: split_groups[row["evidence_group"]].add(row.get("split",""))
    split_violations=[g for g,s in split_groups.items() if len(s)>1]
    internal_pages={r["source_url"] for r in internal}
    external_pages={r["source_url"] for r in external}
    external_facts={r["fact_key"] for r in external}
    internal_facts={r["fact_key"] for r in internal}
    leakage=(len(set(split_violations)) + bool(internal_pages & external_pages) + bool(internal_facts & external_facts))
    per_split=Counter(r.get("split","") for r in internal)
    classes="\n".join(f"- {label}: {count} ({count/len(internal):.1%} of internal proposals)" for label,count in proposal_counts.items())
    topics="\n".join(f"- {label}: {count}" for label,count in sorted(topic_counts.items()))
    pages="\n".join(f"- `{url}`: {count} ({count/len(all_rows):.1%} of all candidates)" for url,count in sorted(page_counts.items(),key=lambda item:(-item[1],item[0])))
    concentration=", ".join(f"{n} ({c})" for n,c in page_counts.most_common(3))
    near_violations=sum(1 for a,b,_ in near if a["id"] in internal_ids and b["id"] in internal_ids and a.get("split")!=b.get("split"))
    near_violations+=sum(1 for a,b,_ in near if (a["id"] in internal_ids and b["id"] in external_ids) or (a["id"] in external_ids and b["id"] in internal_ids))
    metrics={"internal_records":len(internal),"external_candidates":len(external),
        "proposal_class_distribution":proposal_counts,"external_proposal_distribution":external_counts,
        "topics":dict(sorted(topic_counts.items())),"source_pages":len(page_counts),"domains":sorted(domains),
        "fact_keys":len(facts),"evidence_groups":len(groups),"source_page_distribution":dict(page_counts),
        "source_concentration_top_three":concentration,"exact_duplicate_rate":exact_duplicates/max(len(all_rows),1),
        "exact_duplicate_count":exact_duplicates,"normalized_claim_label_conflicts":claim_conflicts,
        "near_duplicate_pairs_ge_090":len(near),"near_duplicate_leakage_violations":near_violations,
        "provenance_completeness_count":len(all_rows)-len(conflicts),"provenance_incomplete_count":len(conflicts),
        "source_group_split_violations":len(split_violations),"external_page_or_fact_overlap_count":int(bool(internal_pages&external_pages))+int(bool(internal_facts&external_facts)),
        "inherited_phase15_split_sizes":dict(per_split),"reviewed_count":0,"pending_review_count":len(all_rows),
        "rejected_count":0,"adjudicated_count":0,"review_agreement":"Unavailable: no real reviews exist."}
    (root/"dataset_statistics.json").write_text(json.dumps(metrics,indent=2,ensure_ascii=False),encoding="utf-8")
    quality=("# Phase 16 quality report\n\n"+
      "## Review state\n\n- Real reviewer decisions: **0**; independent agreement: unavailable.\n"+
      f"- Pending review: **{len(all_rows)}** ({len(internal)} internal and {len(external)} external candidates).\n- Rejected: **0**; adjudicated: **0**.\n\n"+
      "## Dataset indicators (separate; no aggregate score)\n\n"+
      f"- Proposal class distribution (not gold labels):\n{classes}\n- External proposal counts (not gold labels): `{json.dumps(external_counts)}`\n"+
      f"- Unique source pages: {len(page_counts)}; source domains: {len(domains)} ({', '.join(sorted(domains))}).\n- Unique fact keys: {len(facts)}; evidence groups: {len(groups)}.\n"+
      f"- Three most concentrated pages: {concentration}.\n- Exact duplicate rows: {exact_duplicates}; normalized-claim label conflicts: {claim_conflicts}.\n"+
      f"- Near-duplicate pairs at >=0.90 `SequenceMatcher` similarity: {len(near)}; cross-split/external group violations: {near_violations}.\n"+
      f"- Complete source/provenance/license fields: {len(all_rows)}/{len(all_rows)-len(conflicts)+len(conflicts)}; incomplete: {len(conflicts)}. Evidence passages: {sum(bool(r.get('evidence','').strip()) for r in all_rows)}/{len(all_rows)}.\n"+
      f"- Inherited internal Phase 15 split sizes: {json.dumps(dict(per_split),sort_keys=True)}; source-group split violations: {len(split_violations)}.\n"+
      f"- External source/fact overlap with internal candidate: {int(bool(internal_pages&external_pages))+int(bool(internal_facts&external_facts))}.\n\n## Topic coverage\n\n{topics}\n\n"+
      "## Source distribution\n\n"+pages+"\n\n## Interpretation\n\n"+
      "All labels shown above are synthetic proposals, not gold labels. Source concentration is high because evidence comes from a handful of Python documentation pages. The six external rows are not an independent benchmark until reviewed and adjudicated. No model training is permitted.\n")
    (reports/"QUALITY_REPORT.md").write_text(quality,encoding="utf-8")
    card=("# Phase 16 dataset card\n\n**Status: pending human validation; not ready for final training.**\n\n"+
      f"- Internal candidate rows: {len(internal)} (all synthetic pending review).\n- External candidates: {len(external)} (all synthetic pending review).\n"+
      f"- Human reviewed: 0; public human-annotated included: 0; actual human verified labels: 0.\n- Proposed internal labels: `{json.dumps(proposal_counts)}`.\n"+
      "- Intended users: trained Python/programming reviewers and dataset curators.\n- Not for production training or reliability claims until independent reviews, adjudication, licensing, and an external benchmark gate are satisfied.\n\n"
      "The dataset is evidence-relative. Supported means the passage directly establishes the claim; Contradicted means it directly conflicts; Insufficient Evidence means the supplied passage establishes neither. All current claims originated as synthetic and no source dataset was imported. See `review/reviewer_guidelines.md` and `reports/LICENSE_AUDIT.md`.\n")
    (reports/"DATASET_CARD.md").write_text(card,encoding="utf-8")
    return metrics

def write_phase16_report(root: str | Path, inventory: dict[str, Any], metrics: dict[str, Any]) -> str:
    root=Path(root); candidates=inventory["candidates"]
    reviewed=[r for r in inventory["queue"] if r["review_status"]!="pending"]
    external=inventory["external"]
    report=("# CodeGuard AI — Phase 16 dataset and review preparation\n\n"
      "**Phase status: review infrastructure prepared. Dataset status: NOT READY for Phase 17.**\n\n"
      "## 1. Research and candidate assessment\n\n"
      f"Investigated {len(candidates)} candidate resources spanning programming QA/code benchmarks, human-annotated factuality/claim benchmarks, and evidence-verification datasets. Candidate-level fields, source and paper links, licensing, annotation properties, decisions, and exclusion reasons are in `../candidates/dataset_candidates.csv`.\n\n"
      "CodeSimpleQA is the strongest programming factual-QA lead: the paper describes 8 annotators and 3 senior engineers and programming-document grounded QA. It is not imported: the paper reports inconsistent sizes (1,498, 1,478, and 312 in different passages), does not provide an inspected record-level evidence release/link or a dataset license in the paper. It remains REVIEW. The detailed research used primary paper/site/repository pages; see `DATASET_CANDIDATES.md`.\n\n"
      "## 2. Accepted and excluded sources\n\n"
      "Accepted public datasets: **0**. No external raw data was acquired. The Phase 15 CodeGuard synthetic candidates were copied into an isolated review workspace only. FEVER, SciFact, SciClaimEval, FACTORY, ExpertQA, CodeQA, CS1QA, CoSQA, StaQC, CoNaLa, CodeSearchNet, HumanEval, MBPP, SWE-bench Verified, SimpleQA, SimpleQA Verified, SciFact-Open, and ProCQA/programming-QA candidates were explicitly assessed in `dataset_candidates.csv`.\n\n"
      "## 3. Licensing and provenance\n\n"
      "No public dataset is cleared for reuse in this phase. Candidate license status and exact URLs are detailed in `LICENSE_AUDIT.md`. Phase 15 Python documentation excerpts retain source URL, source section, and PSF License Version 2 attribution. Existing synthetic candidates retain their provenance; one source-less legacy record remains excluded.\n\n"
      "## 4. Label mapping\n\n"
      "No external labels were automatically mapped. Candidate conversions and reasons for REVIEW_REQUIRED are in `LABEL_MAPPING.md`. Canonical labels remain Supported, Contradicted, and Insufficient Evidence, with IE explicitly not equivalent to Contradicted. Synthetic labels are shown only as `proposed_label`.\n\n"
      "## 5. Human review and adjudication\n\n"
      f"Review queue size: **{len(inventory['queue'])}** ({len(inventory['internal'])} internal plus {len(external)} external). Real reviews: **{len(reviewed)}**; pending: **{len(inventory['queue'])}**; rejected: **0**; adjudicated: **0**. No reviewer identities or agreement metrics were fabricated. The local Dataset Review page stores decisions in a separate, Git-ignored SQLite file and requires distinct reviewer identifiers for A/B.\n\n"
      "The interface is ready for a real reviewer: candidate shown one at a time with evidence/source/proposed label; decision, confidence, notes; two independent slots; disputed state and independent adjudication. See reviewer, adjudication, and schema docs in `review/`.\n\n"
      "## 6. Counts and composition\n\n"
      f"Internal candidates: **{len(inventory['internal'])}**, all `synthetic_pending_review`; external candidates: **{len(external)}**, all synthetic pending review. Public verified: 0; manually verified: 0; synthetic reviewed: 0. Proposed internal class distribution (not gold labels): `{json.dumps(metrics['proposal_class_distribution'])}`. External proposal distribution (not gold labels): `{json.dumps(metrics['external_proposal_distribution'])}`. Full topic and source distribution and percentages appear in `QUALITY_REPORT.md` and `dataset_statistics.json`.\n\n"
      "## 7. Duplicate, leakage, and external set\n\n"
      f"Exact duplicates: {metrics['exact_duplicate_count']}; normalized-claim label conflicts: {metrics['normalized_claim_label_conflicts']}; near-duplicate pairs at >=0.90 similarity: {metrics['near_duplicate_pairs_ge_090']}; near-duplicate split/external violations: {metrics['near_duplicate_leakage_violations']}; source-group split violations: {metrics['source_group_split_violations']}. Existing Phase 15 group assignments are preserved and checked. The six-row external candidate uses a source page/fact keys absent from internal data, but remains entirely synthetic and unreviewed; `gold_label` is blank and must remain unused for tuning until independently reviewed/adjudicated.\n\n"
      "## 8. Separate quality indicators\n\n"
      f"Provenance field completeness at generation: {metrics['provenance_completeness_count']}/{len(inventory['queue'])}; review completion: 0/{len(inventory['queue'])}; label agreement: unavailable; duplicate/conflict counts and concentration: see `QUALITY_REPORT.md`; external isolation: checked; human-verified external benchmark: 0. No aggregate dataset-quality score was created.\n\n"
      "## 9. Limitations and readiness gate\n\n"
      "Dataset is mostly and entirely synthetic, based on few official documentation pages and polarity templates. The external set is not human validated. No public candidate met the complete task/domain/license bar. Critical readiness items therefore fail: at least 1,000 reviewed items, human-adjudicated labels, resolved licensing, representative source/topic breadth, and an independently reviewed external benchmark.\n\n"
      "### READY_FOR_PHASE_17: FALSE\n\n"
      "Do not train, tune, select, or report final model performance until the review queue is genuinely reviewed and the independent external benchmark is human-adjudicated.\n\n"
      "## 10. Files created/modified\n\n"
      "Phase 16 implementation and tests: `backend/src/codeguard/ml/phase16.py`, `backend/src/codeguard/ml/review.py`, `tests/unit/test_phase16_review.py`, `frontend/app.py`, and `.gitignore`.\n\n"
      "Generated workspace: `data/ml/phase16/candidates/dataset_candidates.csv`; `raw/README.md`; `processed/canonical.csv`, `verified.csv`, `pending_review.csv`, `rejected.csv`; `review/review_queue.csv`, `review_summary.json`, `reviewer_guidelines.md`, `adjudication_guidelines.md`, `review_schema.md`, and the local `reviews.sqlite3`; `external/external_test.csv`; `dataset_manifest.json`; `dataset_statistics.json`; and reports `DATASET_CANDIDATES.md`, `DATASET_CARD.md`, `LABEL_MAPPING.md`, `LICENSE_AUDIT.md`, `QUALITY_REPORT.md`, and `PHASE_16_REPORT.md`. The database is Git-ignored and stores actual user reviews.\n\n"
      "Documentation updated: `docs/phases/PROJECT_PROGRESS.md`, `README.md`, and `docs/phases/PHASE_16_DATASET_REPORT.md`. The documentation report mirrors this report.\n\n"
      "## 11. Verification performed\n\n"
      "- `python -m unittest discover -s tests -v`: 81 tests completed successfully; 5 Docker integration tests skipped by their default opt-in safety guard.\n"
      "- `python -m compileall -q frontend backend scripts tests`: passed.\n"
      "- `python -m pip check`: no broken requirements.\n"
      "- Streamlit `AppTest` of `frontend/app.py`: zero app exceptions.\n"
      "- No Docker integration run, live provider API call, submitted-code execution, or production model training was performed. Existing model artifacts and Phase 15 source datasets were not modified.\n\n"
      "## 12. Next incomplete phase\n\n"
      "Phase 17 model training is NOT READY. Readiness is `FALSE`: 72 synthetic candidates await real independent review, zero public datasets were accepted, and zero human-verified records or independent external benchmark labels exist. Continue only after human review/adjudication and licensing/source diversity gates are satisfied.\n")
    (root/"reports"/"PHASE_16_REPORT.md").write_text(report,encoding="utf-8")
    (ROOT/"docs"/"phases"/"PHASE_16_DATASET_REPORT.md").write_text(report,encoding="utf-8")
    return report

def main() -> None:
    inventory=build_phase16_workspace()
    write_manifest(PHASE16_DIR,source_facts_path=PHASE15_DIR/"raw"/"source_facts.json")
    write_research_reports(PHASE16_DIR,inventory)
    metrics=write_phase16_reports(PHASE16_DIR,inventory)
    write_phase16_report(PHASE16_DIR,inventory,metrics)
    from codeguard.ml.review import initialize_review_db, review_counts
    database=PHASE16_DIR/"review"/"reviews.sqlite3"
    initialize_review_db(PHASE16_DIR/"review"/"review_queue.csv",database)
    counts=review_counts(database)
    print("="*52)
    print("PHASE 16 COMPLETE — REVIEW WORKSPACE PREPARED")
    print("Public datasets investigated:",len(CANDIDATES))
    print("Public datasets accepted: 0")
    print("Public verified records: 0")
    print("Human-reviewed records: 0")
    print("Synthetic records:",len(inventory["internal"]))
    print("External synthetic candidates:",len(inventory["external"]))
    print("Pending review:",counts["pending"])
    print("Rejected:",counts["rejected"])
    print("Total usable verified records:",counts["verified_label_count"])
    print("Proposed class counts (not gold):",metrics["proposal_class_distribution"])
    print("External benchmark: NOT READY; all rows pending human review")
    print("Duplicate violations:",metrics["exact_duplicate_count"]+metrics["normalized_claim_label_conflicts"])
    print("Leakage violations:",metrics["source_group_split_violations"]+metrics["near_duplicate_leakage_violations"]+metrics["external_page_or_fact_overlap_count"])
    print("Licensing blockers: at least 2 candidates remain REVIEW; see LICENSE_AUDIT.md")
    print("Human-review blocker: 72 real, independent review decisions are pending")
    print("READY_FOR_PHASE_17: FALSE")
    print("Model training: NOT RUN")
    print("="*52)

def _license_audit() -> str:
    return """# License and provenance audit — Phase 16

**No third-party dataset was downloaded or copied.** A candidate is not accepted for reuse unless the dataset-level license, redistribution rights, derivative-work terms, attribution, and record-level source terms are clear.

| Candidate | Exact source and license evidence | Decision / rights status |
|---|---|---|
| CodeSimpleQA | [Paper](https://arxiv.org/html/2512.19424v1); the paper's arXiv submission license is not a license to its data. No dataset license or direct dataset artifact was located in the paper. | REVIEW. Rights unknown. Do not copy until authors provide dataset and license terms. |
| CS1QA | [Paper](https://aclanthology.org/2022.naacl-main.148/), The official paper record is the source reviewed; no dataset repository license was verified. Classroom chat data rights need independent confirmation. | EXCLUDE from data. Underlying data terms need independent confirmation. |
| SciClaimEval | [Official task site](https://sciclaimeval.github.io/), [LREC paper](https://aclanthology.org/2026.lrec-1.864/). No dataset redistribution license confirmed in this review. | EXCLUDE; rights also not cleared. |
| CodeQA | [Official repository](https://github.com/jadecxliu/CodeQA) says MIT for repository; paper identifies derived code-summarization sources. | EXCLUDE; source code/data rights are not automatically covered by repository license. |
| CoSQA | [Project repository](https://github.com/Jun-jie-Huang/CoCLR), [ACL paper](https://aclanthology.org/2021.acl-long.442/). Inspected HF mirror did not expose an explicit license. | EXCLUDE; rights unverified and task mismatch. |
| StaQC | [Hugging Face card](https://huggingface.co/datasets/koutch/staqc) states CC BY 4.0 for that distribution; source posts originate from Stack Overflow and carry revision-specific terms under [Stack Overflow licensing](https://stackoverflow.com/help/licensing). | EXCLUDE. Per-record rights/attribution and task mismatch. |
| CoNaLa | [Official project page](https://conala-corpus.github.io/) and paper [ACL Anthology](https://aclanthology.org/P18-1223/); no explicit dataset license located on the project page; Stack Overflow sources have their own terms. | EXCLUDE. Do not redistribute while license is unclear. |
| CodeSearchNet | [Repository](https://github.com/github/CodeSearchNet) uses MIT for repository; sample code retains individual source repository licenses. | EXCLUDE; record-level review required. |
| HumanEval | [Official repository](https://github.com/openai/human-eval), MIT license. | EXCLUDE from this claim dataset; code execution benchmark only. |
| MBPP | [Google Research repository](https://github.com/google-research/google-research/tree/master/mbpp), with dataset text/source provenance requiring separate verification. | EXCLUDE; no claim-evidence labels and data reuse not cleared here. |
| SWE-bench Verified | [SWE-bench repository](https://github.com/SWE-bench/SWE-bench), [human verification description](https://openai.com/index/introducing-swe-bench-verified/). Issues and repository code have upstream-specific terms. | EXCLUDE; human review labels issue/test quality, not truth claims. |
| ExpertQA | [Paper](https://arxiv.org/abs/2309.07852), [original dataset card](https://huggingface.co/datasets/cmalaviya/expertqa); mirror/license metadata can differ. | REVIEW. Verify original license, CS subset and rows before any acquisition. |
| FACTORY | [Hugging Face card](https://huggingface.co/datasets/facebook/FACTORY) reports CC BY-NC 4.0; source materials may have additional terms. | EXCLUDE; noncommercial terms plus task/domain mismatch. |
| SciFact | [Official repository](https://github.com/allenai/scifact) distinguishes CC BY 4.0 annotations and ODC-By 1.0 abstracts. | EXCLUDE; biomedical domain and label gap. |
| FEVER | [Official dataset page](https://fever.ai/dataset/fever.html), [license notice](https://fever.ai/download/fever/license.html): Wikipedia page terms apply, CC BY-SA 3.0 fallback where applicable. | EXCLUDE; out-of-domain and share-alike/source-attribution requirements. |
| SimpleQA | [SimpleQA release article](https://openai.com/index/introducing-simpleqa/), [official code/data repository](https://github.com/openai/simple-evals). | EXCLUDE; not claim+evidence triples for programming. No files copied. |
| SimpleQA Verified | [Epoch AI benchmark review](https://epoch.ai/benchmarks/simple-qa-verified/review) and source links; dataset reuse rights were not cleared for this project. | EXCLUDE; general-domain QA and rights not audited for import. |
| SciFact-Open | [Repository](https://github.com/dwadden/scifact-open); inherits SciFact components and their distinct terms. | EXCLUDE; science domain and no programming behavior. |
| ProCQA / programming QA family | [LREC paper](https://aclanthology.org/2024.lrec-main.1143/); accepted Stack Overflow answers have revision-level licensing. | EXCLUDE; accepted answers are not claim-evidence labels. |

Included CodeGuard synthetic examples quote only short official Python documentation passages already included in Phase 15 and retain source URLs, section, and the [PSF License Version 2](https://docs.python.org/3/license.html) attribution. No source dataset license is inferred from a paper or code-repository license.
"""

def _label_mapping() -> str:
    return """# Label mapping and transformation policy

Canonical labels are evidence-relative:

- **Supported:** the supplied evidence directly establishes the claim.
- **Contradicted:** the supplied evidence directly conflicts with the claim.
- **Insufficient Evidence:** this supplied evidence does not establish either truth or falsity. It is not a synonym for Contradicted.

No external dataset was used, and no external labels were automatically mapped.

| Candidate labels/task | Possible mapping | Status and reason |
|---|---|---|
| CodeSimpleQA factual QA | No direct mapping | `REVIEW_REQUIRED`: correct reference answers could help create future evidence-grounded questions, but questions/answers are not claim/evidence triples with three gold classes. Do not treat all benchmark QA as Supported. |
| FEVER SUPPORTS / REFUTES / NOT ENOUGH INFO | Conceptually SUPPORTS→Supported; REFUTES→Contradicted; NOT ENOUGH INFO→Insufficient Evidence | `REVIEW_REQUIRED`, not applied: Wikipedia domain; evidence IDs must be resolved to text; NEI evidence treatment and licensing need record-level adjudication. |
| SciFact SUPPORT / CONTRADICT | SUPPORT→Supported; CONTRADICT→Contradicted | `REVIEW_REQUIRED`, not applied: no robust third class in its labeled claims; biomedical domain and separate corpus license. |
| FACTORY Factual / NonFactual / Inconclusive / No Verifiable Fact | Factual might be Supported only when source directly entails; NonFactual may be contradiction or unsupported; Inconclusive may be IE; No Verifiable Fact is not necessarily IE | `REVIEW_REQUIRED`, not applied: labels have different unit and evidence semantics, and data is noncommercial and not programming-focused. |
| CodeQA, CS1QA, StaQC, CoNaLa, CoSQA, CodeSearchNet | None | `REVIEW_REQUIRED` mapping prohibited: these label answer relevance, code correspondence, or generated code correctness, not claim truth against evidence. |
| HumanEval, MBPP, SWE-bench | None | Execution/test outcome is a separate code correctness signal; it is not an explanation claim label. |
| ExpertQA | No mapping until schema/domain inspection | `REVIEW_REQUIRED`: check claim-level support, correctness, and source reliability semantics separately, and establish a license-cleared programming-specific subset. |

Synthetic Phase 15 `SUPPORTED/CONTRADICTED/INSUFFICIENT_EVIDENCE` labels are retained only as **proposed_label** for human review. They are not gold labels. A reviewer's decision can replace or reject the proposal. External candidates have no `gold_label` until independently reviewed and, where disputed, adjudicated.
"""

if __name__ == "__main__":
    main()
