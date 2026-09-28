# Phase 16.5 — Source-backed candidate expansion and review workflow

**Build status: implemented and verified. Candidate target status: NOT MET. Phase 17 readiness: FALSE.**

## Purpose and boundaries

This phase expands the existing human-review queue and makes the review workflow safer and easier to audit. It is data preparation only. The 92 added records are synthetic candidate claims with *proposed* labels; those proposals have not been verified by a human. No model was trained, evaluated, or changed. The minimum requested pool size was 1,000; the delivered total is 164, so the target remains unmet. The pool was not padded with paraphrases merely to approach a numeric target.

## Candidate and source inventory

The build retains the existing 72 Phase 16 candidates and adds 92 candidates from 31 manually curated facts in 17 canonical Python documentation pages. Together the inventory covers 72 fact keys / claim families, 24 documentation page URLs, and 34 topic labels. Twenty-one candidates (7 per proposed class) are held in a distinct external review queue. New candidates have the `synthetic` origin, pending status, blank `label` and `gold_label`, and a separate `proposed_label` field. Source URL, page title, section, evidence excerpt, source group, claim family, provenance statement, retrieval date, and PSF license attribution are recorded. Evidence excerpts and claim formulations were curated from the official Python documentation; they have not yet received independent human review.

The source set is concentrated: the three most represented pages contribute 66 candidates in total. The 15 >=0.90-similarity pairs in the expanded queue were inherited from the Phase 16 baseline; they are visible in the audit rather than silently dropped. One newly generated candidate was filtered because it was a near duplicate. Exact duplicate count in the expanded queue is zero. These quality measures are lexical screening signals, not a human quality judgment.

## Review workflow and label policy

- Internal batches are mixed across the three *proposed* label classes and programming topics; the first batch is introductory. The external queue is separate and must not be used to tune or train on internal examples.
- Reviewers work independently, use distinct reviewer IDs, and should not see the proposal while making their first evidence-only decision. The UI hides the proposed label by default. Review mode distinguishes evidence-only from optional source-verified review; opening or checking a source is recorded when the reviewer selects source verification.
- After two independent reviews, agreement is a review outcome only; it does **not** make a gold label. Disagreement is escalated to a distinct third adjudicator. Only the adjudication event can populate the final label in `adjudicated.csv`.
- `candidates.csv`, `pending_review.csv`, `reviewed.csv`, `rejected.csv`, and the external queue do not carry adjudicated labels as gold. `adjudicated.csv` is the only Phase 16.5 export intended to carry gold labels. The SQLite event log is the review audit trail, not a training-ready gold dataset.
- Review decisions and timestamps are human activity. No human review was performed as part of this automated build.

## Current results

The reproducible machine-readable counts are in `../data/ml/phase16_5/candidate_statistics.json`; batch composition is in `../data/ml/phase16_5/review_batches.csv`.

| Measure | Observed result |
|---|---:|
| Existing Phase 16 candidates retained | 72 |
| New Phase 16.5 candidates | 92 |
| Total candidates | 164 |
| Internal / external held-out candidates | 143 / 21 |
| New curated facts / new source pages | 31 / 17 |
| Total fact keys / source URLs / topic labels | 72 / 24 / 34 |
| Proposed-label distribution, all candidates (not gold) | 61 Supported / 60 Contradicted / 43 Insufficient Evidence |
| Pending / reviewed / adjudicated / rejected | 164 / 0 / 0 / 0 |
| Gold-labeled records | 0 |
| New candidates withheld by near-duplicate filter | 1 |
| Exact duplicates / >=0.90 near-duplicate pairs | 0 / 15 (the latter inherited from Phase 16) |
| Candidate target | 1,000 minimum; **not met** |
| Phase 17 ready | **No** |

Proposed-label balance is only a queue-design property. It must not be presented as verified class balance or model quality.

## Files and use

The generator is `../src/codeguard/ml/phase16_5.py`; focused tests are in `../tests/test_phase16_5.py`. Generated artifacts live in `../data/ml/phase16_5/`: `README.md`, `candidate_statistics.json`, `duplicate_audit.json`, `quality_exclusions.csv`, `fact_inventory.csv`, `source_inventory.csv`, `candidates.csv`, `pending_review.csv`, `review_batches.csv`, `external_review_queue.csv`, `reviewed.csv`, `adjudicated.csv`, and `rejected.csv`. The review database and append-only review records stay under `../data/ml/phase16/review/`.

Run the builder from the repository root with:

```powershell
.venv\Scripts\python.exe -m codeguard.ml.phase16_5
```

The build is idempotent: it adds records only when their IDs are absent, retains the review database, and refreshes exports. It does not start code execution, make API calls, or train a model.

## Limitations and next gate

1. The pool is far below the 1,000-candidate minimum and all 164 candidates need two independent human reviews; disagreements need independent adjudication.
2. The new facts and claims are synthetic, selected from a small Python-only source set, and share manual curation. There is no independent human-labeled external benchmark.
3. The external queue has source-page separation from internal candidates, but this alone does not establish broad external validity.
4. Source excerpts were manually transcribed from current official documentation pages; a reviewer should verify each claim and the relevant page section. Retrieval dates identify when pages were checked, not immutable documentation versions.
5. Lexical duplicate checks can miss semantic duplicates and can flag distinct claims. The inherited near-duplicate pairs need human disposition before dataset use.
6. Proposed labels do not establish that evidence fully entails a claim, and an insufficient-evidence proposal is relative to the quoted excerpt rather than to all Python documentation.

**Phase 17 gate:** keep `READY_FOR_PHASE_17: FALSE`. Do not train or claim model quality until the candidate-size criteria are met with quality-controlled examples, independent reviewers and adjudication are complete, source/license checks are signed off, and a genuinely independent human-reviewed external benchmark exists.

## Primary sources

The new evidence snippets cite the official Python documentation: [Built-in Types](https://docs.python.org/3/library/stdtypes.html), [Built-in Functions](https://docs.python.org/3/library/functions.html), [The Python Tutorial](https://docs.python.org/3/tutorial/controlflow.html), and official standard-library pages including [collections](https://docs.python.org/3/library/collections.html), [itertools](https://docs.python.org/3/library/itertools.html), [typing](https://docs.python.org/3/library/typing.html), [asyncio tasks](https://docs.python.org/3/library/asyncio-task.html), [subprocess](https://docs.python.org/3/library/subprocess.html), [pathlib](https://docs.python.org/3/library/pathlib.html), [contextlib](https://docs.python.org/3/library/contextlib.html), and [tempfile](https://docs.python.org/3/library/tempfile.html). License attribution is recorded per row and links to the [Python license page](https://docs.python.org/3/license.html).
