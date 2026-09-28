# Phase 16.9 — Candidate capacity test and controlled expansion

**Scope: capacity measurement and one controlled candidate batch. Phase 17: NOT READY.**

## Final report

| Measure | Result |
|---|---:|
| Starting candidates | 311 |
| Final candidates | 389 |
| New candidates | 78 |
| Starting facts | 205 |
| Final facts | 205 |
| Measured candidate capacity | 389 |
| Source URLs / source groups / topics | 45 / 45 / 97 |
| Internal | 193 |
| External | 196 |
| Proposed Supported | 188 |
| Proposed Contradicted | 109 |
| Proposed Insufficient Evidence | 92 |
| Exact duplicates rejected | 0 |
| Near-duplicates rejected | 0 |
| Quality exclusions this phase | 0 (1 prior cumulative exclusion retained) |
| Human reviewed | 0 |
| Adjudicated | 0 |
| Gold labelled | 0 |
| Phase 17 | **NOT READY** |

All class counts above are unverified proposed labels, not gold labels. The new 78 candidates are Supported proposals only: one canonical evidence-backed fact per inventory key that previously had no candidate. No contradicted or insufficient-evidence claims were generated from generic templates.

## Capacity analysis before generation

The initial inventory had 205 fact keys. The existing pool represented 127 keys; 78 had no candidate. Observed per-fact candidate counts among those 127 were:

- 12 facts with 1 candidate
- 47 facts with 2 candidates
- 67 facts with 3 candidates
- 1 fact with 4 candidates

Thus, 205 facts can support at least one candidate in the measured pool, 115 have demonstrated capacity for at least two candidates, 68 for at least three, and 1 has four. These are observed counts, not a promise that each fact can support more distinct claims.

Before persistence, each uncovered fact's canonical claim was dry-run through the existing exact/normalized/near-duplicate filter against all 311 candidates and against other dry-run additions. All 78 passed; exact matches: 0, similarity ≥0.90 matches: 0. The measured capacity was therefore **311 existing records + 78 novel supported claims = 389**. This is a conservative measured yield, not a mathematical upper bound on every possible future claim. It is far below 1,000, so reaching 1,000 from these facts would require more independently curated facts or more manual claim review; this phase did not force additional variants.

## Controlled generation and partitioning

Each accepted row contains a stable `cg169-<fact_key>-s` review ID, claim, evidence summary, proposed label, official source URL/title/section/group, topic, provenance, synthetic origin, pending status, and blank gold label. Existing source URLs inherit their existing internal/external partition. Six previously unused source URLs were assigned to the external partition; none are shared across partitions.

The 78 additions split into 14 internal and 64 external candidates. Final counts are 193 internal and 196 external. Internal/external overlap is 0 for source URLs, fact keys, and normalized claim text. The external queue remains synthetic and pending; it is not a gold benchmark.

## Duplicate and review integrity

- Final normalized exact-duplicate count: **0**.
- Final same-fact semantic-signature duplicate count: **0**.
- Final near-duplicate pairs at ≥0.90: **15**, all inherited from earlier phases; **0** new candidates participate in a near-duplicate pair.
- New quality exclusions: **0**. The cumulative prior exclusion history was not cleared.
- All 389 candidates are pending. Human review, adjudication, and gold labels remain **0**.
- Two Phase 16.9 builder runs preserved candidate IDs, states, proposed labels, label/gold fields, and database counts. The second run inserted **0** candidates. Review database: 389 records, 0 review events, 0 adjudication events.

## Tests and environment

- `python -m unittest discover -s tests -v`: **91 tests discovered; 85 passed, 5 skipped, 1 import error**. The failing import is `tests.test_ml_pipeline`, blocked by missing scikit-learn (`ModuleNotFoundError: sklearn`). The Phase 16.9, Phase 16.8, Phase 16.7, Phase 16.6B, and Phase 16.5 focused dataset tests passed.
- `python -m compileall -q app.py src tests`: passed.
- `python -m pip check`: no broken installed requirements.
- No Streamlit, Docker, or ML verification is claimed.

## Readiness decision

Phase 17 is **NOT READY**. Candidate volume remains below 1,000; all records are synthetic and pending; no independent reviews, adjudications, or gold labels exist; and the external pool is not an independent human-reviewed benchmark. Licensing and source/claim review gates remain outstanding. No training or production-inference changes occurred.

## Implementation artifacts

- Capacity analysis, controlled append, and duplicate/review statistics: `src/codeguard/ml/phase16_9.py`.
- New candidate records are stored in the existing review database and Phase 16.5 exports; machine-readable Phase 16.9 statistics and audit are under `data/ml/phase16_9/`.
- Tests: `tests/test_phase16_9.py`.
