# Data layout

This directory holds local application state, reproducible research data, and derived datasets.

- `raw/phase17/` contains the bounded NVIDIA OpenCodeReasoning-2 Python download, its source README, and `DATASET_METADATA.json`. Raw Parquet shards are intentionally ignored by Git because they are large; metadata and download instructions are retained.
- `processed/` contains derived Phase 17 JSONL records. Regenerate them with the training workflow below; it does not overwrite the raw source.
- `splits/phase17/` contains the fixed grouped train, validation, and test split files produced by Phase 17.
- `ml/` contains the synthetic pilot and research/review datasets used by earlier phases. Do not interpret proposed review labels as adjudicated gold labels.
- `codeguard.db` is local SQLite application state and is ignored by Git; it may include private prompts and responses.

## Phase 17 reproduction

Dataset: [NVIDIA OpenCodeReasoning-2](https://huggingface.co/datasets/nvidia/OpenCodeReasoning-2), Python split, pinned revision `eadf535931451525f3e5621d0f960c240bc62fd9`. The collection is identified upstream as CC BY 4.0, while upstream source records may carry their own license terms. The downloader preserves per-row license values and the preprocessing allow-list; review the source terms before redistribution.

After installing the project and its dependencies, run:

```powershell
python scripts/download/download_phase17_dataset.py
python scripts/training/train_phase17.py
```

The download script fetches only the first three contiguous Python shards and writes per-file SHA-256 metadata. Training rebuilds processed records and grouped splits and updates the model and generated reports. It is a reproduction command; do not run it when the intent is only to load or inspect the checked-in model.

See [Phase 17 dataset selection](../docs/research/PHASE_17_DATASET_SELECTION.md), [research notes](../docs/research/PHASE_17_DATASET_RESEARCH.md), and the [model card](../docs/research/MODEL_CARD.md).
