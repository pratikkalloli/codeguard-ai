# Phase 16.8 — Bounded official Python fact expansion

**Scope: inventory-only. Phase 17: NOT READY.**

## Final report

| Measure | Verified result |
|---|---:|
| Starting facts | 146 |
| New facts | 59 |
| Final unique fact keys | 205 |
| Starting candidates | 311 |
| Final candidates | 311 |
| New candidates | 0 |
| Source URLs in final fact inventory | 45 |
| Source groups in final fact inventory | 45 |
| Topics in final fact inventory | 97 |
| Duplicates rejected (exact) | 0 |
| Near-duplicates rejected (normalized similarity ≥0.90) | 0 |
| Quality exclusions | 0 |
| Human reviewed | 0 |
| Adjudicated | 0 |
| Gold labelled | 0 |
| Phase 17 | **NOT READY** |

## Coverage and sources

The inventory-only batch adds claims about import search/cache behavior; descriptors and attribute access; comparisons and hashing; synchronous and asynchronous iterator/generator protocols; context-manager exception behavior; subprocess return, timeout, and pipe semantics; pathlib file and path operations; itertools; dataclasses; enum; typing; logging; and functools. Source evidence was checked against the official [import system](https://docs.python.org/3/reference/import.html), [data model](https://docs.python.org/3/reference/datamodel.html), [expressions](https://docs.python.org/3/reference/expressions.html), [contextlib](https://docs.python.org/3/library/contextlib.html), [subprocess](https://docs.python.org/3/library/subprocess.html), [pathlib](https://docs.python.org/3/library/pathlib.html), [itertools](https://docs.python.org/3/library/itertools.html), [dataclasses](https://docs.python.org/3/library/dataclasses.html), [enum](https://docs.python.org/3/library/enum.html), [typing](https://docs.python.org/3/library/typing.html), [logging](https://docs.python.org/3/library/logging.html), and [functools](https://docs.python.org/3/library/functools.html) documentation.

All new rows have stable fact keys, canonical facts, topics, official source URLs and titles, source groups, section and locator fields, paraphrased evidence, PSF license attribution, provenance status, retrieval date, and pending independent-review status. The additions share some existing source pages; the final URL/group count grew from 43 to 45.

## Duplicate and idempotency checks

- Compared normalized canonical facts using exact equality and `SequenceMatcher` with a 0.90 threshold, across all 59 new facts against the original 146 and within the new batch. Exact duplicate pairs: **0**; near-duplicate pairs: **0**.
- Final inventory contains **205 unique fact keys**; reruns do not append duplicate keys.
- Ran the existing Phase 16.5 inventory builder twice. Both runs retained the same **311** candidate IDs, review statuses, label fields, and `gold_label` fields. The database remained at 311 review records, 0 review events, and 0 adjudication events.
- The builder merges Phase 16.8 records into the fact/source inventory only. The new module contains no generated candidate variants and adds no rows to the candidate dataset.

## Tests and environment

- `python -m unittest discover -s tests -v`: **88 tests discovered; 82 passed, 5 Docker-gated tests skipped, 1 import error**. The import error is `tests.test_ml_pipeline`: scikit-learn is unavailable (`ModuleNotFoundError: sklearn`). The 3 Phase 16.8 checks and focused Phase 16.7/16.6B/16.5 inventory checks passed.
- `python -m compileall -q app.py src tests`: passed.
- `python -m pip check`: no broken installed requirements.
- No ML verification is claimed. Streamlit AppTest and Docker integration verification are not claimed for this run.

## Readiness

The inventory has 205 facts, still below the earlier 250–300 research target. The candidate pool remains 311 (below 1,000), and all records remain pending with no human review, adjudication, or gold labels. Independent external benchmark review and licensing sign-off are also outstanding. **Do not start Phase 17 or train a model.**

## Implementation files

- Curated inventory-only facts: `src/codeguard/ml/phase16_8_facts.py`.
- Inventory merge and source export: `src/codeguard/ml/phase16_5.py`.
- Integrity tests: `tests/test_phase16_8.py`.
- Persisted inventory/source exports: `data/ml/phase16_5/fact_inventory.csv` and `data/ml/phase16_5/source_inventory.csv`.
