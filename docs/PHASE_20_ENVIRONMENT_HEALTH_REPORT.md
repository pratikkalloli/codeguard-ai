# Phase 20 Environment Health Audit and Repair

Date: 2026-09-29

## Pre-repair diagnosis (recorded before creating a clean environment)

- Repository: `C:\Codeguard_AI`. The existing working tree contains Phase 20 implementation changes and generated Phase 16 report path updates from the preceding task. Those changes were retained.
- Preserved data at audit start: `data/codeguard.db` exists (110,592 bytes); `models/phase17/pass_rate_predictor.joblib` exists (2,415,099 bytes). No destructive operation has been performed on either.
- Existing `.venv`: CPython **3.11.9**, Windows **AMD64**, 64-bit, base interpreter `C:\Users\Pratik Kalloli\AppData\Local\Programs\Python\Python311\python.exe`.
- Python 3.12 was not registered by `py -0p` and was not found in the checked standard Python installation directories. Python 3.11 satisfies the project declaration `requires-python = ">=3.10"`.
- Project dependencies are declared in `pyproject.toml`; `requirements.txt` delegates to `-e .` and `requirements-dev.txt` adds pytest. Package discovery is configured for `backend/src`.
- Installed versions in the old environment included NumPy 2.4.6, pandas 3.0.6, PyArrow 25.0.1, scikit-learn 1.9.1, SciPy 1.17.1, joblib 1.6.0, Streamlit 1.64.0, matplotlib 3.11.2, pytest 9.1.1, and pip 26.2.1.
- Confirmed corruption: pandas' installed `WHEEL` metadata says `cp314-cp314-win_amd64`, while the interpreter is `cp311`; importing pandas fails with `ModuleNotFoundError: pandas._libs.pandas_parser`. This is a cross-Python-version compiled wheel in the venv, not an application logic defect.
- Compiled import probes: NumPy 2.4.6, PyArrow 25.0.1 (`pyarrow.lib`), scikit-learn 1.9.1 (`Pipeline`, `FeatureUnion`), SciPy 1.17.1 (`scipy.linalg`), and joblib 1.6.0 succeeded. pandas and pandas native imports failed. Streamlit 1.64.0 imported.
- `pip check` reports 11 distributions unsupported on this platform, including pandas, matplotlib and several Streamlit dependencies. The old dependency set is inconsistent even though some packages import.
- Baseline full pytest collection was interrupted by two errors: matplotlib could not import `_c_internal_utils` in `tests/unit/test_ml_pipeline.py`, and pandas could not import `pandas._libs.pandas_parser` in `tests/unit/test_phase17_public_data.py`. Pytest stopped at collection; no complete baseline test count is available.
- No Python installation override variables (`PIP*`/`PYTHON*`) were present in the process environment at the time checked. No Python 3.12 interpreter was available. The root cause indicates the current `.venv` has compiled artifacts copied/installed for a different Python ABI; the old environment will be retained until a clean replacement passes verification.

## Repair and final verification

### Root cause and environment decision

- The old `.venv` was **not healthy**. It is CPython 3.11.9 (`cp311`) but contains CPython 3.14 (`cp314`) Windows wheels. pandas and matplotlib both have `cp314-cp314-win_amd64` wheel tags in this Python 3.11 environment; contourpy also reports `Requires-Python >=3.12`. This explains the missing pandas parser and matplotlib `_c_internal_utils` native modules and the `pip check` platform failures. This was a mixed/corrupted environment, not a CodeGuard evaluation-logic issue.
- Python 3.12 was not installed/registered in this host. Python 3.11.9 is installed, 64-bit AMD64, meets `pyproject.toml`'s `>=3.10` requirement, and has compatible wheels for the declared dependencies.
- Created and verified a new `.venv_clean` from the installed Python 3.11.9 base. Installed from `requirements-dev.txt` with `--only-binary=:all:`. The clean distribution wheels are `cp311` where native wheels are required. `pip check` reports no broken requirements. The old `.venv` was retained; it was not deleted or modified as part of the repair. `.venv_clean/` is ignored by Git.
- No project dependency pins were randomly changed. The existing setuptools package configuration and dependency declarations were used. The repaired Streamlit entry point runs from `.venv_clean`.

### Final versions and native checks

Verified versions in `.venv_clean`:

| Component | Version |
| --- | --- |
| Python | 3.11.9, 64-bit AMD64 |
| Streamlit | 1.64.0 |
| pandas | 3.0.6 |
| PyArrow | 25.0.1 |
| NumPy | 2.4.6 |
| scikit-learn | 1.9.1 |
| SciPy | 1.17.1 |
| joblib | 1.6.0 |
| matplotlib | 3.11.2 |
| pytest | 9.1.1 |

All native checks passed: `pandas._libs`, `pyarrow.lib`, scikit-learn `Pipeline`/`FeatureUnion`, and `scipy.linalg`. A pandas DataFrame converted to a PyArrow table successfully; SciPy linear algebra produced the expected result. Streamlit imported at 1.64.0.

### Code, model, database, and authentication

- Compiled and imported all **39** discoverable `codeguard` modules; **0 import failures**. `python -m compileall -q backend/src frontend` passed.
- The existing Phase 17 artifact is present at `models/phase17/pass_rate_predictor.joblib` (2,415,099 bytes). It loaded with the clean scikit-learn environment and produced an actual prediction: status `predicted`, model `linear_svr_c0_1`, target `pass_rate`. `apply_ml_advisories` also ran. The numeric prediction is a dataset-domain advisory, not a general correctness result. The model was not replaced or retrained.
- The production SQLite database passed `PRAGMA quick_check`. It contains the existing account/evaluation/report/log tables and, at inspection, 1 DEVELOPER and 1 USER account, 5 evaluations, 22 application events, and 2 reports. The two stored password encodings use the `scrypt` format; password hashes and usernames were not printed in this audit. The database and model were not intentionally modified.
- Authentication, registration, login, role enforcement, and ownership isolation tests passed using disposable test accounts/databases. A DEVELOPER account exists in the production database, but its login password was not provided, so that specific existing credential could not be authenticated in this audit. No password or hash was read out or disclosed.
- The actual user evaluation flow was exercised with a temporary account and disposable database, without mocks: code extraction found one block; AST status was `valid`; restricted Docker execution returned `Passed`; the `square(4)` function test returned `16` and passed; four real performance measurements were saved; evidence retrieval was available; claim statuses were `Insufficient evidence` and `Supported`; the Phase 17 prediction was available; and the unified report plus 12 events were persisted. The temporary database was removed when that check ended. This run did not write to the production database.

### Streamlit, Docker, and tests

- `frontend/app.py` passed Streamlit AppTest with **0 exceptions**. All Phase 20 user/developer navigation tests passed. A developer Logs AppTest rendered a non-empty event table, the ML page made a real inference, and the Evidence page rendered source/retrieval tables; all had **0 exceptions**.
- Started the actual app using `.venv_clean` at `http://127.0.0.1:8501`: HTTP **200**, Streamlit health endpoint `/_stcore/health` returned `ok`, and the fresh startup log had no traceback.
- Docker was found through the existing Docker Desktop install-location fallback even though `docker` is not on `PATH`. CLI: **29.8.0**; engine: reachable **Linux**; Compose: **5.5.1**; harmless `python:3.12-slim` container: **Python 3.12.14**. Five dedicated Docker tests passed. The full suite was rerun with `CODEGUARD_DOCKER_INTEGRATION=1`: **150 passed, 0 failed, 0 skipped**, including Docker integration and Phase 18 container demonstrations. Existing network, filesystem, user, capability, privilege, memory, CPU, PID, timeout, and output restrictions were not weakened.
- Current-environment baseline before repair: pytest collection stopped with two errors (pandas parser missing and matplotlib `_c_internal_utils` missing); no complete baseline test count was available. The clean-environment full test suite passed **150/150**.
- `python -m pip check`: passed. `python -m compileall -q backend/src frontend`: passed. No Docker checks were skipped in the final enabled run.

### Project-integrity and security review

- The `.venv_clean` environment, SQLite database, Streamlit logs, caches, raw datasets, and model artifacts are ignored or remain outside tracked source. No `.env` file exists at the repository root; `.env.example` contains configuration names/placeholders only. No database, runtime log, or private-key file is tracked.
- A text scan of 6,733 project/runtime files found no stale `C:\codex` references. Three high-confidence token-pattern matches were confined to ignored downloaded `narwhals` and `packaging` license/source files and were false positives; there were no matches in tracked project code, tests, or configuration. Match values were not displayed.
- Git status was reviewed; the pre-existing Phase 20 implementation changes and this report are visible as expected. No automatic commit was made. Existing Phase 16 test-generated documentation path updates were retained. No Phase 17 model or dataset contents were changed.

### Fresh-terminal commands

Use the repaired environment already created in this checkout:

```powershell
Set-Location C:\Codeguard_AI
.\.venv_clean\Scripts\Activate.ps1
python -m pip check
python -m streamlit run frontend/app.py
```

To rerun all tests, including Docker integration and Phase 18 container cases:

```powershell
$env:CODEGUARD_DOCKER_INTEGRATION = "1"
python -m pytest -q
```

To compile and check dependencies:

```powershell
python -m compileall -q backend/src frontend
python -m pip check
```

### Remaining issue

- The existing production DEVELOPER password was not supplied, so that particular stored account's password could not be tested. The authentication and developer page flows were verified with disposable test credentials; no secret was requested, printed, or modified.
