# Phase 19 — Unified ML and verification report integration

Run date: 2026-09-27  
Status: implemented and verified

## Changes

- Extended the existing report builder in `src/codeguard/reports.py` to schema version 2. It accepts an optional Phase 17 inference result and emits the first-class `ml_reliability` object both at the report root and in the independent `signals` map.
- Added eight explicit signal sections: `static_ast_analysis`, `docker_execution`, `function_tests`, `performance_measurement`, `explanation_claims`, `evidence_retrieval`, `claim_verification`, and `ml_reliability`. Existing report fields remain available for consumers. The report still has no combined reliability score.
- The Streamlit Reliability Report page now runs Phase 17 inference for the first extracted code block, displays the result and metadata in the main report view, and includes it in the downloadable report JSON. Multiple code blocks are not silently combined; the displayed block index is explicit.
- Refreshed the Phase 18 machine-readable reports so their `final_output` uses the unified report builder schema.
- Added safe inference failure handling for malformed input, missing/inaccessible artifacts, unsupported artifacts, load errors, and prediction errors. The report remains usable and records an unavailable ML signal if inference fails.

## Report schema

The ML field follows this stable structure (values below illustrate field types; live inference supplies the actual prediction):

```json
{
  "ml_reliability": {
    "available": true,
    "model": "linear_svr_c0_1",
    "model_version": "eadf535931451525f3e5621d0f960c240bc62fd9",
    "task": "pass_rate_prediction",
    "task_description": "Predict source-recorded execution test pass rate for competitive-programming Python solutions.",
    "dataset_name": "NVIDIA OpenCodeReasoning-2 (Python split, bounded three-shard prefix)",
    "dataset_size": {
      "downloaded_records": 60000,
      "usable_records": 53401,
      "reported_full_python_records": 1398166
    },
    "prediction": 0.5387,
    "prediction_range": [0.0, 1.0],
    "confidence": null
  }
}
```

The model is a regression estimate of **source-recorded programming pass-rate reliability**. It does not estimate general code correctness, security, explanation/factual correctness, or the CodeGuard labels Supported/Contradicted/Insufficient Evidence. It is not a human-reviewed or gold label. `confidence` is `null` because the current model has no calibrated confidence interval or uncertainty estimate. The model parameters, seed, feature fields, feature summary, and limitations are also included in the live output.

The dataset figures come from the existing Phase 17 download and preprocessing metadata: 60,000 downloaded rows, 53,401 usable rows, and a reported full Python split of 1,398,166 records. The prediction is computed on demand by the existing Phase 17 model; no prediction value is hard-coded.

## Signal separation and UI

The report does not collapse signals into one unsupported score. Static AST findings, recorded Docker execution (when available), per-function Docker test results, process/container measurements, extracted explanation claims, retrieved evidence, rule-based verification, and the Phase 17 prediction remain separate.

The main Reliability Report view displays **Predicted execution pass-rate reliability** as a unit-interval number with explanatory help text, model/version, dataset name/size, task, confidence note, and code-block index. It does not call the number a correctness percentage. The JSON download contains the same structured `ml_reliability` signal.

The app does not persist a separate isolated-run status in its current evaluation database. In reports opened from normal app history, `docker_execution` therefore says `not_recorded`; function-test records remain explicitly identified as restricted Docker runs. Phase 18 machine reports pass the actual isolated-run result directly to the builder.

## Failure behavior

When inference cannot run, the report emits `available: false`, `prediction: null`, a reason, declared range, and the no-confidence note. AST, Docker/test, performance, evidence, and claim-verification sections are still generated. Malformed or non-finite predictor output is never presented as a valid prediction.

## Verification

- Full suite with `CODEGUARD_DOCKER_INTEGRATION=1`: **118 tests passed, 0 failed, 0 skipped**. This includes the existing Docker integration tests, all five Phase 18 end-to-end cases, and eight Phase 19 report/inference regression tests.
- Phase 18 demos rerun against the unified report: **5/5 expected signals observed**; all eight named report signal sections were present in each report.
- Report tests verify live-value inclusion, model/dataset metadata, numeric range, graceful ML failure, unchanged AST and Docker data, unchanged evidence/verification results, and absence of an overall reliability score.
- `python -m compileall -q app.py src tests`: passed.
- `python -m pip check`: no broken requirements.
- Streamlit AppTest: **0 app exceptions**.
- Docker restrictions were not changed. No new dataset/model was added and no training was run.
