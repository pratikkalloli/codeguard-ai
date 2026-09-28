# CodeGuard Claim Verifier — Model Card

**Model version:** `claim-verifier-v1.0.0`  
**Dataset version:** generated `1.0.0-synthetic-pilot-<UTC timestamp>`  
**Model artifact:** `models/claim_verifier/claim_verifier_v1.joblib` (Logistic Regression)  
**Last trained:** 2026-09-26

## Purpose

This is a small supervised-learning demonstration that predicts one of `SUPPORTED`, `CONTRADICTED`, or `INSUFFICIENT_EVIDENCE` from an explanation claim and retrieved passage. The result is an **advisory classification**, not evidence or proof that a claim is true.

The existing deterministic verifier remains authoritative. Direct evidence-backed rule results are preserved. The classifier is consulted only for claims the deterministic verifier classifies as insufficient; its prediction, confidence, and review state are stored separately from the rule result.

## Training data

- **Total:** 15 records.
- **Class distribution:** 5 `SUPPORTED`, 5 `CONTRADICTED`, 5 `INSUFFICIENT_EVIDENCE`.
- **Origin:** all 15 are marked `synthetic`; there are no human-labeled records.
- For each of the five current explicit proposition rules, one supported and one opposite-polarity claim are generated and checked against that rule and its retrieved Python documentation passage.
- Five separate out-of-scope topics are labeled insufficient only because the present corpus/rules do not establish them. This label does not mean the claims are false. Some have no retrieved passage.
- The equal class counts follow the selected proposition/topic coverage. Class balance was not used as evidence of representativeness.
- Source, title, URL, section, chunk ID, retrieval score, corpus SHA-256, and label rationale are retained when available in `data/ml/claims.csv` and `data/ml/dataset_metadata.json`.

The source corpus contains 12 curated paraphrase chunks from official Python documentation. It is small and is not an independent real-world claim dataset.

**Separate final candidate:** `data/ml/final/` contains a later 31-record synthetic data build for future research. It was not used to train the artifacts described by this model card and is not connected to production inference. See its `dataset_metadata.json` and `dataset_sources.json` for provenance and limitations.

## Split and leakage controls

Splits are deterministic with seed 42 and grouped so each proposition pair and each out-of-scope topic stays in one partition. Near-duplicate claim/evidence pairs are detected using transparent string-similarity thresholds and checked not to cross the split boundary. With only five independent groups per class, the actual split is **9 train / 3 validation / 3 test (60/20/20)** instead of the approximate requested 70/15/15. Each partition has one example per class in validation and test. Train-only cross-validation uses three-fold `StratifiedGroupKFold`; paired examples stay within the same fold.

The three-record test set is far too small for reliable generalization estimates. Each per-class test support is one.

## Features

- Word unigram/bigram TF-IDF over the claim concatenated with the retrieved evidence.
- Claim and evidence word counts.
- Claim-token overlap with evidence.
- Existing local retrieval TF-IDF cosine score.

No target label, label-derived feature, test result, or future outcome is provided to the feature extractor. TF-IDF is lexical and does not represent semantic understanding.

## Algorithms and training

The reproducible script `python -m codeguard.ml.train` trains:

1. A majority-class baseline derived from the training partition.
2. Balanced Logistic Regression on the TF-IDF and numeric feature union. This is the advisory integration artifact because it exposes class probabilities.
3. Balanced Linear SVM on the same feature union. This baseline has no probability output in this implementation.

Hyperparameters are fixed in code; the test set is not used for tuning or selection. Both model artifacts are saved under `models/`.

## Evaluation procedure and actual results

Metrics below were computed once on the three-record held-out test set. Precision and recall are macro averages; F1 (micro) equals accuracy for this single-label multiclass task.

| Model | Accuracy | Precision (macro) | Recall (macro) | F1 (micro) | Macro F1 | Weighted F1 |
|---|---:|---:|---:|---:|---:|---:|
| Majority baseline | 0.333 | 0.111 | 0.333 | 0.333 | 0.167 | 0.167 |
| Logistic Regression | 0.333 | 0.167 | 0.333 | 0.333 | 0.222 | 0.222 |
| Linear SVM | 0.667 | 0.500 | 0.667 | 0.667 | 0.556 | 0.556 |

Logistic Regression per-class results (one test example per class):

| Actual class | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| SUPPORTED | 0.500 | 1.000 | 0.667 | 1 |
| CONTRADICTED | 0.000 | 0.000 | 0.000 | 1 |
| INSUFFICIENT_EVIDENCE | 0.000 | 0.000 | 0.000 | 1 |

The Logistic Regression confusion matrix uses rows = actual and columns = predicted, ordered `SUPPORTED`, `CONTRADICTED`, `INSUFFICIENT_EVIDENCE`:

```text
[[1, 0, 0],
 [1, 0, 0],
 [0, 1, 0]]
```

The Logistic Regression model missed the contradicted dictionary-order example (predicted supported) and the insufficient-evidence string-mutability example (predicted contradicted). Linear SVM also missed the contradicted dictionary-order example. These few cases are not enough to establish error patterns beyond this generated set.

Three-fold grouped cross-validation used the **training split only**:

| Model | Mean accuracy | Accuracy std | Mean macro F1 | Macro F1 std |
|---|---:|---:|---:|---:|
| Logistic Regression | 0.889 | 0.157 | 0.852 | 0.210 |
| Linear SVM | 0.556 | 0.157 | 0.426 | 0.183 |

The higher Logistic Regression cross-validation results alongside its 0.333 held-out accuracy show instability/overfitting on this tiny dataset. The held-out result must remain visible and should not be replaced by the cross-validation score.

Machine-readable results, classification reports, and error examples are in `reports/pilot/ml_metrics.json`; the dataset summary is in `reports/pilot/ml_dataset_analysis.json`; model comparison is in `reports/pilot/model_comparison.csv`; the Logistic Regression confusion matrix is `reports/pilot/confusion_matrix.png`.

## Confidence and review threshold

The integrated Logistic Regression emits its maximum class probability. These values are **uncalibrated model scores**, not probabilities that a claim is true. On the three-row validation split, two predictions were correct and one was wrong. The threshold is the next representable probability above the most confident validation error: **0.909170314714529**. That rejects the observed validation error. This empirical threshold is provisional and fragile because it is derived from only three synthetic rows. Predictions under it are marked **LOW CONFIDENCE / REVIEW REQUIRED**. The rule-based result is preserved regardless of the ML prediction.

## Intended and non-intended use

**Intended:** classroom demonstration of a reproducible classical ML workflow, feature extraction, group-aware splitting, metrics, and cautious integration.

**Not intended:** factual verification, replacing documentation evidence or deterministic rules, evaluating arbitrary AI explanations in production, ranking AI providers, or making safety/security decisions.

## Limitations and failure cases

- All training and evaluation examples are synthetic, tiny, and derived from the same narrow rule/corpus concepts.
- The test set has three records; reported scores are highly discrete and unreliable as population estimates.
- The corpus consists of paraphrases, not a broad independently labeled documentation collection.
- Lexical overlap can be misleading; TF-IDF does not capture meaning, context, negation robustly, or entailment.
- Logistic probabilities are not calibrated. The validation-derived rejection threshold is not a validated operating point.
- The classifier performs poorly on the held-out Logistic Regression cases and does not beat the majority baseline in test accuracy.
- New domains, wording, Python versions, evidence formats, or changed corpus/rules may invalidate its behavior.
- The deterministic rule verifier remains authoritative; an ML output never turns a rule-insufficient claim into evidence-backed support or contradiction.

Retrain only after adding independently reviewed, provenance-preserving labeled examples and repeating group-aware evaluation. Never report synthetic samples as human-labeled data.
