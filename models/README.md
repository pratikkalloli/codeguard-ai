# Model artifacts

This directory contains serialized estimators and the configuration needed to interpret them.

- `phase17/` is the public reliability regression model. `pass_rate_predictor.joblib` predicts the source-recorded execution pass rate for competitive-programming Python solutions. It is not a CodeGuard explanation-verification model.
- `claim_verifier/` contains the small synthetic claim/evidence pilot classifiers used for advisory inference. These do not establish factual correctness and are not trained on adjudicated human labels.

The Phase 17 artifact is checked in together with `feature_config.json`, `target_definition.json`, `training_config.json`, and `MODEL_CARD.md`. Its reproducible training workflow is `python scripts/training/train_phase17.py`, using the pinned dataset workflow documented in [data/README.md](../data/README.md). Do not retrain just to load the model.

The claim-verifier pilot can be regenerated with `python -m codeguard.ml.train`; generated estimator files are saved beneath `models/claim_verifier/`. The synthetic data and evaluation outputs are described in [the model card](../docs/research/MODEL_CARD.md).

Limitations: both model families are research artifacts. Phase 17 models an automated benchmark target from a narrow domain, and the claim verifier uses a tiny synthetic pilot. Neither replaces static validation, isolated execution, documentary evidence, human review, or an independent benchmark. Predictions are advisory.
