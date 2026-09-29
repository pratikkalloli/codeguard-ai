# CodeGuard AI — System Architecture

## Request and evaluation flow

```text
Manual paste or optional OpenAI Responses API
                    │
                    ▼
        Frontend workflow and display
                    │
         ┌──────────┴───────────┐
         ▼                      ▼
 Python fence extraction    Explanation sentences
         │                      │
         ▼                      ▼
 AST validation         Local TF-IDF retrieval
         │                      │
         ▼                      ▼
 Restricted Docker     Proposition-specific evidence rules
 execution and tests              │
         │                 ┌──────┴──────────┐
         │                 ▼                 ▼
         │          Retain rule result   ML advisory for
         │                              insufficient evidence
         └──────────────────┬───────────────┘
                            ▼
                    SQLite evaluation records
                                  │
                    Dashboard / comparison / JSON report
```

## Project modules

- `frontend/app.py` is the Streamlit entry point. It presents the 11 user-facing views and coordinates workflows.
- `backend/src/codeguard/input_processing.py` separates fenced Python code from prose; `validation.py` performs syntax and selected static-risk checks.
- `backend/src/codeguard/execution.py` invokes the restricted Docker runner. There is no host-execution fallback.
- `backend/src/codeguard/ingestion.py`, `embeddings.py`, and `retrieval.py` validate, index, and search the curated documentation corpus.
- `backend/src/codeguard/claims.py` extracts conservative claim candidates; `claim_verification.py` applies narrow proposition rules after evidence retrieval.
- `backend/src/codeguard/providers/` contains provider-neutral types and the optional OpenAI Responses API adapter.
- `backend/src/codeguard/storage.py` manages SQLite records and additive migrations; `comparison.py` groups evaluations; `reports.py` creates descriptive JSON reports.
- `backend/src/codeguard/ml/` contains dataset preparation, training, model loading, inference, review, and Phase 17 public-reliability code.
- `scripts/` contains repeatable Phase 17 download, preprocessing, and training commands.
- `data/`, `models/`, and `reports/` hold source/derived data, model artifacts, and generated machine-readable results respectively.

## Phase 20 application shell, identity, and ownership

`frontend/app.py` launches the Phase 20 UI in `frontend/phase20_ui.py`. The entry screen separates account creation, normal sign-in, and developer sign-in. After login, the navigation is selected from the stored role: users receive Home, New Evaluation, My Evaluations, Compare, and Profile; developers receive the engineering console (Overview, Evaluations, Logs, System Health, Docker, ML, Evidence, Datasets, Users, and Settings).

The Streamlit entry points derive the checkout root from their own file location and add its `backend/src` directory to Python's import path before importing the backend package. The package is also configured for editable installation in `pyproject.toml`; run `python -m pip install -e .` from the repository root when setting up the environment. This supports launching Streamlit from a different current directory and avoids relying on a machine-specific path.

The backend identity and authorization rules are in `backend/src/codeguard/auth.py` and `access.py`. Passwords are encoded with salted `hashlib.scrypt`; retrieval functions return account fields without the password hash. Developer account creation is a one-time local CLI operation (`python -m codeguard.auth_bootstrap <username>`), with `getpass` prompts and no credential in process arguments. A developer role cannot be selected during public registration.

SQLite initialization creates `users`, `application_logs`, and `evaluation_reports` additively and adds `owner_user_id`/`evaluation_name` columns to existing evaluation sessions if needed. Existing rows are retained with a null owner and can only be listed by developers. User history and report reads apply the owner ID in the SQL query; developer services re-read the account role before accessing cross-user records. No account-delete operation can orphan an evaluation.

## Authenticated evaluation pipeline

`backend/src/codeguard/pipeline.py` runs the existing extraction, AST/risk validation, restricted Docker execution, optional function tests, timing capture, explanation verification and curated evidence retrieval, Phase 17 inference, and Phase 19 report builder. Each result remains separate. The pipeline persists a unified report and structured events under the evaluation ID. Progress callbacks move stages to complete only when the underlying call returned; unavailable Docker, missing tests, missing code, and missing ML artifacts remain unavailable/not-run outcomes.

Code extraction in `input_processing.py` accepts Python-labelled fences, generic fences that parse as Python, and AST-valid unfenced code segments separated from prose. Invalid or non-Python blocks remain in the explanation text. Multiple code blocks retain their order. If none are found, the UI uses an actionable instruction instead of implying that the user must have written fences.

## Structured events and developer observability

`events.py` writes event, UTC timestamp, level, evaluation ID, actor, component, duration, status, error type, and bounded redacted details to SQLite. It removes password/secret/API-key/token-shaped fields and never stores the complete prompt or response in event details. The event table keeps at most 5,000 rows. Developer access is required by `list_events` and the UI. The existing evaluation records continue to retain full user input so that users can reopen their own reports; that data is private local application state.

`health.py` probes the SQLite file, Docker CLI/Linux engine/local image, actual Phase 17 inference, evidence retrieval, required directories, configuration presence, and running-app context. The harmless optional Docker probe uses no network, a read-only root, UID/GID 65534:65534, 128 MiB memory, 0.5 CPU, and 32 processes. The Docker dashboard identifies the execution configuration as a local development boundary, not production isolation.

The ML, evidence, and dataset screens read existing model artifacts/configuration, experiment reports, the checked-in official-document corpus and retrieval, dataset cards, and the Phase 16 review queue. They do not synthesize users or metric values, promote proposed labels to gold, or train a model. Existing Phase 16 human-review/adjudication actions remain separate and developer-only.

## Configuration and limits

`CODEGUARD_DATABASE_PATH` optionally selects the local SQLite file. `CODEGUARD_ENV` and `LOG_LEVEL` are informational configuration shown in the developer console. `OPENAI_API_KEY` and `CODEGUARD_OPENAI_MODEL` retain the optional Responses API integration; `.env` loading is not automatic. The CLI bootstrap needs no environment password variable.

This is local session-based authentication, not enterprise identity. There is no MFA, email verification, password reset, or account deletion. Anyone with direct access to the host, application process, or local SQLite file is outside the UI's authorization boundary. Docker and the host kernel can contain vulnerabilities. The system continues to support Python only, and ML/evidence research limitations remain unchanged.

## Documentation corpus and retrieval

The checked-in corpus at `backend/src/codeguard/corpus/python_docs.json` contains 12 short curated paraphrase chunks. Its source metadata points to official Python documentation pages. The corpus loader refuses URLs outside `docs.python.org`.

Ingestion cleans whitespace, splits on sentence boundaries, enforces a maximum chunk size, and keeps metadata and explicit fact keys. TF-IDF uses term frequency, inverse document frequency, L2 normalization, and cosine similarity, with light token normalization for plurals. The generated index is stored in `data/python_docs_tfidf.json`, which is ignored by Git. The index rebuilds when its format or source-corpus hash changes.

Verification is deterministic and deliberately narrow. Similarity alone cannot mark a claim Supported or Contradicted. When evidence is missing or a proposition is outside the recognized rules, the result remains **Insufficient evidence**.

## Data model

SQLite retains evaluation sessions, prompts, responses, extracted code blocks, test results, performance measurements, and explanation claims. Claim rows keep rule results, ML advisory results, confidence, verification method, evidence provenance, and review-required state separate.

## Security and privacy boundaries

- Submitted code runs only through Docker with networking disabled, no host mounts, a read-only root, non-root user, resource limits, and timeouts. This is not production isolation.
- The optional provider reads `OPENAI_API_KEY` from the environment and sends a coding question only when the user selects that provider. API usage may be billed.
- SQLite can contain prompts and full responses. Keep local database files private and out of version control.
- Retrieval evidence and model predictions have documented limits; neither guarantees that all claims are extracted or correctly verified.
