# Phase 18 — End-to-end demonstration validation

Run date: 2026-09-27  
Machine-readable outputs: [`reports/phase18/summary.json`](../../reports/phase18/summary.json) and one JSON record per case in the same directory.  
Reproduction: with Docker Desktop running, set `CODEGUARD_DOCKER_INTEGRATION=1` and run `python -m pytest`; to regenerate exports, run `python -c "from codeguard.phase18_demo import run_phase18_demonstrations; run_phase18_demonstrations('reports/phase18')"`.

## What was exercised

Each deterministic case used the existing functions in order: question and response construction, fenced-code extraction, storage in a temporary SQLite database, AST validation, restricted Docker execution, function tests in a fresh restricted container, persisted execution/test measurements, explanation claim extraction, local corpus retrieval, evidence-backed claim verification and existing ML advisories, Phase 17 pass-rate inference, and the existing reliability report builder. The temporary database was discarded after its persisted artifacts were read into the report. The normal app history was not modified.

The report builder now places the Phase 17 result in its first-class `ml_reliability` section. Each exported `final_output` is the unified report, with the ML signal alongside the independent AST, Docker, function-test, performance, evidence, and claim-verification signals.

| Case | AST | Docker execution | Function test | Claim verification | Phase 17 estimate |
|---|---|---|---|---|---:|
| Correct solution | `valid` | Passed | passed (6 = 6) | Supported | 0.538713 |
| Incorrect code | `valid` | Passed | failed (expected 6, returned 3) | Supported | 0.531514 |
| Explanation error | `valid` | Passed | passed (6 = 6) | Contradicted | 0.538713 |
| Performance | `valid` | Passed | passed (3500 = 3500) | Supported | 0.594713 |
| Risk | `valid_with_risks` | Passed | passed (9 = 9) | Supported | 0.559666 |

Every prediction returned status `predicted` from `linear_svr_c0_1`. It is an estimate of source-recorded competitive-programming pass rate, not a correctness verdict, confidence interval, or evidence source.

## Case details

### 1. Correct solution

- **Question:** Return the sum of the integers in a list. State whether Python lists are mutable.
- **Input response:** explanation `Lists are mutable.` and `def solution(values): return sum(values)`.
- **AST:** syntax valid; no flagged patterns.
- **Docker:** `Passed`; output `6`.
- **Function test:** `[1, 2, 3]` expected `6`, actual `6`, passed.
- **Performance:** child-process wall time 0.016471 s; cgroup peak 31,240,192 bytes. These include runtime/sandbox costs.
- **Claim/evidence:** `Lists are mutable.` → **Supported**. Retrieved evidence from [The Python Tutorial: Data Structures](https://docs.python.org/3/tutorial/datastructures.html): “Lists are mutable data structures.”
- **Phase 17 estimate:** 0.5387129175.
- **Final report:** test summary 1/1 passed; the unified report includes a separate `ml_reliability` section and no overall reliability score.

### 2. Syntactically valid but incorrect code

- **Question:** Return the sum of the integers in a list.
- **Input response:** `def solution(values): return max(values)`; explanation `Lists are mutable.`
- **AST:** `valid`.
- **Docker:** `Passed`; execution completed and printed `3` for `[1, 2, 3]`.
- **Function test:** expected `6`, actual `3`, failed. This distinguishes successful execution from solving the stated problem.
- **Performance:** child-process wall time 0.011292 s; cgroup peak 17,272,832 bytes.
- **Claim/evidence:** `Lists are mutable.` → **Supported**, with the same official tutorial evidence as the correct case.
- **Phase 17 estimate:** 0.5315139454.
- **Final report:** test summary 0/1 passed; the unified report retains the failed test result and separate ML signal.

### 3. Explanation error

- **Question:** Return the sum of the integers in a list and explain list mutability.
- **Input response:** correct `sum` implementation; explanation `Lists are immutable.`
- **AST:** `valid`.
- **Docker:** `Passed`; output `6`.
- **Function test:** expected `6`, actual `6`, passed.
- **Performance:** child-process wall time 0.068188 s; cgroup peak 17,240,064 bytes.
- **Claim/evidence:** `Lists are immutable.` → **Contradicted**. The retrieved Python tutorial passage says lists are mutable and describes methods that modify an existing list.
- **Phase 17 estimate:** 0.5387129175.
- **Final report:** test summary 1/1 passed; the claim, retrieved evidence, and ML signal remain separate report sections.

### 4. Deliberately inefficient implementation

- **Question:** Return the sum of a non-empty list of integers.
- **Input response:** a nested-loop implementation repeats each addition once per list element, then divides by the list length; explanation `Lists are mutable.`
- **AST:** `valid`.
- **Docker:** `Passed`; output `3500` for 3,500 ones.
- **Function test:** expected `3500`, actual `3500`, passed.
- **Performance:** child-process wall time 0.495477 s; cgroup peak 17,555,456 bytes. This is the observed measurement for this input and environment, not a calibrated benchmark or general complexity threshold.
- **Claim/evidence:** `Lists are mutable.` → **Supported**, with official tutorial evidence.
- **Phase 17 estimate:** 0.5947133178.
- **Final report:** includes runtime, memory, tests, and ML prediction separately; it does not convert them to a performance grade.

### 5. Static risk finding

- **Question:** Write a short marker to a temporary file and return the number of characters written.
- **Input response:** calls `open(..., 'w')` on `/tmp/codeguard-phase18-marker.txt`; explanation `Lists are mutable.`
- **AST:** `valid_with_risks`; the existing `risky_call` rule flags `open` for file access.
- **Docker:** `Passed`; output `9`. The file is confined to the container's ephemeral `/tmp` tmpfs; there are no host volume mounts.
- **Function test:** no arguments, expected `9`, actual `9`, passed.
- **Performance:** child-process wall time 0.016703 s; cgroup peak 16,723,968 bytes.
- **Claim/evidence:** `Lists are mutable.` → **Supported**, with official tutorial evidence.
- **Phase 17 estimate:** 0.5596664115.
- **Final report:** retains the static warning while separately recording successful execution, tests, and the ML signal. The static analyzer warns; it does not claim to block the operation.

## Limits and interpretation

- The 5 cases produced all their declared expected signals. A Docker status of `Passed` means the snippet completed; the incorrect-code case demonstrates why the independent function test is necessary.
- CodeGuard reports static findings, test outcomes, measurements, retrieved evidence, and the auxiliary ML estimate separately. It does not produce one total reliability score.
- The Phase 17 prediction is a first-class `ml_reliability` object in report schema version 2, with model/dataset metadata and an explicit unavailable state if inference did not succeed.
- Performance values contain interpreter startup and sandbox/container overhead. The deliberately quadratic case produced an observable measurement, but a single run is not a benchmark comparison.
- The risky case is a bounded benign write into container `/tmp`; no network access, host paths, or user-provided arbitrary attack payloads were used.
- No model or dataset was added or changed. No Docker security restriction was changed.
