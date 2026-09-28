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
