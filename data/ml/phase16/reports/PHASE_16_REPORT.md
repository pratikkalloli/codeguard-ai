# CodeGuard AI — Phase 16 dataset and review preparation

**Phase status: review infrastructure prepared. Dataset status: NOT READY for Phase 17.**

## 1. Research and candidate assessment

Investigated 19 candidate resources spanning programming QA/code benchmarks, human-annotated factuality/claim benchmarks, and evidence-verification datasets. Candidate-level fields, source and paper links, licensing, annotation properties, decisions, and exclusion reasons are in `../candidates/dataset_candidates.csv`.

CodeSimpleQA is the strongest programming factual-QA lead: the paper describes 8 annotators and 3 senior engineers and programming-document grounded QA. It is not imported: the paper reports inconsistent sizes (1,498, 1,478, and 312 in different passages), does not provide an inspected record-level evidence release/link or a dataset license in the paper. It remains REVIEW. The detailed research used primary paper/site/repository pages; see `DATASET_CANDIDATES.md`.

## 2. Accepted and excluded sources

Accepted public datasets: **0**. No external raw data was acquired. The Phase 15 CodeGuard synthetic candidates were copied into an isolated review workspace only. FEVER, SciFact, SciClaimEval, FACTORY, ExpertQA, CodeQA, CS1QA, CoSQA, StaQC, CoNaLa, CodeSearchNet, HumanEval, MBPP, SWE-bench Verified, SimpleQA, SimpleQA Verified, SciFact-Open, and ProCQA/programming-QA candidates were explicitly assessed in `dataset_candidates.csv`.

## 3. Licensing and provenance

No public dataset is cleared for reuse in this phase. Candidate license status and exact URLs are detailed in `LICENSE_AUDIT.md`. Phase 15 Python documentation excerpts retain source URL, source section, and PSF License Version 2 attribution. Existing synthetic candidates retain their provenance; one source-less legacy record remains excluded.

## 4. Label mapping

No external labels were automatically mapped. Candidate conversions and reasons for REVIEW_REQUIRED are in `LABEL_MAPPING.md`. Canonical labels remain Supported, Contradicted, and Insufficient Evidence, with IE explicitly not equivalent to Contradicted. Synthetic labels are shown only as `proposed_label`.

## 5. Human review and adjudication

Review queue size: **72** (66 internal plus 6 external). Real reviews: **0**; pending: **72**; rejected: **0**; adjudicated: **0**. No reviewer identities or agreement metrics were fabricated. The local Dataset Review page stores decisions in a separate, Git-ignored SQLite file and requires distinct reviewer identifiers for A/B.

The interface is ready for a real reviewer: candidate shown one at a time with evidence/source/proposed label; decision, confidence, notes; two independent slots; disputed state and independent adjudication. See reviewer, adjudication, and schema docs in `review/`.

## 6. Counts and composition

Internal candidates: **66**, all `synthetic_pending_review`; external candidates: **6**, all synthetic pending review. Public verified: 0; manually verified: 0; synthetic reviewed: 0. Proposed internal class distribution (not gold labels): `{"Contradicted": 28, "Insufficient Evidence": 10, "Supported": 28}`. External proposal distribution (not gold labels): `{"Contradicted": 2, "Insufficient Evidence": 2, "Supported": 2}`. Full topic and source distribution and percentages appear in `QUALITY_REPORT.md` and `dataset_statistics.json`.

## 7. Duplicate, leakage, and external set

Exact duplicates: 0; normalized-claim label conflicts: 0; near-duplicate pairs at >=0.90 similarity: 15; near-duplicate split/external violations: 0; source-group split violations: 0. Existing Phase 15 group assignments are preserved and checked. The six-row external candidate uses a source page/fact keys absent from internal data, but remains entirely synthetic and unreviewed; `gold_label` is blank and must remain unused for tuning until independently reviewed/adjudicated.

## 8. Separate quality indicators

Provenance field completeness at generation: 72/72; review completion: 0/72; label agreement: unavailable; duplicate/conflict counts and concentration: see `QUALITY_REPORT.md`; external isolation: checked; human-verified external benchmark: 0. No aggregate dataset-quality score was created.

## 9. Limitations and readiness gate

Dataset is mostly and entirely synthetic, based on few official documentation pages and polarity templates. The external set is not human validated. No public candidate met the complete task/domain/license bar. Critical readiness items therefore fail: at least 1,000 reviewed items, human-adjudicated labels, resolved licensing, representative source/topic breadth, and an independently reviewed external benchmark.

### READY_FOR_PHASE_17: FALSE

Do not train, tune, select, or report final model performance until the review queue is genuinely reviewed and the independent external benchmark is human-adjudicated.

## 10. Files created/modified

Phase 16 implementation and tests: `src/codeguard/ml/phase16.py`, `src/codeguard/ml/review.py`, `tests/test_phase16_review.py`, `app.py`, and `.gitignore`.

Generated workspace: `data/ml/phase16/candidates/dataset_candidates.csv`; `raw/README.md`; `processed/canonical.csv`, `verified.csv`, `pending_review.csv`, `rejected.csv`; `review/review_queue.csv`, `review_summary.json`, `reviewer_guidelines.md`, `adjudication_guidelines.md`, `review_schema.md`, and the local `reviews.sqlite3`; `external/external_test.csv`; `dataset_manifest.json`; `dataset_statistics.json`; and reports `DATASET_CANDIDATES.md`, `DATASET_CARD.md`, `LABEL_MAPPING.md`, `LICENSE_AUDIT.md`, `QUALITY_REPORT.md`, and `PHASE_16_REPORT.md`. The database is Git-ignored and stores actual user reviews.

Documentation updated: `PROJECT_PROGRESS.md`, `README.md`, and `docs/phases/PHASE_16_DATASET_REPORT.md`. The documentation report mirrors this report.

## 11. Verification performed

- `python -m unittest discover -s tests -v`: 81 tests completed successfully; 5 Docker integration tests skipped by their default opt-in safety guard.
- `python -m compileall -q app.py src tests`: passed.
- `python -m pip check`: no broken requirements.
- Streamlit `AppTest` of `app.py`: zero app exceptions.
- No Docker integration run, live provider API call, submitted-code execution, or production model training was performed. Existing model artifacts and Phase 15 source datasets were not modified.

## 12. Next incomplete phase

Phase 17 model training is NOT READY. Readiness is `FALSE`: 72 synthetic candidates await real independent review, zero public datasets were accepted, and zero human-verified records or independent external benchmark labels exist. Continue only after human review/adjudication and licensing/source diversity gates are satisfied.
