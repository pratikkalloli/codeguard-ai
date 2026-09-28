# Phase 16.6 — Candidate dataset scaling

**Status: incomplete. Candidate minimum not met. Phase 17 readiness: FALSE.**

Phase 16.6 was intended to expand the reviewable, source-grounded candidate pool to at least 1,000 records while keeping internal and external source groups separate. The current pass did not add new facts or candidates. The existing pool remains the verified Phase 16.5 result. It would be misleading to describe the volume target as complete or relabel generated proposals as reviewed data.

## Verified current state

Counts below come from `data/ml/phase16_5/candidates.csv`, `candidate_statistics.json`, `duplicate_audit.json`, and the SQLite review database at `data/ml/phase16/review/reviews.sqlite3` after rerunning the idempotent builder.

| Measure | Verified value |
|---|---:|
| Starting candidates | 164 |
| Final candidates | 164 |
| New candidates in this pass | 0 |
| Internal / external | 143 / 21 |
| Unique source URLs / source groups | 24 / 24 |
| Unique fact keys | 72 |
| Topics | 34 |
| Exact normalized duplicates | 0 |
| Near-duplicate pairs at similarity >= 0.90 | 15 (inherited from Phase 16) |
| Quality exclusions in existing exclusion log | 1 |
| Pending / human reviewed / adjudicated / gold-labeled | 164 / 0 / 0 / 0 |
| Proposed labels (not gold) | Supported 61; Contradicted 60; Insufficient Evidence 43 |
| Gold labels | None |
| Internal/external source URL overlap | 0 |
| Internal/external fact-key overlap | 0 |

The external queue is separated by source pages and fact keys, but has 21 rather than the requested 100 candidates. It remains pending review and is not a gold benchmark. The proposed-label distribution is a property of the synthetic queue only.

## Work completed

- Added Dataset Review filters for topic, source URL, source group, proposed label, reviewer, and adjudication state. Existing status, partition, and batch filters remain.
- Removed the builder's fixed historical starting-candidate constant from the current/new candidate statistics; these values now derive from the actual queue and generated IDs.
- Reran the builder and confirmed that it retained all records and review states. No model training, production model changes, human review, or adjudication occurred.
- Read the official Python documentation inventory and checked primary reference pages while auditing possible scope expansion. A larger fact inventory was not added in this pass because each fact and its evidence/claim variants require source-section verification and the current pass did not complete that curation.

## Verification

- `python -m unittest tests.test_phase16_5 tests.test_phase16_review -v`: **16 passed**.
- `python -m compileall -q app.py src tests`: passed.
- `python -m pip check`: no broken requirements.
- Full `python -m unittest discover -s tests -v`: **77 tests discovered; 71 passed, 5 Docker integration tests skipped, 1 test module failed to import** because `sklearn` is not installed in the available Python runtime (`tests.test_ml_pipeline`). The project `.venv` interpreter could not be launched in this environment, so that dependency-specific test could not be completed here.
- Streamlit was not launched for an interactive UI check in this pass. Docker tests stayed skipped by their default guard.

## Remaining blockers for Phase 17

1. Candidate count is 164, below 1,000.
2. External subset is 21, below 100, and has not been independently reviewed.
3. All candidates remain pending; two independent human reviews and required adjudications have not been supplied.
4. There are no human-adjudicated gold labels and no human agreement statistics.
5. Source licensing review and benchmark review remain incomplete.
6. The 15 inherited near-duplicate pairs need review/disposition.
7. The full test suite needs a rerun in an environment with scikit-learn available; Docker integration remains environment-dependent.

**READINESS FOR PHASE 17: FALSE.** Do not train a final model or treat any proposed label as training truth based on this candidate pool.
