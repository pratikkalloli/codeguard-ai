# Phase 17 model results

Regression target: source-recorded `pass_rate` in [0, 1]. Accuracy/F1/AUC use the derived reporting threshold `pass_rate >= 0.5`; this is not an original dataset label.

| Model | Validation MAE | Test MAE | Test RMSE | Test R² | Test accuracy* | Test macro F1* | Test weighted F1* |
|---|---:|---:|---:|---:|---:|---:|---:|
| Mean dummy | 0.2839 | 0.2993 | 0.3643 | -0.0038 | 0.7646 | 0.4333 | 0.6626 |
| Ridge | 0.2260 | 0.2350 | 0.3159 | 0.2453 | 0.8082 | 0.6741 | 0.7847 |
| LinearSVR (selected) | 0.1841 | 0.2015 | 0.3238 | 0.2066 | 0.8060 | 0.6273 | 0.7639 |
| ExtraTrees numeric | 0.2621 | 0.2781 | 0.3568 | 0.0372 | 0.7639 | 0.4926 | 0.6890 |

Selected using validation MAE: **LinearSVR (`C=0.1`)**. The held-out test set was not used for model or hyperparameter selection. See `phase17_model_results.json` for precision/recall, ROC-AUC, PR-AUC, confusion matrices, and Spearman correlation.
