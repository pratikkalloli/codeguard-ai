"""Download a pinned, bounded prefix of NVIDIA OpenCodeReasoning-2 Python."""

from __future__ import annotations

import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REVISION = "eadf535931451525f3e5621d0f960c240bc62fd9"
BASE = f"https://huggingface.co/datasets/nvidia/OpenCodeReasoning-2/resolve/{REVISION}/train/python"
SHARDS = [f"train-{i:05d}-of-00070.parquet" for i in range(3)]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    part = destination.with_suffix(destination.suffix + ".part")
    chunk_size = 64 * 1024 * 1024
    existing = part.stat().st_size if part.exists() else 0
    probe = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "CodeGuardAI-Phase17/1.0"})
    with urllib.request.urlopen(probe, timeout=120) as response:
        total = int(response.headers.get("Content-Length", "0"))
    if not total:
        raise RuntimeError(f"Server did not provide Content-Length for {url}")
    if existing > total:
        part.unlink()
        existing = 0
    with part.open("ab" if existing else "wb") as stream:
        start = existing
        while start < total:
            end = min(total - 1, start + chunk_size - 1)
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "CodeGuardAI-Phase17/1.0", "Range": f"bytes={start}-{end}"},
            )
            with urllib.request.urlopen(request, timeout=180) as response:
                if response.status != 206:
                    raise RuntimeError(f"Expected HTTP 206 for range {start}-{end}; got {response.status}")
                received = 0
                while received < end - start + 1:
                    block = response.read(min(1024 * 1024, end - start + 1 - received))
                    if not block:
                        break
                    stream.write(block)
                    received += len(block)
                if received != end - start + 1:
                    raise RuntimeError(f"Short range response at offset {start}; rerun to resume")
            stream.flush()
            start = end + 1
    if part.stat().st_size != total:
        raise RuntimeError(f"Download size mismatch for {destination}")
    part.replace(destination)


def main() -> None:
    raw = ROOT / "data" / "raw" / "phase17" / "opencodereasoning2" / "train" / "python"
    entries = []
    for filename in SHARDS:
        path = raw / filename
        if not path.exists():
            download(f"{BASE}/{filename}?download=true", path)
        entries.append({"filename": str(path.relative_to(ROOT)), "bytes": path.stat().st_size, "sha256": sha256(path)})
    metadata = {
        "dataset_name": "NVIDIA OpenCodeReasoning-2 (Python split, bounded three-shard prefix)",
        "source_url": "https://huggingface.co/datasets/nvidia/OpenCodeReasoning-2",
        "revision": REVISION,
        "license": "CC BY 4.0 for the collection; each row's upstream license retained and filtered",
        "row_license_policy": ["apache-2.0", "mit", "cc-by-4.0"],
        "download_timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "reported_full_python_record_count": 1398166,
        "downloaded_files": entries,
        "record_count": None,
        "sha256": None,
        "sha256_method": "After inspection, SHA-256 of the sorted per-shard SHA-256 hex strings concatenated in file order.",
        "notes": "Raw record count and aggregate digest are filled by inspection; usable_record_count is filled after preprocessing. Original Parquet shards are preserved. Three contiguous shards from the pinned Python split; no CodeGuard labels are imported. Upstream license terms may additionally apply.",
    }
    out = ROOT / "data" / "raw" / "phase17" / "DATASET_METADATA.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
