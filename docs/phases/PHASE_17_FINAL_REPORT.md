# Phase 17 — Public dataset ML training and integration

**Run date:** 2026-09-27  
**Status:** Completed as a bounded public-data auxiliary experiment. The CodeGuard claim-verification dataset remains **NOT READY** for production/gold training: the Phase 16 pool still consists of proposed labels, with zero human-reviewed, adjudicated, or gold-labelled records.

## 1. Objective

Add a reproducible ML signal trained on a large public Python dataset while keeping it separate from the app's deterministic checks, Python documentation evidence verifier, and human review labels. Do not claim that a benchmark score establishes factual correctness or general code safety.

## 2. Dataset discovery and selection

Seven candidates were compared in [dataset research](../research/PHASE_17_DATASET_RESEARCH.md). NVIDIA OpenCodeReasoning-2 was selected because it has a large Python corpus and an execution-related numeric outcome field. It does not contain CodeGuard's evidence-grounded labels. The [selection record](../research/PHASE_17_DATASET_SELECTION.md) explains the choice and limits.

The source dataset card describes about 1,398,166 Python examples across 34,125 questions. This bounded run downloaded the first three contiguous shards at pinned revision `eadf535931451525f3e5621d0f960c240bc62fd9` (60,000 rows). The original Parquet files, per-file SHA-256 values, download time, source URL, revision, license notes, and aggregate checksum are preserved in `data/raw/phase17/`.

The NVIDIA card identifies the collection as CC BY 4.0 and warns that upstream materials have their own terms. All 60,000 downloaded rows reported `apache-2.0` in their row-level license field. That field was retained and filtered against an explicit license allow-list. This technical check preserves attribution; upstream rights still apply.

## 3. Fields and label definition

The selected release has solution code, question IDs, source, upstream dataset, difficulty, per-row license, source-generated `judgement`, QwQ critique, R1 response, and `pass_rate`. The question field in the Python shards is the placeholder `-`, not the problem statement.

The model predicts `pass_rate` in [0, 1] as a regression task. The source describes this as a test pass rate and uses -1 where validation was unavailable. Generated critique and `right`/`wrong` judgement are not features or targets. No public record was mapped to Supported, Contradicted, or Insufficient Evidence; no human review or gold label was fabricated.

## 4. Preprocessing and dataset quality

The deterministic preprocessor reads Parquet in bounded batches, preserves original code and provenance, parses only numeric pass rates, extracts static code features without executing code, removes exact duplicate records, and records every filtering decision. With a fixed code normalization and seed:

- Raw rows: 60,000.
- Rows with valid pass rate before code/duplicate filtering: 56,310.
- Missing/invalid pass-rate rows excluded: 3,688.
- Rows without code excluded: 2.
- Exact duplicate rows excluded: 2,909 (4.85% of downloaded rows).
- Final usable rows: **53,401**.
- Every retained row is Python; all downloaded rows have the row-level `apache-2.0` value.
- Parsed syntax failures: 0. Code was not executed; 10 retained rows contain a static mention of selected dangerous APIs, which is not a safety determination.
- Average solution length: 1,002.8 characters, 131.6 whitespace-delimited tokens, and 37.5 lines.
- Near-duplicate rate was not estimated. Exact normalized-code hashes and question IDs are held together across splits.

See `reports/phase17/phase17_dataset_statistics.json`, `docs/research/phase17/phase17_dataset_statistics.md`, `reports/phase17/phase17_dataset_sample.json`, and `reports/phase17/phase17_preprocessing_report.json` for distributions and row-level sample examples.

## 5. Leakage controls and split

All downloaded examples came from the source's training split. A deterministic seed of 1701 was used for a grouped 70/15/15 partition. Connected components link any rows that share a `question_id` or exact normalized-code SHA-256. The resulting sizes are:

| Split | Rows | Share |
|---|---:|---:|
| Train | 37,365 | 70.0% |
| Validation | 8,144 | 15.3% |
| Test | 7,892 | 14.8% |

Question-ID overlap and exact-code-hash overlap are both zero across every split pair. Model selection used validation MAE; the test set was used only for final reporting. Semantic near-duplicate matching was not run. The public corpus may overlap model pretraining data, and the held-out split is not an external benchmark.

## 6. Feature engineering and models

Inputs are solution-code word TF-IDF (unigrams/bigrams, max 50,000 features), deterministic AST/code-shape values (syntax validity, AST nodes, functions, classes, imports, loops, branches, exception blocks, comprehensions, code length, and static API mention counts), plus source, upstream dataset, and difficulty categories.

`pass_rate`, generated judgement, QwQ critique, R1 rationale, and the placeholder question field are excluded from features. The linear models use code and metadata; the ExtraTrees baseline uses numeric code-shape features.

Four regressors were compared:

- Mean DummyRegressor baseline.
- Ridge regression (`alpha=1.0`).
- LinearSVR (`C=0.1`, `max_iter=5000`), selected by lowest validation MAE.
- ExtraTreesRegressor (120 trees, `min_samples_leaf=3`, `max_features=0.8`).

The model, fitted preprocessing pipeline, feature configuration, target definition, seed, hyperparameters, dataset revision, and metrics are under `models/phase17/`.

## 7. Evaluation

The selected LinearSVR on the untouched test split:

- **MAE:** 0.2015 pass-rate units.
- **RMSE:** 0.3238.
- **R²:** 0.2066.
- **Spearman rho:** 0.4888.
- **ROC-AUC:** 0.7755 and **PR-AUC:** 0.8985 after deriving a binary reporting target at `pass_rate >= 0.5`.
- Derived-threshold accuracy: **0.8060**; macro F1: **0.6273**; weighted F1: **0.7639**.
- Derived-threshold confusion matrix, labels `[pass_rate < 0.5, pass_rate >= 0.5]`: `[[448, 1410], [121, 5913]]`.

The thresholded metrics are a secondary view of the regression output, not an original dataset label. The held-out target is imbalanced (6,034/7,892 rows have pass_rate >= 0.5), so accuracy and weighted F1 alone overstate performance. The dummy baseline has test accuracy 0.7646, macro F1 0.4333, and MAE 0.2993. Ridge has MAE 0.2350; ExtraTrees has MAE 0.2781. The model improves over the mean baseline, but its R² and macro F1 show substantial error remains.

Figures: `reports/phase17/phase17_confusion_matrix.png` (derived threshold) and `reports/phase17/phase17_metrics.png` (predicted vs. observed continuous pass rate). Full split/model metrics are in `reports/phase17/phase17_model_results.json`.

## 8. Comparison with CodeGuard components

`docs/research/phase17/phase17_system_comparison.md` compares the model against Python AST syntax validity on the same derived pass/fail target and a syntax-plus-ML proxy. All 7,892 test examples parse syntactically, so syntax validity alone predicts the majority class and achieves 0.7646 accuracy. The combined proxy matches ML because all test code is syntactically valid.

This is only a benchmark-target proxy comparison. The dataset does not provide explanation evidence for the app's official Python documentation verifier, and the source's `pass_rate` was not independently rerun. Docker was unavailable; no submitted dataset code was executed in this workspace. Runtime failures and evidence retrieval cannot be compared on this corpus. The existing deterministic verifier, explanation evidence verifier, and CodeGuard report remain independent outputs; the application does not combine them into one verdict.

## 9. Application integration

The app has an **ML Reliability Analysis** page that displays the auxiliary predicted pass rate, selected model/revision, held-out metrics, deterministic static validation, and separate explanation-evidence results. Regression confidence is explicitly shown as uncalibrated/unavailable. The inference API is `backend/src/codeguard/ml/public_reliability.py`; it does not execute code and warns that the model is domain-specific.

This model does not replace or alter the existing synthetic claim-verifier model and does not assign review decisions or gold labels. The existing Phase 16 candidate pool remains 389; human reviewed 0, adjudicated 0, gold labelled 0.

## 10. Limitations and intended use

- OpenCodeReasoning-2 responses and critiques are model-generated; this is not human adjudication.
- The measured target is source-provided execution pass rate for competitive-programming solutions, not general code correctness, factuality, security, or explanation quality.
- The dataset split's question text is blank; the model cannot condition on problem semantics.
- The three-shard prefix is a bounded sample of the full corpus, and the held-out sample is not an external source.
- Exact duplicates and question IDs are grouped, but semantic near duplicates and pretraining contamination are not measured.
- Upstream evaluation/pass-rate quality may vary. A pass-rate estimate does not verify the code at runtime.
- No CodeGuard labels, human review, or gold-label counts were created.

Intended use is a clearly marked auxiliary signal alongside current independent verifiers. It is not intended as a standalone pass/fail decision or a factual correctness proof.

## 11. Reproduction

Using the project Python environment with `requirements.txt` installed:

```powershell
python scripts/download/download_phase17_dataset.py
python scripts/training/train_phase17.py
python -m pytest
python -m compileall -q frontend backend scripts tests
python -m pip check
```

The training script repeats preprocessing, grouped split creation, baseline fitting, validation selection, test evaluation, model saving, plots, and reports. The downloader pins the dataset revision and verifies per-shard SHA-256 values. The downloaded original Parquet files are retained under `data/raw/phase17/`.

## 12. Verification and status

- Unit suite: **105 tests run, 100 passed, 5 Docker-gated tests skipped** (Docker integration flag is off; Docker is unavailable in the current environment).
- Streamlit 1.64.0 AppTest: 11 tabs rendered without exceptions; submitting the auxiliary analysis form produced an ML prediction without errors.
- Scikit-learn, SciPy, PyArrow, NumPy, pandas, joblib, Matplotlib, and Streamlit are declared/available in the runtime used for this run.
- Docker: **unavailable**, not verified.
- ML training/inference: **verified** on the recorded public-data split.

The public-data auxiliary experiment is complete. The CodeGuard human-labelled claim-verification gate remains **NOT READY** until real independent reviews and adjudicated gold data exist.
