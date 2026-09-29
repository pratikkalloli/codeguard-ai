# Phase 20 implementation report

Date: 2026-09-28

## Summary

Phase 20 adds an authenticated user experience and a separate developer console around the existing CodeGuard evaluation and research components. The existing report schema and individual analysis signals remain distinct. The Phase 17 model, datasets, and review labels were not modified.

## Implementation

- **Python extraction:** `backend/src/codeguard/input_processing.py` recognizes Python and `py` fences, generic AST-valid fences, and AST-valid unfenced code in mixed prose. It preserves multiple valid blocks in order and retains invalid/non-Python material as explanation text.
- **Database:** `backend/src/codeguard/storage.py` adds safe, additive tables for user accounts, structured application logs, and unified reports; evaluation sessions get nullable owner and display-name fields. Legacy evaluation rows remain available to developers. Runtime database files remain ignored.
- **Authentication and authorization:** `backend/src/codeguard/auth.py` uses salted scrypt hashes and server-side session revalidation. Registration creates USER accounts only. A one-time developer bootstrap is available with `python -m codeguard.auth_bootstrap <username>`; the password is prompted privately. `backend/src/codeguard/access.py` gates evaluation and report list/detail access by role and owner.
- **User interface:** `frontend/phase20_ui.py` provides landing, sign-in/registration, HOME, NEW EVALUATION, MY EVALUATIONS, COMPARE, and PROFILE. Evaluations use the existing extraction, AST/risk analysis, Docker execution, optional function tests, measurements, claim/evidence verification, ML inference, and unified report builder through `backend/src/codeguard/pipeline.py`. Progress updates are sent by real component completion callbacks. Results retain separate signals and display source, outputs, tests, performance, risks, claims, evidence, ML metadata, and saved report.
- **Developer interface:** a separate role-gated navigation exposes OVERVIEW, EVALUATIONS, LOGS, SYSTEM HEALTH, DOCKER, ML, EVIDENCE, DATASETS, USERS, and SETTINGS. Dataset Review continues to use the existing Phase 16 reviewer/adjudication system.
- **Logging:** `backend/src/codeguard/events.py` records evaluation IDs, actors, event/level/component, timing, status, error type, and bounded details. Sensitive-key and token-pattern redaction runs before persistence; retention is capped at 5,000 rows. Log retrieval requires the DEVELOPER role.
- **Health and dashboards:** `backend/src/codeguard/health.py` checks the local SQLite database, Docker CLI/engine/image, model inference, documentation corpus retrieval, expected project directories, runtime versions, and configuration presence. It displays the Docker runner restrictions and labels them a local development boundary, not a production sandbox. The Docker runtime probe uses a harmless Python version command and the same isolation limits. The ML dashboard reads existing metadata/results; evidence and dataset pages read existing corpus/dataset/review data.
- **Design and docs:** the interface has reusable dark graphite styling, restrained gradients, card and status treatments, shared navigation, code highlighting, and explicit loading/error/warning/empty states. Updated README, architecture, `.env.example`, Phase 20 plan, and project progress.
- **Streamlit imports:** both entry points now derive the checkout root and add `backend/src` before importing `codeguard`. `pyproject.toml` already configures setuptools package discovery for that source layout; README setup now installs the project editable with `python -m pip install -e .`.

## Tests and verification

- Baseline before changes: **108 passed, 10 skipped**.
- Final `python -m pytest -q`: **140 passed, 10 skipped, 0 failed**.
- `python -m compileall -q backend frontend scripts tests`: passed.
- `python -m pip check`: no broken requirements.
- Phase 20 Streamlit AppTest covered registration/login, user pages, developer pages, access denial, and the existing dataset review view without app exceptions.
- Import regression imported `phase20_ui` from outside the checkout and asserted `codeguard.__file__` resolves under this project's `backend/src`. The normal `frontend/app.py` also passed AppTest from outside the checkout. The initial environment editable install targeted `C:\codex`; it was reinstalled from `C:\Codeguard_AI`, and both Streamlit entry points now bootstrap the backend source directory relative to their own file locations.
- Real Streamlit process started from `frontend/app.py`; `http://127.0.0.1:8501` returned HTTP 200 and the startup log contained no traceback.
- The existing `linear_svr_c0_1` Phase 17 artifact loaded and made an inference. This remains an advisory estimate of the upstream `pass_rate` target, not a general correctness or security classifier.
- Docker CLI was not found. The five Docker integration tests and five Phase 18 container-backed demonstrations were skipped by their normal guards. A real container-backed evaluation was therefore unavailable in this environment; this report does not claim Docker verification.

## Security and limitations

- Existing Docker execution restrictions remain intact; no host execution fallback or evaluated-code network access was added. The developer probe uses `--network=none`, read-only root, UID/GID 65534:65534, dropped capabilities, no-new-privileges, 128 MiB memory, 0.5 CPU, 32 processes, bounded time/output, and an isolated temporary filesystem.
- Existing user-owned history/report queries and developer page services have application-level role checks. UI navigation hiding is not the authorization boundary.
- Developer bootstrap is intentionally local and one-time. Configure `CODEGUARD_DATABASE_PATH` to select a protected local database and keep that runtime file untracked. This local prototype does not provide cloud identity, deployment-grade session hardening, or a production-grade sandbox.
- Docker-dependent integration still needs to run on a host with Docker Desktop CLI and a reachable Linux engine. No Docker test result is fabricated.
- The repository's existing dataset report test rewrites documented generated paths in `docs/phases/PHASE_16_DATASET_REPORT.md`; the updated paths match current repository locations and were retained.

## Files

Created: `backend/src/codeguard/access.py`, `auth.py`, `auth_bootstrap.py`, `events.py`, `health.py`, `pipeline.py`, `frontend/phase20_ui.py`, `docs/phases/PHASE_20_REPORT.md`, `docs/phases/PHASE_20_PLAN.md`, and Phase 20 unit tests for extraction, auth/RBAC, health, pipeline, and AppTest.

Modified: `.env.example`, `.gitignore`, `README.md`, `backend/src/codeguard/input_processing.py`, `backend/src/codeguard/storage.py`, `docs/architecture/ARCHITECTURE.md`, `docs/phases/PROJECT_PROGRESS.md`, `frontend/app.py`, `tests/unit/test_storage.py`, and the generated-path references in `docs/phases/PHASE_16_DATASET_REPORT.md`.
