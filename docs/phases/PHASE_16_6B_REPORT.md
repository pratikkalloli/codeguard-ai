# Phase 16.6B — Source-fact inventory expansion and candidate scaling

**Status: source inventory expanded; candidate target not met. Phase 17 readiness: FALSE.**

## Verified counts

All candidate and review values below were derived from the persisted CSV exports and SQLite review database after the build and its idempotency rerun.

| Measure | Starting state | Final state | Change in this phase |
|---|---:|---:|---:|
| Candidates | 164 | 311 | +147 |
| Internal candidates | 143 | 179 | +36 |
| External candidates | 21 | 132 | +111 |
| Fact keys | 72 | 127 | +55 |
| Unique source URLs | 24 | 39 | +15 net (16 URLs used by new facts; one URL already existed) |
| Recorded source groups | — | 32 | — |
| Topic labels | 34 | 58 | +24 |
| Pending | 164 | 311 | +147 |
| Human reviewed | 0 | 0 | 0 |
| Adjudicated | 0 | 0 | 0 |
| Gold-labeled | 0 | 0 | 0 |

Final proposed-label counts across all records are Supported 110, Contradicted 109, and Insufficient Evidence 92. These are unverified proposal counts, not a gold-label distribution.

The 55 new fact keys are on 16 official Python documentation pages and span 25 topics (24 are new to the existing candidate pool). Each inventory row has a stable fact key, canonical claim, topic, source URL/title, source group, section/evidence locator, evidence summary, Python Software Foundation license attribution, and provenance status. New candidate claims are synthetic proposed examples. Internal facts generate two selected claim forms each; external facts generate three. The candidates have pending review status and blank gold/final labels.

New source pages:

- [argparse](https://docs.python.org/3/library/argparse.html), [concurrent.futures](https://docs.python.org/3/library/concurrent.futures.html), [csv](https://docs.python.org/3/library/csv.html), [dataclasses](https://docs.python.org/3/library/dataclasses.html)
- [datetime](https://docs.python.org/3/library/datetime.html), [decimal](https://docs.python.org/3/library/decimal.html), [enum](https://docs.python.org/3/library/enum.html), [io](https://docs.python.org/3/library/io.html)
- [logging](https://docs.python.org/3/library/logging.html), [math](https://docs.python.org/3/library/math.html), [multiprocessing](https://docs.python.org/3/library/multiprocessing.html), [pickle](https://docs.python.org/3/library/pickle.html)
- [sqlite3](https://docs.python.org/3/library/sqlite3.html), [statistics](https://docs.python.org/3/library/statistics.html), [built-in types](https://docs.python.org/3/library/stdtypes.html), [string](https://docs.python.org/3/library/string.html)

## Candidate and quality checks

- 147 new candidates were accepted: 36 internal and 111 external. The external subset now has 132 candidates, exceeding its 100-record preparation target. It remains a pending review queue, not a gold benchmark.
- Exact normalized duplicate count: 0. Same-fact semantic-signature duplicates: 0. Near-duplicate pairs at similarity >=0.90: 15, all inherited Phase 16 pairs; no new near-duplicate candidates were accepted. The cumulative exclusion CSV has one prior Phase 16.5 exclusion; this phase added zero exclusions. The quality filter retains negation in its same-fact signature so valid contradicted claims are not collapsed into supported claims.
- Internal/external source URL overlap: 0. Internal/external fact-key overlap: 0.
- The SQLite database has 311 candidate records, all pending. Reviewer-event and adjudication-event counts remain zero. No reviewer identity, decision, timestamp, agreement, adjudication, or gold label was created.
- An idempotency rerun inserted zero candidates and retained the same 311 record identities, review states, label fields, and event counts.
- Production model changed: **No**. Training performed: **No**.

## Implementation and artifacts

- New curated source facts: src/codeguard/ml/phase16_6b_facts.py.
- Repeatable persistence/export and stable candidate ID handling: src/codeguard/ml/phase16_5.py (continues the existing Phase 16.5 builder and review database).
- Inventory and candidate integrity checks: tests/test_phase16_6b.py.
- Machine-readable inventories and exact counts: data/ml/phase16_5/fact_inventory.csv, source_inventory.csv, candidate_statistics.json, duplicate_audit.json, candidates.csv, and external_review_queue.csv.
- Dataset Review retains the Phase 16.6 filters: status, partition, batch, topic, source URL, source group, proposed label, reviewer, and adjudication state.

## Tests and environment

- Full unittest discovery: **83 discovered; 77 passed, 5 skipped, 1 import error**. The error is tests.test_ml_pipeline failing to import sklearn.
- Phase 16.6B inventory/dedup/separation tests: **6 passed**. The full suite also passed the existing Phase 16/16.5 review workflow tests.
- compileall: passed. pip check: no broken installed requirements.
- Scikit-learn: **unavailable** in the supplied runtime, although requirements.txt declares scikit-learn>=1.6. The project .venv interpreter could not be launched in this environment.
- Docker: **unavailable**; the Docker command is not installed/available. Docker integration tests were skipped by their opt-in guard.
- Streamlit: **not verified**; it is unavailable in the supplied runtime, so AppTest was not run.

## Remaining gates

Phase 17 is **NOT READY**. The current pool is 311, below the minimum 1,000. The source inventory has 127 fact keys, below the requested 200–300 target. All candidates need two independent human reviews; any required disagreements need adjudication. There are no human-adjudicated gold labels or human agreement statistics. Licensing review and independent external benchmark review remain incomplete. The 15 inherited near-duplicate pairs still need disposition. Restore a suitable project environment to rerun the ML test module, Streamlit AppTest, and Docker integration tests where Docker is available.
