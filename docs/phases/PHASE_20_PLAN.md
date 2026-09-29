# Phase 20 implementation plan

## Baseline

- Repository: `C:\Codeguard_AI`, a clean `main` worktree at baseline commit `ffc0eb0`.
- Streamlit entry point: `frontend/app.py`.
- Business logic: `backend/src/codeguard/`; SQLite persistence is in `storage.py`.
- The existing Streamlit application exposes eleven tabs. Evaluation runs extraction, static analysis, claim/evidence verification, and ML advisory inference before persisting the report. Docker execution, function tests, and performance measurement are separate user-triggered actions.
- The existing schema contains evaluation sessions, questions, responses, extracted code, tests, metrics, and verified claims. Existing evaluation ownership, authentication, structured event logging, and role checks are not present.
- The Docker runner in `execution.py` uses `python:3.12-slim`, disables networking, uses a read-only root filesystem and UID/GID 65534:65534, and applies memory, CPU, process, timeout, and output limits. No host execution fallback is present.
- Phase 17 inference, official Python evidence retrieval and verification, Phase 16 dataset review, Phase 18 demonstrations, and Phase 19 unified reporting are existing research features to preserve.
- Baseline command `python -m pytest`: **108 passed, 10 skipped** in 79.55 seconds. Five Docker integration tests and five Phase 18 Docker demonstrations were skipped because their opt-in integration environment was not enabled. The Docker CLI is not available in this environment.
- Baseline `python -m compileall backend frontend scripts tests`: passed.
- Baseline Streamlit AppTest: zero exceptions and all eleven existing tabs rendered. The existing Streamlit server wrote a clean startup log and its local address was bound to port 8501.

## Planned implementation

1. Expand extraction to accept labeled and generic fences plus AST-valid unfenced code in mixed prose. Preserve multiple blocks and explanatory prose; expose actionable no-code feedback. Add focused extraction tests first.
2. Add SQLite user accounts with scrypt password hashes, one-time CLI developer bootstrap, session login, and explicit role-checked service functions. Add a nullable owner reference to existing evaluation sessions with a safe migration; legacy rows remain visible to developers only.
3. Add user-isolated history and reporting queries, user registration/login/profile, and a user dashboard with evaluation, history, comparison, and profile workflows that call the existing analysis engine.
4. Add structured, redacted, bounded application event logging and developer-only observability pages for real evaluation counts, logs, system health, Docker configuration/availability, ML artifacts, evidence corpus, datasets, users, and settings.
5. Apply reusable design tokens and shared UI components, improve code/results/history/error/empty states, and keep the existing separate evaluation signals and security restrictions.
6. Add authentication, access-control, logging, health, and UI tests; run all existing tests plus supported Docker tests where available; compile, check dependencies, launch Streamlit, and update setup/security/architecture documentation.

## Constraints and validation

- Do not change model artifacts, research labels, or datasets.
- Do not weaken Docker isolation or add host execution.
- Do not fabricate users, events, metrics, or evaluation results.
- Use disposable test databases for account, ownership, and event tests.
- Treat Docker integration verification as unavailable when the Docker CLI/engine cannot be reached; do not report skipped checks as passes.

## Implementation and final verification — 2026-09-28

- Implemented robust Python extraction for Python/py/generic fences and AST-valid unfenced blocks in mixed prose. Multiple blocks retain their order; invalid and non-Python blocks stay in the explanation.
- Added additive SQLite migrations for users, owner-scoped evaluations, saved unified reports, and bounded application events. Existing evaluation/review records are preserved. User passwords use salted scrypt hashes. A one-time `python -m codeguard.auth_bootstrap <username>` command prompts for the developer password without placing it in arguments or source.
- Added application-level USER/DEVELOPER authorization, user-isolated history/reports/comparison/profile workflows, and a distinct engineering console. Both role page sets are covered by Streamlit AppTest.
- The shared pipeline now calls the existing extraction, AST/risk validation, Docker runner, function tests, measurements, claim extraction, official evidence verification, Phase 17 advisory inference, and Phase 19 report builder. It persists each evaluation and emits structured events. The Phase 17 model and dataset were not changed.
- Added developer-only operational views for evaluations, redacted/filterable logs, live SQLite/Docker/ML/evidence/filesystem checks, sandbox configuration and harmless Docker runtime probe, model metadata/metrics, evidence corpus, Phase 16 dataset/review queue, users, and settings. Dashboard metrics query persisted records and measurement names.
- The actual Streamlit app returned HTTP 200 from `http://127.0.0.1:8501` with no startup traceback. The existing Phase 17 artifact loaded and generated a real `linear_svr_c0_1` prediction. `python -m compileall -q backend frontend scripts tests` passed; `python -m pip check` reported no broken requirements.
- Final `python -m pytest -q`: **140 passed, 10 skipped, 0 failed**. The 10 skips are the five Docker integration tests and five Phase 18 Docker demonstrations. The Docker CLI is not available in this environment, so Docker engine/image/runtime integration and real evaluation execution could not be verified here. The Docker dashboard correctly reports that availability state; restrictions remain in the runner and runtime probe.
- Security/working-tree review: no `.env` file or runtime database is tracked; the runtime database and Streamlit logs are ignored. No model, dataset, candidate, or review labels were changed. Existing tests updated `docs/phases/PHASE_16_DATASET_REPORT.md` with current generated paths; the changed paths are valid and retained.
- Remaining environment limitation: run `CODEGUARD_DOCKER_INTEGRATION=1 python -m pytest tests/docker` on a host where Docker Desktop CLI and Linux engine are reachable to verify the Docker-dependent cases and complete a real container-backed evaluation.
- Streamlit import follow-up: this virtual environment initially had an editable `codeguard-ai` install pointing at the separate `C:\codex` checkout. Both Streamlit entry points now add their own checkout's `backend/src` path before package imports, and `python -m pip install --no-deps -e .` reinstalled the existing `pyproject.toml` package from `C:\Codeguard_AI`. Verified import resolution points to this checkout.
