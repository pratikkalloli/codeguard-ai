"""Command-line wrapper for the bounded Phase 17 public-data preprocessor."""

from __future__ import annotations

import argparse
from pathlib import Path

from codeguard.ml.phase17_public_data import preprocess


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, default=root / "data" / "raw" / "phase17" / "opencodereasoning2")
    parser.add_argument("--processed", type=Path, default=root / "data" / "processed" / "phase17_records.jsonl")
    parser.add_argument("--report", type=Path, default=root / "reports" / "phase17" / "phase17_preprocessing_report.json")
    parser.add_argument("--sample", type=Path, default=root / "reports" / "phase17" / "phase17_dataset_sample.json")
    args = parser.parse_args()
    result = preprocess(args.raw, args.processed, args.report, args.sample)
    print(result)


if __name__ == "__main__":
    main()
