# Phase 17 model card

- Purpose: auxiliary regression estimate of benchmark execution pass rate for competitive-programming Python solutions.
- Dataset: NVIDIA OpenCodeReasoning-2 Python split, pinned revision `eadf535931451525f3e5621d0f960c240bc62fd9`; three contiguous shards, row-level license filter.
- Task/target: regression to recorded `pass_rate` in [0, 1]. This is not a CodeGuard claim label or a human-reviewed correctness judgment.
- Model: linear_svr_c0_1; alternatives: mean dummy, Ridge, LinearSVR, and ExtraTrees numeric baseline.
- Features: solution-code word TF-IDF, deterministic AST/code-shape features, source/upstream dataset/difficulty metadata. No critique, generated judgement, pass_rate input, or R1 rationale.
- Split: fixed seed 1701; grouped 70/15/15 by connected components of question ID and normalized exact code hash.
- Test metrics: `{"accuracy": 0.8060060821084643, "confusion_matrix_labels_0_1": [[448, 1410], [121, 5913]], "derived_binary_target": "pass_rate >= 0.5 (analysis threshold; not an original dataset label)", "f1": 0.8853784532454892, "macro_f1": 0.6272792554649367, "mae": 0.2015016977860969, "pr_auc": 0.8984689896834751, "precision": 0.8074559606718558, "r2": 0.2066292111777156, "recall": 0.9799469671859463, "rmse": 0.32384794040143955, "roc_auc": 0.7755342171184243, "spearman_rho": 0.4888342147794476, "weighted_f1": 0.7638507519083715}`.
- Limitations: generated/automated source; no human verification; blank question text; noisy or unavailable execution pass_rate; contest-domain only; no evidence-grounded factual verification; exact duplicates grouped but semantic near duplicates not fully excluded.
- Intended use: display as an auxiliary dataset-domain signal alongside the independent validators.
- Not intended: standalone correctness/safety proof, factual verification, replacing isolated tests, or assigning CodeGuard review/gold labels.
