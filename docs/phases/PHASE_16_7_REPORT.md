# Phase 16.7 — Official Python source/fact inventory expansion

**Status: inventory-only expansion complete for this pass. Phase 17 remains NOT READY.**

## Verified results

| Measure | Result |
|---|---:|
| Old fact keys | 127 |
| New facts added | 19 |
| Final unique fact keys | 146 |
| Source URLs represented in the full fact inventory | 43 |
| Source groups represented in the full fact inventory | 43 |
| Topic labels represented in the full fact inventory | 66 |
| Exact duplicates rejected | 0 |
| Near duplicates rejected (normalized text similarity ≥0.90) | 0 |
| Quality exclusions in this phase | 0 |
| Candidates before / after | 311 / 311 |
| Human reviewed / adjudicated / gold-labeled | 0 / 0 / 0 |

The 19 added facts cover scope and name resolution, exception behavior, threading locks and condition variables, warning filtering, and operating-system environment mappings. The four newly represented documentation URLs are the [Execution model](https://docs.python.org/3/reference/executionmodel.html), [threading](https://docs.python.org/3/library/threading.html), [warnings](https://docs.python.org/3/library/warnings.html), and [os](https://docs.python.org/3/library/os.html) pages. Their fact rows record stable keys, canonical claims, exact section/locator text, paraphrased evidence, source group, PSF license attribution, provenance, and `pending_independent_review` status.

Every new fact was compared against the existing 127 canonical facts using normalized exact comparison and `SequenceMatcher` at the ≥0.90 threshold. Neither check found a match. The full 146-key inventory has unique keys. The candidate builder keeps these records inventory-only and merges them on later runs, without using them as candidate-generation inputs. Its repeat build retained all 311 existing candidates and their pending states; existing review event counts remained zero. No candidate sample was generated.

## Coverage gaps and scope decision

The source audit showed under-coverage in execution-model name resolution and exception semantics, synchronization and threading behavior, warning filter rules, and `os.environ` behavior. This pass added facts only where the official page established a distinct, testable rule with a locatable section. It deliberately stopped at 19 because the reviewed additions came from four page families; adding claims from further topic areas requires equivalent source-by-source locator and duplicate review. The requested 250–300 inventory target is **not met** (104–154 more facts would be needed). The result is a bounded verified increment, not a claim that 146 is the maximum possible official-doc inventory.

The 311 candidate records remain synthetic pending-review records; this phase did not increase candidate count, alter labels, fabricate review, train a model, or begin Phase 17. There remain 15 inherited candidate near-duplicate pairs from the Phase 16 baseline; this phase added none.

## Tests and environment

- `python -m unittest discover -s tests -v`: **85 tests discovered; 79 passed, 5 Docker-gated tests skipped, 1 import error**. `tests.test_ml_pipeline` cannot import because `scikit-learn` is absent from the supplied runtime.
- Focused Phase 16.7, 16.6B, and 16.5 inventory/review tests passed after updating the prior assertion that incorrectly required every fact inventory key to have a candidate.
- `python -m compileall -q app.py src tests`: passed.
- `python -m pip check`: no broken installed requirements.
- Streamlit AppTest was not run because Streamlit is unavailable. Docker integration was not run; Docker CLI is unavailable. No host execution was substituted.

## Phase 17 gate

**NOT READY.** The fact inventory remains below 250; the candidate pool remains below 1,000; all 311 candidates are pending; no independent review, adjudication, or gold labels exist; licensing review and an independent human-reviewed external benchmark remain outstanding. No model training or production model changes occurred.

## Implementation

- Inventory-only curated records: `src/codeguard/ml/phase16_7_facts.py`.
- Append-preserving inventory merge and source inventory integration: `src/codeguard/ml/phase16_5.py`.
- Tests: `tests/test_phase16_7.py`; updated Phase 16.6B inventory assertion in `tests/test_phase16_6b.py`.
- Full inventory export: `data/ml/phase16_5/fact_inventory.csv`; page-level source export: `data/ml/phase16_5/source_inventory.csv`.
