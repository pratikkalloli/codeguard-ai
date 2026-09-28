from __future__ import annotations

import json
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import joblib
import pyarrow as pa
import pyarrow.parquet as pq

from codeguard.ml.phase17_public_data import code_features, preprocess
from codeguard.ml.public_reliability import predict_pass_rate
from scripts.training.train_phase17 import make_splits, union_find_groups
from scripts.download.download_phase17_dataset import download, sha256


class ConstantModel:
    def predict(self, frame):
        return [0.625] * len(frame)


class FakeResponse:
    def __init__(self, data: bytes, status: int, headers: dict[str, str]):
        self.data, self.status, self.headers = data, status, headers

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = len(self.data)
        result, self.data = self.data[:size], self.data[size:]
        return result


class Phase17PublicDataTests(unittest.TestCase):
    def test_downloader_resumes_and_hashes(self):
        payload = b"phase17-download-payload"

        def fake_urlopen(request, timeout=0):
            if request.get_method() == "HEAD":
                return FakeResponse(b"", 200, {"Content-Length": str(len(payload))})
            start, end = map(int, request.get_header("Range").split("=")[1].split("-"))
            return FakeResponse(payload[start:end + 1], 206, {})

        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp) / "raw.bin"
            dest.with_suffix(".bin.part").write_bytes(payload[:5])
            with patch("scripts.download.download_phase17_dataset.urllib.request.urlopen", side_effect=fake_urlopen):
                download("https://example.invalid/data", dest)
            self.assertEqual(dest.read_bytes(), payload)
            self.assertEqual(sha256(dest), hashlib.sha256(payload).hexdigest())

    def test_feature_extraction_is_static_and_handles_malformed_code(self):
        valid = code_features("import os\ndef f(x):\n    for i in x:\n        if i: pass\n")
        self.assertEqual(valid["syntax_valid"], 1.0)
        self.assertEqual(valid["functions"], 1.0)
        self.assertEqual(valid["loops"], 1.0)
        invalid = code_features("def broken(:\n    pass")
        self.assertEqual(invalid["syntax_valid"], 0.0)
        self.assertGreater(invalid["code_chars"], 0)

    def test_preprocessing_license_target_missing_and_exact_duplicate_filters(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shard_dir = root / "raw" / "train" / "python"
            shard_dir.mkdir(parents=True)
            rows = [
                {"id": "a", "question_id": "q1", "solution": "print(1)", "pass_rate": 1.0, "license": "apache-2.0", "source": "x", "dataset": "d", "split": "train", "difficulty": "EASY"},
                {"id": "b", "question_id": "q1", "solution": "print(1)", "pass_rate": 1.0, "license": "apache-2.0", "source": "x", "dataset": "d", "split": "train", "difficulty": "EASY"},
                {"id": "c", "question_id": "q2", "solution": "print(2)", "pass_rate": -1.0, "license": "mit", "source": "x", "dataset": "d", "split": "train", "difficulty": "EASY"},
                {"id": "d", "question_id": "q3", "solution": "print(3)", "pass_rate": 0.5, "license": "unknown", "source": "x", "dataset": "d", "split": "train", "difficulty": "EASY"},
                {"id": "e", "question_id": "q4", "solution": "", "pass_rate": 0.5, "license": "mit", "source": "x", "dataset": "d", "split": "train", "difficulty": "EASY"},
            ]
            pq.write_table(pa.Table.from_pylist(rows), shard_dir / "train-00000-of-00070.parquet")
            out, report_path, sample_path = root / "processed.jsonl", root / "prep.json", root / "sample.json"
            result = preprocess(root / "raw", out, report_path, sample_path)
            kept = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(kept), 1)
            self.assertEqual(kept[0]["pass_rate"], 1.0)
            self.assertEqual(result["counts"]["excluded_exact_duplicate"], 1)
            self.assertEqual(result["counts"]["excluded_invalid_pass_rate"], 1)
            self.assertEqual(result["counts"]["excluded_license"], 1)
            self.assertEqual(result["counts"]["excluded_missing_code"], 1)
            self.assertTrue(report_path.is_file())
            self.assertTrue(sample_path.is_file())

    def test_group_splits_hold_question_and_exact_code_together(self):
        records = [
            {"question_id": f"q{i}", "code_sha256": f"h{i}", "pass_rate": i % 2}
            for i in range(120)
        ]
        records.extend([
            {"question_id": "q0", "code_sha256": "h120", "pass_rate": 1},
            {"question_id": "q999", "code_sha256": "h0", "pass_rate": 1},
        ])
        components = union_find_groups(records)
        self.assertEqual(components[0], components[-1])
        splits = make_splits(records)
        names = list(splits)
        for i, left in enumerate(names):
            for right in names[i + 1:]:
                self.assertFalse({r["question_id"] for r in splits[left]} & {r["question_id"] for r in splits[right]})
                self.assertFalse({r["code_sha256"] for r in splits[left]} & {r["code_sha256"] for r in splits[right]})

    def test_prediction_loads_model_and_marks_auxiliary_scope(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "model.joblib"
            joblib.dump({"model": ConstantModel(), "model_name": "test-constant", "revision": "rev"}, path)
            prediction = predict_pass_rate("x = 1", metadata={"source": "atcoder"}, model_path=path)
            self.assertEqual(prediction["status"], "predicted")
            self.assertEqual(prediction["prediction"], 0.625)
            self.assertEqual(prediction["confidence"], None)
            self.assertIn("auxiliary", prediction["limitations"][0])
            self.assertEqual(predict_pass_rate("", model_path=path)["status"], "not_available")
            self.assertEqual(predict_pass_rate("x = 1", model_path=Path(temp) / "missing")["status"], "not_available")


if __name__ == "__main__":
    unittest.main()
