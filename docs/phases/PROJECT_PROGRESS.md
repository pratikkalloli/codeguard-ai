# CodeGuard AI Project Progress

## Completed phases

### Part 1 — Planning and environment setup

- Defined the project goal, problem, objectives, staged roadmap, and recommended architecture and technologies.
- Created the initial Streamlit application and requirements file in `C:\codex`.
- The user opened the Streamlit app successfully in a browser.

### Part 2 — Manual input and response extraction

- Added a coding-question field and an AI-response field.
- Added extraction of Markdown fenced code blocks labeled `python` or `py`.
- Kept remaining prose (and non-Python fences) as explanation text.
- The app displays extracted code without executing it.

### Phase 3 — Project structure and SQLite storage

- Added `src/codeguard/storage.py` with SQLite schema creation for evaluation sessions, questions, AI responses, extracted code, test results, and evaluation metrics.
- Added functions to save an evaluation, list recent history, and retrieve one evaluation with its extracted code.
- Updated the Streamlit app to save successful manual extractions and provide an Evaluation history tab.
- Added database files to `.gitignore`; the local database is created at `data/codeguard.db` when the app runs.
- Added `tests/test_storage.py` with tests for insertion/retrieval, missing IDs, and invalid empty questions.
- Verification: `python -m unittest tests.test_storage` passed (3 tests). Python compilation completed, and a Streamlit `AppTest` render showed both tabs with no app exceptions.

### Phase 4 — Static Python validation

- Added `src/codeguard/validation.py` to report missing code, syntax errors, and a limited set of potentially risky imports/calls using Python's AST parser.
- Added validation summaries and line-specific risk findings to new evaluations and history details.
- Static findings are warnings for review; validation does not execute code and does not guarantee safety or correctness.
- Added tests for missing code, benign valid syntax, syntax errors, and risky calls.
- Verification: `python -m unittest tests.test_storage tests.test_validation` passed (8 tests); compilation succeeded; Streamlit render showed both tabs with no app exceptions.

### Phase 5 — Restricted Docker execution

- Confirmed Docker Desktop's Linux engine is running (`OSType=linux`, server 29.8.0) and downloaded the official `python:3.12-slim` image.
- Added `src/codeguard/execution.py`. It sends source over stdin and mounts no host folders. Containers run with no network, a read-only root filesystem, non-root UID, dropped capabilities, no-new-privileges, 128 MiB memory, 0.5 CPU, 32 processes, CPU/file/descriptor limits, a 16 MiB no-exec temporary filesystem, 64 KiB combined captured output, and an enforced wall timeout. Containers are removed after each run.
- Docker execution is opt-in from the “Isolated run” tab. The app does not auto-download missing images; it explains the PowerShell `docker pull python:3.12-slim` command.
- Exposed statuses: Passed, Failed, Timeout, Security blocked, and Execution error.
- Security limit: Docker is a useful local development boundary, not a production-grade guarantee against Docker runtime, kernel, or host vulnerabilities. Do not use this as a public multi-user service sandbox.
- Verification: a harmless print program passed in the container; a harmless bounded infinite loop returned Timeout after the one-second test limit. Two fresh integer-addition cases passed after the final changes. `docker ps` showed no leftover running containers. No host folders were mounted and container network was disabled.

### Phase 6 — Manual function test cases

- Added a Test cases tab. It accepts one JSON array of positional arguments and one expected JSON return value per line, with up to 10 cases.
- Each case runs in a fresh restricted container. The current MVP checks a named function's JSON-serializable return value; it does not currently support class methods, stdout-only solutions, or arbitrary test harness formats.
- Test results are saved to SQLite with inputs, expected/actual outputs, status, and error details. Evaluation history displays the saved results.
- Verification: two harmless integer-addition cases passed in separate containers. Storage and function-result unit tests passed as part of the 14-test suite. Compilation succeeded and Streamlit rendered all four tabs without app exceptions.

### Phase 7 — Performance measurement

- The Docker-only supervisor measures submitted Python child-process wall time separately from Docker image readiness checks, container startup (when the Docker engine timestamp can be compared reliably), Docker run wall time, an explicitly labeled residual Docker overhead estimate, and overall end-to-end wall time.
- Image download/preparation is not included in an evaluation: the image is expected to be prepared before running. The image readiness/inspect check is separately timed. Startup timing is marked unavailable if engine timestamp data is missing or appears inconsistent; it is not replaced with a fabricated zero.
- The isolated supervisor reads cgroup v2 `memory.peak` when available. The UI and database label this as peak whole-container memory, including Python runtime and sandbox overhead; it is not code-only memory. Memory is reported unavailable when the container does not expose a reliable reading.
- Performance metrics and measurement descriptions are saved in SQLite and shown in the Isolated run and Evaluation history views. Test-case output includes process wall time and whole-container peak memory where available.
- These timings include creation and exit of a separate Python process and are not pure algorithm benchmarks. Docker overhead is a residual estimate that can include container startup and teardown; it is not a directly measured Docker-only component.
- Verification: 5 Docker integration tests passed using harmless print, addition, sleep, bounded-memory, and timeout samples. The standard test suite passed 27 tests with 5 Docker-only tests skipped when integration mode was off. Python compilation succeeded; Streamlit `AppTest` rendered all five tabs without exceptions.

### Phase 8 — Initial explanation claim analysis

- Added sentence-level heuristic claim extraction and a Streamlit Explanation analysis tab. Results are stored in SQLite and show claim text, status, reason, and evidence field.
- The initial analyzer labels likely factual assertions “Insufficient evidence,” labels unrecognized or instruction-like sentences “Not evaluated,” and can flag a narrow, direct mutable/immutable disagreement as an internal contradiction.
- The analyzer has no documentation corpus or retrieval system yet. It never marks a claim “Supported”; its “Contradicted” result only detects the defined internal wording conflict and does not establish external truth. Sentence splitting and claim recognition are heuristic and can miss or misclassify claims.
- Verification: claim analysis and persistence tests pass as part of the 27-test suite. Streamlit render shows the new tab without exceptions.

### Phase 9 — Documentation corpus and evidence retrieval

- Added a curated corpus of 12 short chunks paraphrasing official Python documentation on lists, tuples, dictionaries, sets, comprehensions, built-ins, function definitions, loops, exceptions, and file handling. Every record preserves the Python Software Foundation source label, page title, official URL, section, and stable chunk ID.
- Added a modular ingestion path that validates `docs.python.org` provenance, cleans whitespace, splits on sentence boundaries, caps chunk sizes, and carries evidence metadata forward.
- Added local normalized TF-IDF vector representations and cosine retrieval using only Python's standard library. The JSON vector index is generated in `data/python_docs_tfidf.json`; a corpus SHA-256 check rebuilds it when its source changes. Retrieval is offline and deterministic; it does not use Sentence Transformers, FAISS, Chroma, or a cloud service.
- Added conservative, explicit proposition rules for a narrow set of claims. Similarity alone never changes a status. A rule must recognize the claim and retrieve a chunk with the matching fact key before returning Supported or Contradicted. Other claims remain Insufficient evidence; non-claims remain Not evaluated.
- The Explanation analysis UI displays status, reason, evidence or candidate passage, official source link, TF-IDF cosine similarity, retrieval duration, and chunk ID. Database migrations add source, title, URL, retrieval score, chunk ID, and retrieval time without deleting Phase 8 claim records.
- Verification: tests cover corpus validation, splitting, provenance, local index persistence, retrieval, supported/contradicted/insufficient/not-evaluated outcomes, empty claim, retrieval failure, and database migration/persistence. Sample checks returned Supported for “Python lists are mutable,” Contradicted for “Python tuples are mutable,” and Insufficient evidence for an out-of-scope claim.
- Limitations: TF-IDF is lexical and not a semantic neural embedding. The corpus and comparison rules are deliberately small; similarity is a ranking aid, not truth evidence by itself. No general fact checker is claimed.

### Phase 10 — Optional AI API integration

- Added a provider-neutral response protocol and an OpenAI Responses API adapter. Manual paste remains the default path and requires no key.
- The API key is read only from `OPENAI_API_KEY` in the app process environment and is not stored in source code, session history, or SQLite. Model can be selected per request or configured with `CODEGUARD_OPENAI_MODEL`; the current default follows the official API quickstart. API requests set `store=false`, cap output at 1,200 tokens, and record host-observed API wall time plus provider-reported token counts when returned.
- Added handling for missing keys, network failures, HTTP rate/usage limits, authentication, bad requests/input limits, service errors, incomplete output, and invalid/empty response structures.
- Verification uses mocked HTTP responses and covers key absence, secret non-disclosure, response parsing, token usage, rate limits, network errors, and output-token truncation. No live request was made: `OPENAI_API_KEY` is not configured in this environment. Live provider/account/model/billing behavior remains unverified until a key is configured.

### Phase 11 — Multi-model comparison

- Manual responses can be labeled with a model/source name. The same prompt can be submitted through the optional OpenAI provider for another model. Each answer is stored as a separate evaluation and follows the same extraction, static checks, and explanation evidence pipeline.
- Added comparison grouping for exact prompts after case-folding and whitespace normalization. The comparison view displays syntax findings, saved test pass counts, Python process time, API latency, and evidence status counts. Missing measurements remain “Not run” or “Unavailable”; no aggregate score is invented.
- Offline tests cover comparison grouping. Live multi-model comparison requires a configured API key and account access.

### Phase 12 — Reliability report

- Added a report builder containing question, model/source, generated code and static findings, saved test results/errors, performance metrics, explanation claims/evidence, and limitations.
- Added a Streamlit report view and JSON download. The report describes separate observations and has no undocumented overall reliability score.
- Offline tests verify report contents, pass counts, claim counts, and absence of a synthetic aggregate score.

### Phase 13 — Final dashboard

- Added a dashboard overview with saved evaluation, extracted code, saved test, and analyzed-claim counts.
- The Streamlit interface now has Dashboard, New evaluation, Isolated run, Test cases, Explanation analysis, Model comparison, Reliability report, and Evaluation history views.
- App render verification showed all eight tabs without exceptions.

### Phase 14 — Testing and project documentation

- Added or expanded unit tests for retrieval, evidence verification, provider failures, reports/comparison, schema migration, and previous core behavior.
- Created `README.md`, `docs/architecture/ARCHITECTURE.md`, and `docs/demo/DEMO_GUIDE.md` with Windows commands, architecture, API-key safety, Docker caveats, test instructions, demo flow, and limitations.
- Verification on 2026-09-26: the offline suite ran 50 tests, with 45 passing and 5 Docker-gated integration tests skipped by default; Python compilation succeeded; Streamlit rendered all eight tabs in both Manual paste and OpenAI API selection modes without exceptions. Representative list, tuple, dictionary, and insufficient-evidence outcomes were checked.
- The Docker integration tests had passed when Docker was available during Phase 7. A fresh integration-enabled run on 2026-09-26 could not reach the Docker Desktop Linux daemon (`dockerDesktopLinuxEngine` named pipe missing), so those five checks failed with infrastructure errors in that run. No host-execution fallback was used.

## Current safety and scope notes

- The app executes submitted code only inside the configured Docker container; no host-based execution fallback exists.
- Runtime measurements distinguish child-process wall time from Docker-related timings, but the child-process value is not a pure algorithm benchmark. Whole-container peak memory is available only when cgroup v2 exposes it; it includes runtime and sandbox memory.
- Explanation verification uses a tiny official Python documentation corpus and narrow explicit rules; it is not a general fact checker and does not guarantee factual correctness. TF-IDF is lexical, not a semantic transformer embedding.
- The OpenAI adapter is implemented but a live provider request is not verified because this environment has no API key. API use may incur charges.
- Docker execution still has no host fallback. The Docker engine was unavailable in the most recent integration test attempt; restart Docker Desktop before relying on execution/test-case integration checks.
- History stores full user questions, raw AI responses, explanations, and extracted code in a local SQLite file. Treat that file as potentially sensitive and do not commit it.

## Remaining external verification

The 14-phase implementation roadmap is complete. To verify external integrations, configure an OpenAI API key in the app process environment (optional and potentially billable) and restart Docker Desktop's Linux engine before running the API and Docker integration checks. Until then, manual response entry and the offline tests remain available.

## Final project audit — 2026-09-26

This audit reviewed the project structure, Streamlit application, SQLite schema and migrations, static validation, Docker runner, function tests, performance measurements, explanation analysis, local documentation retrieval, evidence verification, OpenAI adapter, comparison, reports, dashboard, tests, and documentation. No feature work or security relaxation was performed.

### Verification results

- **Offline tests — Verified:** `python -m unittest discover -s tests -v` ran 50 tests: 45 passed, 5 Docker integration tests were skipped by their default opt-in guard. The tests exercise storage and migrations, static validation, claim analysis/evidence outcomes, retrieval, provider responses using mocks, comparisons/reports, and Docker runner input handling/function-test behavior without invoking Docker.
- **Imports and syntax — Verified:** `python -m compileall -q app.py src tests` completed successfully. The offline suite imported and exercised project modules.
- **Streamlit UI — Verified:** Streamlit `AppTest` rendered both Manual paste and OpenAI API selection modes with no app exceptions. The eight views are Dashboard, New evaluation, Isolated run, Test cases, Explanation analysis, Model comparison, Reliability report, and Evaluation history.
- **Dependencies — Verified:** `pip check` reported no broken requirements.
- **SQLite — Verified offline:** schema initialization, saves/loads, separate measurement categories, claim persistence, and additive migrations are covered by passing tests.
- **Docker — Blocked by environment:** the Docker CLI is present, but read-only `docker info` could not connect to Docker Desktop's `dockerDesktopLinuxEngine` named pipe. Therefore actual isolated execution, resource limits, cleanup, cgroup memory readings, function cases in containers, and live Docker performance measurements were not re-verified in this audit. The five integration tests were correctly skipped in the default offline suite. No host-execution fallback was added or used.
- **OpenAI — Implemented; live behavior not verified:** provider behavior is covered with mocked responses. `OPENAI_API_KEY` was absent (checked as a boolean only), so no live API request was made. Account, model availability, network behavior, and billing remain unverified.
- **Secrets scan — Verified:** repository scan found environment-variable references and the test-only string `test-secret`; it found no hard-coded API key pattern. The actual environment key value was never displayed.
- **Reliability claims — Verified for transparency:** reports do not calculate an overall reliability score. Retrieval is lexical TF-IDF over a small curated corpus with narrow proposition rules; it is not a general fact checker. Runtime timings are labeled with their measurement scope, and container memory includes sandbox/runtime overhead when available.
- **Documentation — Reviewed:** README, architecture, demo guide, and this progress record were checked against the inspected implementation. The demo guide requires Docker for sandbox demonstrations; use manual, offline views if the engine is unavailable.
- **Dead code and regressions — Reviewed, not exhaustively proven:** module responsibilities and imports were inspected and all automated checks above passed. Static inspection cannot prove the absence of every unreachable branch or latent defect.

### Audit status

The 14 planned phases are implemented and the offline checks pass. The project is **offline verified with external integration limits**: Docker-backed behavior is currently blocked by the unavailable Docker daemon, and live OpenAI behavior is unverified because no API key is configured. These are environment limitations, not successful live integration tests. No application code was changed during the final audit; this section is the only audit update.

### External checks still required

When Docker Desktop's Linux engine is running, use the README's opt-in command to run `tests.test_execution_integration`; do not substitute host execution. A live OpenAI check is optional and requires the user to configure a key privately; mocked provider tests remain the offline verification path.

## UI redesign — 2026-09-26

- Replaced the default Streamlit presentation with a dark-first developer-tool shell, custom responsive styling, compact top status bar, sidebar navigation across the original workflows, and a session-level light/dark toggle. Existing page content remains backed by the same evaluation modules and SQLite operations.
- Redesigned the dashboard with a project hero, navigation actions, actual saved-record metrics, activity timeline, claim-status chart, recent evaluation table, and live system status. Counts/charts use database records; empty data is shown as empty/unavailable.
- Reworked New Evaluation into a two-column prompt/response workflow with the existing Manual/OpenAI selection and a transparent stage pipeline. The result snapshot distinguishes completed extraction/static/claim work from Docker execution, tests, and performance that have not been run. Code blocks have syntax highlighting, line numbers, and Streamlit's copy control.
- Added model comparison cards populated from each saved evaluation's code validation, test, process-time, and claim observations. Kept the no-aggregate-score policy.
- Added an ML Performance view. At the UI-only redesign checkpoint it displayed predictive values as unavailable because no training data/model existed; the supervised ML phase below now populates it with actual synthetic-pilot artifacts while preserving unavailable states for anything not measured.
- Reliability reports now use expandable engineering sections. The claim/evidence view explains whether the narrow rule plus retrieved documentation was used or whether the claim was not verified.
- Updated README navigation/theme/availability notes. The UI-only change preserved the then-existing ML, Docker, RAG, API, database, and evaluation behavior; the Docker status probe only calls `docker info` and never runs user code.
- Verification after redesign: all 50 offline tests passed/skipped as before (45 passed, 5 Docker-gated skips); compile check passed; Streamlit `AppTest` rendered each of the nine navigation destinations and both theme settings without exceptions; `pip check` found no broken requirements. Docker itself remains blocked by the unavailable Linux daemon, so execution integration remains unverified in this UI pass.

## Supervised ML phase — 2026-09-26

### Implemented

- Added `src/codeguard/ml/` modules for synthetic dataset creation/validation/versioning, exact and near-duplicate analysis, grouped splits, feature extraction, majority/Logistic Regression/Linear SVM baselines, grouped cross-validation, test evaluation, confidence thresholding, and advisory inference.
- Added scikit-learn, matplotlib, and joblib project requirements; current environment dependency consistency check passes.
- Added `data/ml/claims.csv`, split CSVs, timestamped immutable dataset snapshots, and `dataset_metadata.json`. The actual dataset contains **15 synthetic records**: 5 Supported, 5 Contradicted, and 5 Insufficient Evidence. No example is represented as human-labeled. Ten rule-derived examples preserve official source metadata; five out-of-scope examples carry source evidence only when retrieval returned a passage.
- Used proposition/topic groups to prevent paired or near-duplicate records crossing train, validation, test, and cross-validation folds. With only five independent groups per label, actual train/validation/test sizes are 9/3/3 (60/20/20), not the desired approximate 70/15/15. Four near-duplicate pairs were detected and kept within groups.
- Added word unigram/bigram TF-IDF for claim plus evidence and transparent claim/evidence word counts, lexical overlap, and retrieved similarity numeric features. Labels are not features.
- Trained and saved Logistic Regression and Linear SVM artifacts plus a majority-class baseline comparison. Saved test metrics, class reports, confusion matrix, model comparison CSV, dataset analysis, and error examples under `reports/`.
- Integrated Logistic Regression only as an advisory for rule-insufficient claims. Direct evidence-backed deterministic results are retained unchanged. SQLite now stores `rule_result`, `ml_result`, `ml_confidence`, `verification_method`, and `ml_review_required` via additive migrations. The UI labels probabilities uncalibrated, shows review-required below the validation-derived threshold, and describes ML predictions as advisory rather than proof.
- Connected the ML Performance page to the generated dataset, model version, actual test metrics, grouped CV, confusion matrix, class metrics, model comparison, and error analysis. No overall score is added.
- Added `docs/research/MODEL_CARD.md` and updated README and architecture documentation with provenance, split methodology, actual metrics, limitations, and reproduction command.

### Actual results

- Model version: `claim-verifier-v1.0.0`; dataset version is timestamped in its metadata.
- Held-out test has 3 rows (one per class). Majority baseline: accuracy 0.333, macro precision 0.111, macro recall 0.333, micro F1 0.333, macro F1 0.167, weighted F1 0.167.
- Logistic Regression: accuracy 0.333, macro precision 0.167, macro recall 0.333, micro F1 0.333, macro F1 0.222, weighted F1 0.222. It matched the majority baseline in accuracy.
- Linear SVM: accuracy 0.667, macro precision 0.500, macro recall 0.667, micro F1 0.667, macro F1 0.556, weighted F1 0.556. This tiny test result is not a valid estimate of real-world superiority.
- Three-fold **StratifiedGroupKFold on train only**: Logistic Regression mean accuracy 0.889 (std 0.157), mean macro F1 0.852 (std 0.210); Linear SVM mean accuracy 0.556 (std 0.157), mean macro F1 0.426 (std 0.183). The Logistic Regression gap between CV and held-out test indicates instability/overfit.
- Logistic Regression test errors: the contradicted dictionary insertion-order claim was predicted Supported; an insufficient-evidence string mutability claim was predicted Contradicted. Linear SVM also missed the contradicted dictionary claim.
- The confidence rejection threshold is **0.909170314714529**, derived as the next representable value above the most confident error among three validation rows. It is provisional; class probabilities are uncalibrated. Deterministic results remain authoritative.

### Verification and limitations

- Final suite: **61 tests run; 56 passed, 5 Docker-only tests skipped**. `compileall`, `pip check`, and Streamlit AppTest all passed. AppTest checked all nine navigation destinations, dark/light themes, OpenAI form mode without requesting the API, and rendered the populated ML page.
- Dataset/test scores are a pipeline demonstration only: all 15 examples are synthetic, only three test rows exist, and the current classifier performs poorly on held-out Logistic Regression cases. More independently reviewed data is required before any claim of useful real-world model performance.
- The Docker engine remained unavailable, but this ML phase did not change Docker execution or add any host-execution path.
## Final dataset building phase — 2026-09-26

### Scope and public-data research

- Inspected the existing pilot dataset (15 records, all synthetic), its 12-passage Python documentation corpus, grouped split and training code, current production model files, and existing test structure.
- Researched FEVER (185,445 claims; Wikipedia-derived SUPPORTS / REFUTES / NOT ENOUGH INFO with evidence references for supported/refuted records) and SciFact (about 1.4K biomedical claims with sentence-indexed support/contradict rationales). Their schemas are close to the task, but both are out of the Python-programming domain; SciFact's released claim labels also do not provide a robust insufficient-evidence class. They were recorded in `data/ml/final/dataset_sources.json` and excluded from the final candidate rather than mixed in for scale.
- The project’s curated Python documentation pages are under the PSF License Version 2. This phase retained their source URLs, passage IDs, sections, and license attribution. No third-party dataset was downloaded or used.

### Dataset delivered

- Added `src/codeguard/ml/final_dataset.py` as a reproducible data-only builder. It preserves the 15 pilot claim examples in the separate final output, adds controlled synthetic claims from 12 curated documentation propositions across mutability, collections, dictionaries, sets, comprehensions, built-ins, functions, loops, exceptions, and files, and runs structural, label, exact duplicate, near duplicate, evidence provenance, and group leakage checks.
- Created `data/ml/final/claims.csv`, `train.csv`, `validation.csv`, `test.csv`, `dataset_metadata.json`, `dataset_sources.json`, `dataset_analysis.json`, and `dataset_analysis.svg`.
- Final candidate: **31 synthetic records** — 13 SUPPORTED, 13 CONTRADICTED, and 5 INSUFFICIENT_EVIDENCE. Eight exact claim/evidence duplicates from overlapping pilot coverage were removed; six near-duplicate claim pairs were detected and remain within evidence groups; zero normalized-claim label conflicts were found. Evidence is present for 30/31 rows. One existing pilot insufficient-evidence example had no retrieved source passage; it remains explicitly marked as source-less and is not represented as contradicted or false.
- Leakage-resistant group splits: **22 train / 5 validation / 4 test** (71% / 16% / 13%). All labels occur in all three partitions and evidence groups do not cross partitions. The group constraint takes precedence over the requested approximate 70/15/15 proportions.
- Every record has `data_origin=synthetic`; none is described as manually verified or publicly labeled. The insufficient-evidence label means only that the supplied passage does not establish the claim.
- No public dataset was included. The candidate remains small, lexically controlled, and derived from a 12-passage source corpus; it is not a human-labeled benchmark or representative evaluation set.

### Training and production artifacts

- **No production model training was run.** The pilot data and current model artifacts remain in their original locations. The new final candidate is separate and is not connected to inference or the dashboard.
- The existing unit-test suite includes tests that fit models in temporary directories as part of pipeline regression coverage. That test-only fitting completed; it did not write to or replace production model artifacts.
- Before/after checks confirmed the model artifact files were not modified. Existing pilot dataset and split files were not overwritten.

### Verification

- Full offline suite: `python -m unittest discover -s tests -v` — **64 tests run, 59 passed, 5 Docker integration tests skipped** by their default opt-in guard.
- `python -m compileall -q app.py src tests` — passed.
- `pip check` — no broken requirements.
- Streamlit AppTest — initial default 3-second harness timeout was exceeded; rerun with `timeout=30` completed with **zero app exceptions**.
- No Docker integration tests were enabled and no submitted code was run.

### Status and remaining work

- This data-building phase is complete. The future model-training phase remains deliberately pending. Do not train from this synthetic candidate as though it were expert-labeled; acquire independently reviewed, programming-domain claim/evidence examples and create an external test set before treating later model metrics as meaningful.

## Phase 15 — Programming claim-evidence research dataset — 2026-09-26

### Implemented

- Added `src/codeguard/ml/research_dataset.py`, an isolated, deterministic data builder that does not train models, change production inference, or write to the prior pilot/final candidate locations.
- Created `data/ml/research_dataset/` with `raw`, `processed`, and `reports` directories; canonical dataset CSV; train, validation, test, and separate external test CSVs; source facts, source inventory, metadata, statistics, dataset card, data dictionary, license attribution, quality report, and two SVG summaries.
- Carried forward source-backed records from the previous synthetic candidate. Excluded a legacy source-less row rather than inventing its evidence or provenance. Added 30 claim examples grounded in 15 concise official Python documentation excerpts and six evidence-relative insufficient-evidence examples.
- External test: six examples from the Python Data Model reference page only; that page URL and proposition keys do not appear in internal splits. This is source-page isolation, but the examples remain synthetic and do not constitute an independent human benchmark.
- Researched FEVER, SciFact, StaQC, CoNaLa, and CodeSearchNet. Excluded all: the reviewed resources do not simultaneously meet the programming-domain claim/evidence/three-label task and licensing/provenance requirements. No public dataset was incorporated.
- All 66 internal and six external rows are marked synthetic and pending expert review. No manually verified label is claimed. `ready_for_model_training` is false; no model was trained and no production model artifact changed.
- Added `tests/test_research_dataset.py` covering schema and label constraints, duplicate/conflict detection, provenance and license requirements, source-group split isolation, external set isolation, reproducibility, and required output files.
- Full methodological details, data-source decisions, limitations, and outputs are in `docs/PHASE_15_DATASET_REPORT.md`.

### Actual build output

- Internal: **66 rows** — 28 Supported, 28 Contradicted, 10 Insufficient Evidence; grouped split **47/10/9** (train/validation/test).
- External: **6 rows** — two per label, from a held-out documentation page.
- Exact duplicates: 0; normalized claim-label conflicts: 0; human-verified records: 0.
- All rows are synthetic. Expert review and adjudication remain required before any model training or model-quality claim.

### Verification

- Initial build quality gate found near-duplicate candidates across different pages due to generic claim templates. IE examples were rewritten as varied, explicit claims, and the near-duplicate threshold set to 0.90 to avoid conflating distinct topics (for example, list and string mutability). The successful builder run then produced the counts above.
- `python -m unittest discover -s tests -v`: **70 tests run, 65 passed, 5 Docker integration tests skipped** by their default opt-in guard. This includes six Phase 15 tests. An initial new-test assertion expected the wrong validation message; it was corrected and the full suite then passed.
- `python -m compileall -q app.py src tests`: passed.
- `python -m pip check`: passed, no broken requirements.
- Streamlit `AppTest` of `app.py`: **zero app exceptions**.
- `pytest` invocation: not run because `pytest` is not installed in the project virtual environment. The repository's unittest suite was run instead; no package was installed solely for test discovery.
- The existing provider unit test emitted a Python `ResourceWarning` while cleaning up a mocked HTTP 429 response; the suite still passed. Docker integration remained skipped and is not verified by this run.
- Dataset reproducibility test rebuilt the dataset in a second clean temporary directory and compared all rows and splits; they matched.
- No model training, live provider request, or submitted-code execution was performed. Test-pipeline model fitting is limited to the existing tests' temporary directories. Production models remain untouched.

### Readiness and next step

- **Dataset build status: built; data readiness: NOT READY.** No training or inference changes are authorized by this dataset phase.
- Next work is independent human review/adjudication and acquisition or creation of a genuinely programming-domain, provenance-complete external benchmark. Model training and integration remain out of scope until data readiness criteria are met.


## Phase 16 — Programming claim-evidence research and human-review preparation — 2026-09-26

### Implemented

- Researched 19 programming QA/code, factuality, and evidence-verification dataset candidates. No public dataset was accepted; licensing, source, annotation type, candidate label mapping, and exclusion/hold reasons are recorded in the Phase 16 inventory and reports. CodeSimpleQA and ExpertQA remain `REVIEW`; neither was downloaded or imported.
- Added an isolated Phase 16 workspace with the 66 existing synthetic internal proposals, six external synthetic proposals, candidate inventory, manifest, quality indicators, source/license reports, and a review queue. Phase 15 source files remain unchanged.
- Added a local Dataset Review view with two independent reviewer slots, confidence/notes, disagreement and adjudication handling, and a separate Git-ignored SQLite review database. Only actual agreed/adjudicated human labels are exported as verified labels; proposed labels remain explicitly separate.
- Added reviewer, adjudication, schema, dataset-card, label-mapping, license, and quality documentation. No training or production inference change was made.

### Verified results

- Candidate resources investigated: 19; public datasets accepted: 0.
- Synthetic candidates: 66 internal plus 6 external. Human review: 0/72; rejected: 0; adjudicated: 0; label agreement: unavailable. Phase 17 readiness: **FALSE**.
- Exact duplicates: 0; normalized claim-label conflicts: 0; near-duplicate pairs at similarity >=0.90: 15, with zero split/external leakage violations. Source-group split violations: 0. Metrics are reported separately; no aggregate quality score was created.
- `python -m unittest discover -s tests -v`: **81 tests passed, 5 Docker integration tests skipped** by their default opt-in guard.
- `python -m compileall -q app.py src tests`: passed. `python -m pip check`: no broken requirements. Streamlit AppTest: zero app exceptions.
- No Docker execution integration run, live provider call, submitted-code execution, or production model training was performed.

### Limitations and next phase

- All 72 proposed examples are synthetic. No human-verified external benchmark exists, and public dataset compatibility/licensing is unresolved for held candidates. The review page is ready for real reviewers, but no reviews have been supplied yet.
- Phase 17 model training is **not ready**. Do not train or claim meaningful model quality until actual independent human review/adjudication, licensing clearance, adequate source/topic breadth, and an independent human-reviewed external set are available.
- Full details and created/modified file inventory: `data/ml/phase16/reports/PHASE_16_REPORT.md` and `docs/phases/PHASE_16_DATASET_REPORT.md`.


## Phase 16.5 — Source-backed candidate expansion and review controls — 2026-09-26

### Implemented

- Added an idempotent Phase 16.5 builder, curated fact/source inventories, source-group metadata, quality exclusion log, mixed internal review batches, and a distinct external queue. Preserved the prior Phase 16 candidates and existing review-event database.
- Added 92 new synthetic candidates based on 31 manually curated facts from 17 official Python documentation pages. The 164-candidate total spans 24 source URLs, 72 fact keys / claim families, and 34 topic labels. There are 143 internal candidates and 21 separately held external candidates. Internal/external source-URL and fact-key overlap counts are both zero.
- New candidates retain blank `label` and `gold_label`; `proposed_label` is explicitly unverified. One new near-duplicate candidate was excluded. The 15 near-duplicate pairs in the expanded queue are inherited from Phase 16 and are surfaced in `duplicate_audit.json` rather than hidden.
- Review batches are class/topic mixed and start with an introductory batch. The Dataset Review UI supports internal batch filtering, separate external review, reviewer navigation, source links, timestamps, evidence-only or optional source-verified mode, and a proposed-label reveal that is hidden by default.
- Tightened the label boundary: two matching independent reviews remain agreement pending adjudication; only a distinct adjudication populates a gold label. The adjudicated export is the only Phase 16.5 export intended to carry gold labels. Review event history records timestamps, mode, and source-verification choice.
- No model was trained, edited, or evaluated. No production inference was changed.

### Verified results

- Phase 16.5 build completed and refreshed artifacts under `data/ml/phase16_5/`. The candidate target is 1,000; current total is **164**, so target is **NOT MET**. All 164 are pending, zero reviewed, zero adjudicated, zero rejected, and zero gold-labeled. Phase 17 readiness remains **FALSE**.
- Proposed-label counts across all candidates are Supported 61, Contradicted 60, and Insufficient Evidence 43. These are queue proposals only, not ground truth or verified class balance.
- `python -m unittest discover -s tests -v`: **86 tests passed; 5 Docker integration tests skipped** by their opt-in guard.
- `python -m compileall -q app.py src tests`: passed. `python -m pip check`: no broken requirements. Streamlit AppTest: **zero app exceptions** (one benign bare-mode ScriptRunContext warning).
- Builder execution produced the expected source, candidate, and batch outputs. No submitted code was executed, no Docker integration test was enabled, no live API call was made, and no model training occurred.

### Limitations and next gate

- The candidate target is not met. The candidate pool is synthetic and built from a concentrated Python documentation source set; it is not a human-labeled dataset. One lexical exclusion and inherited near-duplicate records need reviewer disposition.
- The external queue is source-page separated from internal candidates but is not an independent human benchmark. All candidate claims, evidence excerpts, source sections, and proposed labels still require independent source-backed review by two people; any disputed/agreeing records require a distinct adjudication to create gold labels.
- Do not begin Phase 17 training or make model-quality claims. Meet the 1,000-candidate minimum with quality-controlled examples, complete independent review/adjudication, clear license review, and establish a human-reviewed independent external benchmark first.
- Details, reproducible counts, limitations, and generated files: `docs/phases/PHASE_16_5_REPORT.md` and `data/ml/phase16_5/README.md`.

## Phase 16.6 — Candidate scaling — 2026-09-26 (incomplete)

- Verified the Phase 16.5 baseline directly from `reviews.sqlite3` and the candidate export: 164 records, 143 internal, 21 external, 24 source URLs/source groups, 72 fact keys, and 34 topics. All 164 remain pending; no reviewer event or gold label exists.
- No candidates were added in this attempt. The reviewed source inventory is still the Phase 16.5 inventory. The 1,000-candidate goal was not met; the external subset is 21, below the 100-record target. The 15 >=0.90 lexical near-duplicate pairs remain inherited from Phase 16 and are reported in `duplicate_audit.json`; one prior candidate is listed in the existing quality exclusion log.
- Improved Dataset Review filters to include topic, source URL, source group, proposed label, reviewer, and adjudication state in addition to status, partition, and batch. Changed Phase 16.5 starting/new candidate statistics to derive from actual queue IDs/counts instead of assuming a fixed starting total.
- Phase 17 remains **NOT READY**. The candidate volume, external volume, independent human review/adjudication, gold labels, licensing review, and external benchmark review gates are unmet. No training or production model changes were made.
- Verification: Phase 16/16.5 review tests passed (16/16); Python compileall passed; pip check found no broken requirements. Full unittest discovery ran 77 tests: 71 passed, 5 Docker tests skipped, and test-module import failed for `tests.test_ml_pipeline` because scikit-learn is not installed in the available Python runtime. The Phase 16.5 builder reran successfully and preserved all 164 records and their pending review state.
- See `docs/PHASE_16_6_REPORT.md` for exact current-state counts, test limitation, and remaining gates.

## Phase 16.6B — Source-fact inventory expansion and candidate scaling — 2026-09-26

- Verified the starting state directly: 164 candidate records; 143 internal / 21 external; 72 fact keys; 24 source URLs; 34 topics; 164 pending; 0 reviewed, adjudicated, or gold-labeled. Review-event tables contained no human events.
- Appended 55 source facts curated from 16 official Python documentation URLs, across 24 newly covered topic labels. Fact records include stable fact keys, canonical claims, source URL/title, source group, section locator, evidence summary, license attribution, provenance status, and pending human-review status.
- Generated 147 candidates from the new facts (36 internal and 111 external). Candidate generation varies between two forms for internal facts and three for external facts. Candidate IDs are stable fact-key-derived; claims remain synthetic with proposed labels, pending status, and blank labels/gold labels.
- Actual database/export after build: 311 candidates total (179 internal / 132 external), 127 fact keys, 39 unique source URLs, 32 recorded source groups, and 58 topic labels. Internal/external source URL overlap is 0; fact-key overlap is 0. Exact normalized duplicates and same-fact semantic-signature duplicates are 0. The same-fact signature preserves negation so real contradictions remain distinct. The 15 >=0.90 near-duplicate pairs are inherited from the Phase 16 baseline; 0 new near-duplicate candidates and 0 new quality exclusions were recorded (the cumulative prior exclusion log contains 1).
- Reran the builder and compared persisted review identities, states, gold fields, and review-event counts: 311 records were unchanged, no new records were inserted, and event counts remained 0. No prior records or human review states were overwritten.
- Review queue status: 311 pending; 0 human-reviewed; 0 adjudicated; 0 gold-labeled. Production model changed: NO. Training performed: NO. Phase 17: NOT READY.
- `python -m unittest discover -s tests -v`: 83 discovered; 77 passed, 5 Docker integration tests skipped, 1 module import error (`sklearn` missing from the available runtime). Phase 16.6B focused tests: 6 passed. Compile checks passed; `pip check` found no broken installed requirements.
- Environment limitations: the supplied runtime lacks both `scikit-learn` and Streamlit despite the project's requirements listing scikit-learn; the project `.venv` interpreter could not be launched. Docker CLI is unavailable. Streamlit AppTest was not run.
- The requested 200–300 fact-key target and 1,000 candidate minimum remain unmet. The 55 added facts are a verified, useful expansion, but further page-by-page source curation is needed before expanding the pool further without relying on unsupported facts or repetitive variants. Phase 17 remains blocked by candidate volume, source breadth, review/adjudication, gold labels, licensing sign-off, and external benchmark review.
- Full current results and exact remaining gates: `docs/phases/PHASE_16_6B_REPORT.md`.

## Phase 16.7 — Official Python source/fact inventory expansion — 2026-09-26

- Audited the persisted source/fact inventory and identified under-coverage in execution-model name resolution and exception semantics, threading synchronization, warning filters, and operating-system environment behavior.
- Added 19 inventory-only facts from four official Python documentation pages (Execution model, threading, warnings, and os). Each row records a stable key, canonical fact, topic, source URL/title/group, locator, paraphrased evidence, license/provenance metadata, and pending independent-review status.
- Final fact inventory: **146 unique keys**, 43 source URLs, 43 source groups, and 66 topics (starting baseline 127 keys). Normalized exact duplicates rejected: 0; near-duplicates at ≥0.90 similarity rejected: 0; Phase 16.7 quality exclusions: 0.
- Candidate dataset remained **311 before / 311 after**, all pending. Human reviewed: 0; adjudicated: 0; gold-labeled: 0. Builder merges Phase 16.7 facts into the inventory only; it does not generate candidate variants from them. An idempotency rebuild preserved candidate IDs and states; review-event tables remain empty.
- The target of 250–300 fact keys is not met. This pass stopped at a bounded, source-checked increment; further topic and page review is needed. Phase 17 remains **NOT READY**; no training or production model change occurred.
- Verification: full unittest discovery ran **85 tests: 79 passed, 5 Docker-gated skips, 1 import error** because `scikit-learn` is unavailable. Focused Phase 16.7/16.6B/16.5 inventory checks passed; compileall passed; pip check found no broken installed requirements. Streamlit is unavailable for AppTest and Docker CLI is unavailable for integration checks.
- Full details and official source links: `docs/PHASE_16_7_REPORT.md`.

## Phase 16.8 — Bounded official Python fact expansion — 2026-09-26

- Audited the 146-key inventory for underrepresented areas, then added **59 inventory-only facts** from official Python documentation covering import cache/loading, descriptors and attribute access, comparisons/hashing, iterator/generator and async iteration protocols, context-manager exception handling, subprocess behavior, pathlib, itertools, dataclasses, enum, typing, logging, and functools.
- Final inventory: **205 unique fact keys**, 45 source URLs, 45 source groups, and 97 topic labels. Exact duplicates rejected: 0; normalized near-duplicates at ≥0.90 similarity rejected: 0; quality exclusions: 0.
- Candidate pool remained **311 before / 311 after**, with **0** new candidates. Two inventory-builder runs retained all candidate IDs, review statuses, label fields, and gold-label fields. Review database counts remained 311 records, 0 review events, and 0 adjudication events. Human reviewed: 0; adjudicated: 0; gold labelled: 0.
- Phase 17 remains **NOT READY**. No training, review data fabrication, or candidate generation occurred.
- Verification: unittest discovery ran **88 tests: 82 passed, 5 Docker-gated skips, 1 import error** because scikit-learn is unavailable. Focused inventory tests passed; compileall passed; pip check found no broken installed requirements. No Streamlit, Docker, or ML verification is claimed.
- Full details and official source links: `docs/PHASE_16_8_REPORT.md`.

## Phase 16.9 — Candidate capacity test and controlled expansion — 2026-09-26

- Measured the 205-key inventory before generating candidates: 127 keys already had candidates and 78 had none. Existing per-fact candidate counts were 12 facts with one, 47 with two, 67 with three, and one with four. Conservative measured capacity after testing one source-backed canonical claim for each uncovered fact was **389 candidate records**, below the 1,000 target.
- Dry-run exact/normalized/near-duplicate checks passed for all 78 uncovered fact claims against existing candidates and the batch: 0 exact duplicates, 0 ≥0.90 near-duplicate matches, 0 quality exclusions. Appended one Supported proposal per fact; no templated Contradicted or Insufficient Evidence claims were added.
- Candidate pool grew **311 → 389**: 193 internal and 196 external. Proposed-label counts: Supported 188, Contradicted 109, Insufficient Evidence 92. Internal/external source URL, fact-key, and normalized-claim overlap are each zero. The 15 inherited near-duplicate pairs remain visible; no new candidate enters those pairs.
- All 389 remain pending; human reviewed 0, adjudicated 0, gold labelled 0. The second Phase 16.9 build inserted 0 records and preserved IDs, review states, label/gold fields, and event counts (0 review, 0 adjudication events). No model training or production inference changes occurred.
- Phase 17 is **NOT READY**. Details and capacity reasoning: `docs/PHASE_16_9_REPORT.md`.
- Verification: unittest discovery ran **91 tests: 85 passed, 5 skipped, 1 import error** due to missing scikit-learn. Focused dataset tests passed; compileall passed; pip check found no broken installed requirements. No Streamlit, Docker, or ML verification is claimed.

## Phase 17 — Public dataset ML training and integration — 2026-09-27

- Researched seven public candidates in `docs/research/PHASE_17_DATASET_RESEARCH.md`. Selected NVIDIA OpenCodeReasoning-2 for a bounded auxiliary experiment because its Python split includes source-recorded execution `pass_rate`; it is not a human-labelled CodeGuard claim dataset.
- Pinned to revision `eadf535931451525f3e5621d0f960c240bc62fd9`. Downloaded three contiguous Python shards: **60,000 rows**. All sampled rows reported `apache-2.0`; dataset collection is identified as CC BY 4.0 and upstream license terms are retained as a limitation. Original Parquet files, URL, timestamp, per-file SHA-256, revision, license metadata, and aggregate checksum are stored in `data/raw/phase17/`.
- Preprocessing retained **53,401** usable rows after excluding 3,688 invalid/unavailable pass-rate rows, 2 rows without code, and 2,909 exact duplicates. Static syntax check found 0 malformed rows. Code was not executed. Semantic near-duplicate matching was not run.
- Auxiliary task: regress source-recorded `pass_rate` in [0,1]. The generated `right`/`wrong` judgement, QwQ critique, R1 rationale, and placeholder problem text were excluded from features. Nothing was mapped to Supported/Contradicted/Insufficient Evidence. Human reviewed: **0**; adjudicated: **0**; gold labelled: **0**.
- Fixed seed 1701, grouped 70/15/15 split using connected question-ID/exact-normalized-code groups: **37,365 train / 8,144 validation / 7,892 test**. Cross-split question-ID and exact-code overlap: 0. Models: Dummy mean, Ridge, LinearSVR, ExtraTrees numeric. LinearSVR selected by validation MAE.
- Held-out result: MAE **0.2015**, RMSE **0.3238**, R² **0.2066**, Spearman rho **0.4888**. For the explicitly derived (not source-labelled) `pass_rate >= 0.5` view: accuracy **0.8060**, macro F1 **0.6273**, weighted F1 **0.7639**, ROC-AUC **0.7755**, PR-AUC **0.8985**. This measures contest-dataset pass-rate prediction, not general code correctness or factual verification.
- Model/inference integration: `models/phase17/pass_rate_predictor.joblib` and configuration artifacts; `src/codeguard/ml/public_reliability.py`; new Streamlit “ML Reliability Analysis” page keeps ML output, deterministic AST validation, and explanation evidence separate. Existing claim-verifier model and Phase 16 review records were not relabelled or replaced.
- Reports: `docs/research/PHASE_17_DATASET_SELECTION.md`, `docs/phases/PHASE_17_FINAL_REPORT.md`, dataset statistics/sample/preprocessing/split/model results, figures, and system proxy comparison. Reproduction entry points: `scripts/download/download_phase17_dataset.py` and `scripts/training/train_phase17.py`.
- Final verification: **105 tests run, 100 passed, 5 Docker-gated tests skipped**; `compileall` passed; `pip check` reported no broken requirements. Streamlit 1.64.0 AppTest rendered 11 tabs and the auxiliary prediction form without exceptions. Docker unavailable; no Docker or dataset-code execution verification is claimed.
- Phase 17 public-data auxiliary experiment: **COMPLETE**. CodeGuard gold-labelled claim-verification readiness remains **NOT READY** because the 389 Phase 16 candidates are still pending and human-reviewed/adjudicated/gold counts remain zero. See `docs/phases/PHASE_17_FINAL_REPORT.md` for metrics, comparison, methodology, limits, and reproduction details.

## Final Docker and application verification — 2026-09-27

- Docker Desktop CLI 29.8.0 and Compose 5.5.1 were invoked from the per-user installation path; `docker info` reported the reachable `desktop-linux` Linux engine. The harmless `python:3.12-slim` container returned Python 3.12.14.
- Full suite with `CODEGUARD_DOCKER_INTEGRATION=1`: **105 tests passed, 0 failed, 0 skipped**, including all 5 Docker integration tests. Existing unsafe-code validation tests flag `os.system` and `eval` patterns without executing submitted source; the Docker timeout integration sample also passed.
- `python -m compileall -q app.py src tests`: passed. `python -m pip check`: no broken requirements. Streamlit AppTest: **0 app exceptions**.
- Phase 17 auxiliary pass-rate predictor loaded the existing `models/phase17/pass_rate_predictor.joblib` artifact and returned a numeric prediction for a benign sample. The model and dataset were not modified.
- Existing Docker runner configuration remains `--network=none`, `--read-only`, `--user=65534:65534`, `--memory=128m`, `--cpus=0.5`, and `--pids-limit=32`, with in-container and outer timeout controls and bounded output. No sandbox restrictions were weakened.
- Verification was run from an elevated process context because the restricted Codex shell could not launch the per-user Docker CLI or project virtual-environment interpreter directly. Docker engine and container checks succeeded in that context.
- No application code, model, or dataset changes were made in this verification.

## Phase 18 — End-to-end demonstration validation — 2026-09-27

- Added five deterministic demo cases and an orchestration runner that invokes the existing extraction, storage, AST validation, Docker execution, function tests, execution measurement, explanation claim extraction, corpus evidence retrieval, evidence-backed verification, Phase 17 prediction, and reliability report builder. Each run uses a temporary SQLite database and leaves normal app history untouched.
- Results: correct solution (AST valid, Docker passed, test passed, list-mutability claim Supported); incorrect `max` implementation (AST valid and Docker execution passed, expected-sum function test failed); false `Lists are immutable.` claim (correct code/tests, documentation verification Contradicted); deliberately quadratic sum (correct test, measured child-process runtime 0.495477 s for 3,500 values in this run); `open` risk case (AST `valid_with_risks`, Docker/test passed for a write confined to container `/tmp`). All five declared expected signals were observed.
- Phase 17 inference returned numeric predictions for all five cases using the existing `linear_svr_c0_1` artifact. The estimate remains an auxiliary contest pass-rate prediction, not a CodeGuard correctness verdict. No model or dataset was added or modified.
- The existing report builder does not include the Phase 17 prediction. Exports therefore retain its report unchanged and include the prediction as a sibling in a transparent `final_output` envelope. Timings are observations including interpreter/container overhead, not benchmark guarantees. The risk case is a benign bounded file operation; it does not claim static analysis blocks flagged code.
- Human-readable walkthrough: `docs/demo/PHASE_18_DEMO_CASES.md`. Per-case machine-readable outputs: `reports/phase18/{correct,incorrect_code,explanation_error,performance,risk}.json` and `reports/phase18/summary.json`.
- Verification: full unittest discovery with `CODEGUARD_DOCKER_INTEGRATION=1` ran **110 tests: 110 passed, 0 failed, 0 skipped**, including the 5 Phase 18 end-to-end tests and all 5 existing Docker integration tests. `python -m compileall -q app.py src tests` passed; `python -m pip check` found no broken requirements; Streamlit AppTest had 0 app exceptions. No Docker security restrictions were changed.

## Phase 19 — Unified ML and verification report integration — 2026-09-27

- Integrated the existing Phase 17 pass-rate predictor into report schema version 2 as first-class `ml_reliability` structured data. The signal includes actual model/revision, task, prediction range and live prediction, Phase 17 dataset name and row counts, model parameters/seed, feature metadata, limitations, and `confidence: null` because no calibrated confidence or uncertainty is available.
- Kept eight report signals distinct: static AST analysis, separately recorded Docker execution, restricted Docker function tests, performance measurements, explanation claim extraction, evidence retrieval, claim verification, and ML reliability. No combined reliability score was introduced. The predictor is explicitly an auxiliary estimate of source-recorded competitive-programming execution pass rate, not general code correctness, factual/explanation correctness, or a human/gold label.
- The Streamlit Reliability Report now displays the predictor in the main report view and its JSON download. It labels the predicted pass-rate value, model/version, dataset/size, and code block; help text explains its scope. If ML inference is unavailable or fails, the report records that state and retains other sections.
- Phase 18 case reports were regenerated in `reports/phase18/` with unified report objects. The five deterministic cases all produced expected signals on the final rerun.
- Added eight Phase 19 regression tests for report inclusion, metadata, range, missing/failing ML, AST preservation, Docker-result preservation, and evidence/verification separation. Phase 18 integration tests also assert the unified live ML metadata.
- Documentation: `docs/phases/PHASE_19_UNIFIED_REPORT.md`; Phase 18 walkthrough updated to describe the unified report.
- Final verification: `CODEGUARD_DOCKER_INTEGRATION=1 python -m unittest discover -s tests -v` ran **118 tests: 118 passed, 0 failed, 0 skipped**, including all 10 Docker tests and 5 Phase 18 end-to-end cases. `python -m compileall -q app.py src tests` passed; `python -m pip check` found no broken requirements; Streamlit AppTest had 0 app exceptions.
- No new dataset or model was introduced, no training occurred, and Docker restrictions were not modified.

## Phase 20 — Product UI, authentication, and observability — 2026-09-28

- Recorded baseline before changes: **108 passed, 10 skipped**; baseline compileall passed; existing Streamlit AppTest rendered without exceptions. The Docker CLI was unavailable.
- Fixed code extraction for labeled/generic fences, multiple blocks, and AST-valid unfenced Python mixed with explanation. Added user-friendly no-code guidance and regression coverage for extraction variants.
- Added additive SQLite authentication, ownership, report, and event storage. User passwords are salted scrypt hashes; developer creation is a one-time hidden-prompt CLI bootstrap. Application services enforce USER/DEVELOPER roles and user-owned evaluation/report access.
- Added a modern landing/login, separate user workflow/history/compare/profile views, and developer engineering console. The authenticated pipeline calls existing CodeGuard extraction, static analysis, Docker execution, tests, performance measurements, evidence-backed claim verification, Phase 17 inference, and the Phase 19 report builder. No report score was combined and no research artifacts were changed.
- Added structured events with secret redaction and a 5,000-row retention bound; developer-only evaluation/log/health/Docker/ML/evidence/dataset/user/settings pages; improved code/results and empty/error states. Dashboard metrics use persisted evaluation IDs and measurement records.
- Verification: final `python -m pytest -q`: **140 passed, 10 skipped, 0 failed**. The skips are 5 Docker integration tests and 5 Phase 18 Docker demos. `python -m compileall -q backend frontend scripts tests`: passed. `python -m pip check`: no broken requirements. Streamlit AppTest role/page flows passed; the live app at `http://127.0.0.1:8501` returned HTTP 200 with a clean startup log. The existing Phase 17 model loaded and returned a real prediction.
- Docker integration and container-backed evaluation could not be run: no Docker CLI is available in this environment. No Docker availability or success is claimed. The existing runner restrictions were preserved. See `docs/phases/PHASE_20_PLAN.md` for the security and environment limitations.
- Added Phase 20 authentication, authorization, health, pipeline, extraction, storage, and Streamlit UI regression tests. README, architecture, and environment example were updated. No model or dataset was modified; no human review or labels were created.
- Import path follow-up: an editable package record in the active venv pointed at another checkout. Streamlit entry points now add the project-relative `backend/src` directory; the existing setuptools editable package was reinstalled from `C:\Codeguard_AI`. The import-path regression and normal-entrypoint AppTest pass when launched from outside the project directory.

## Phase 20 — Environment health repair follow-up — 2026-09-29

- Diagnosed the old `.venv` as mixed-ABI: CPython 3.11.9 contained CPython 3.14 Windows wheels, causing pandas and matplotlib native import failures and 11 `pip check` platform errors. Retained the old environment and created `.venv_clean` with compatible CPython 3.11.9 wheels; Python 3.12 was not installed, and 3.11 meets the project requirement.
- Clean-environment verification passed: full suite with `CODEGUARD_DOCKER_INTEGRATION=1` (**150 passed, 0 failed, 0 skipped**), compileall, pip check, Phase 20 AppTests, native package imports, ML prediction, database quick check, and a real temporary-database evaluation through restricted Docker. Docker engine and harmless container test were available. The existing database and ML model were retained.
- Launched the app from `.venv_clean`; localhost returned HTTP 200 and Streamlit health returned `ok`. See `docs/PHASE_20_ENVIRONMENT_HEALTH_REPORT.md` for package versions, evidence, and detailed audit results.
- Limitation: the existing production DEVELOPER password was not supplied, so authentication of that specific stored account could not be tested. Auth/RBAC flows passed with disposable credentials. A later shell-only rerun attempt was blocked because the host denied process execution for the user-level Python executable; this does not alter the earlier completed clean-environment verification recorded in the report.
