#!/usr/bin/env python3
"""Real-model macOS/Linux API/filesystem acceptance in a fresh disposable directory.

Requires model-check and test extras plus cached weights. No model substitution.
Keeps the disposable directory for inspection; never uses the user's Downloads.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from backend.app import create_app
from backend.model import MODEL_ID, REVISION


def wait_for(client, endpoint, predicate, timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(endpoint)
        response.raise_for_status()
        value = response.json()
        if predicate(value):
            return value
        time.sleep(0.1)
    raise AssertionError(f"Timed out waiting for {endpoint}: {value}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if sys.platform not in {"darwin", "linux"}:
        parser.error("Automatic movement acceptance requires macOS or Linux; native Windows is unsupported")
    workspace = Path(tempfile.mkdtemp(prefix="download-classify-acceptance-")).resolve()
    inbox = workspace / "inbox"
    inbox.mkdir()
    manifest = json.loads((ROOT / "fixtures/model-acceptance/manifest.json").read_text())
    settings = {"categories": [{"name": name, "description": description}
                               for name, description in manifest["categories"].items()]}
    report = {"model": MODEL_ID, "revision": REVISION, "device": "cpu",
              "platform": platform.platform(), "python": platform.python_version(),
              "versions": {name: importlib.metadata.version(name)
                           for name in ("gliner2", "torch", "transformers")},
              "workspace": str(workspace), "seam": "Public backend API + disposable filesystem, real LocalModel",
              "poll_interval_seconds": 1.0, "movement_enabled": True}
    try:
        baseline = inbox / "baseline.txt"
        baseline.write_bytes(b"Existing entries must stay untouched")
        # Preserve both files in a real filename collision.
        (inbox / "Invoice").mkdir()
        collision = inbox / "Invoice" / "01.txt"
        collision.write_bytes(b"Existing collision document")
        with TestClient(create_app(workspace / "settings.json", inbox)) as client:
            client.put("/settings", json=settings).raise_for_status()
            client.post("/monitor/start").raise_for_status()
            status = wait_for(client, "/status", lambda s: s["model_status"] in {"ready", "unavailable"})
            assert status["model_status"] == "ready", status
            originals = {}
            for sample in manifest["samples"]:
                content = (ROOT / "fixtures/model-acceptance" / sample["file"]).read_bytes()
                originals[sample["file"]] = content
                (inbox / sample["file"]).write_bytes(content)
            unsupported = {"unsupported.zip": b"PK disposable", "unsupported.bin": b"disposable binary"}
            for name, content in unsupported.items():
                (inbox / name).write_bytes(content)
            rows = wait_for(client, "/results", lambda rows: len(rows) == 14)
            labeled = []
            for sample in manifest["samples"]:
                row = next(row for row in rows if row["filename"] == sample["file"])
                assert row["outcome"] in {"moved", "needs-review"}, row
                assert row["recorded"] is True, row
                assert set(row["scores"]) == set(manifest["categories"])
                assert 0 < row["encoded_tokens"] <= 512
                destination = Path(row["destination"])
                assert destination.read_bytes() == originals[sample["file"]]
                assert not (inbox / sample["file"]).exists()
                prediction = max(row["scores"], key=row["scores"].get)
                labeled.append({**sample, **row, "prediction": prediction,
                                "correct": prediction == sample["expected"],
                                "sha256": hashlib.sha256(originals[sample["file"]]).hexdigest()})
            for name, content in unsupported.items():
                row = next(row for row in rows if row["filename"] == name)
                assert row["outcome"] == "skipped" and "Unsupported" in row["reason"], row
                assert (inbox / name).read_bytes() == content
            assert baseline.read_bytes() == b"Existing entries must stay untouched"
            assert collision.read_bytes() == b"Existing collision document"
            assert (inbox / "Invoice" / "01 (1).txt").read_bytes() == originals["01.txt"]
            # Observe unchanged unsupported files and moved subfolders across more scans.
            time.sleep(2.2)
            assert client.get("/results").json() == rows
            client.post("/monitor/stop").raise_for_status()
            (inbox / "stopped.txt").write_bytes(b"Arrival while stopped")
            client.post("/monitor/start").raise_for_status()
            time.sleep(2.2)
            assert client.get("/results").json() == rows
            assert (inbox / "stopped.txt").read_bytes() == b"Arrival while stopped"
            client.post("/monitor/stop").raise_for_status()
            report["status"] = client.get("/status").json()
            report["results"] = labeled
            report["unsupported_results"] = [r for r in rows if r["outcome"] == "skipped"]
        records = [json.loads(line) for line in (workspace / "movements.jsonl").read_text().splitlines()]
        assert len(records) == 12
        for row in labeled:
            record = next(r for r in records if r["original"] == str(inbox / row["file"]))
            assert record["destination"] == row["destination"] and record["result"] == row["outcome"]
            assert record["time"]
        report["movement_records"] = records
        report["summary"] = {"correct": sum(r["correct"] for r in labeled), "total": 12,
                             "automatic_topic_moves": sum(r["outcome"] == "moved" for r in labeled),
                             "automatic_topic_moves_correct": sum(r["correct"] and r["outcome"] == "moved" for r in labeled),
                             "needs_review_moves": sum(r["outcome"] == "needs-review" for r in labeled),
                             "all_moved_bytes_verified": True, "jsonl_verified": True}
        assert report["summary"]["correct"] >= 10, report["summary"]
        assert all(r["correct"] for r in labeled if r["outcome"] == "moved"), report["summary"]
        assert report["summary"]["needs_review_moves"] >= 1
        txt_destinations = {r["suggestion"] for r in labeled if r["file"].endswith(".txt") and r["outcome"] == "moved"}
        assert len(txt_destinations) >= 2
        # Explicit non-moving fallback using the same real model boundary.
        fallback = workspace / "fallback"
        fallback.mkdir()
        with TestClient(create_app(workspace / "fallback-settings.json", fallback, mode="suggestions-only",
                                   movement_log=workspace / "movements-fallback.jsonl")) as client:
            client.put("/settings", json=settings).raise_for_status()
            client.post("/monitor/start").raise_for_status()
            (fallback / "01.txt").write_bytes(originals["01.txt"])
            row = wait_for(client, "/results", bool)[0]
            assert row["outcome"] == "suggestion-only" and row["destination"] is None, row
            assert (fallback / "01.txt").read_bytes() == originals["01.txt"]
            assert not (workspace / "movements-fallback.jsonl").exists()
            report["fallback_result"] = row
        print(json.dumps(report["summary"], indent=2))
        print(f"Disposable files retained for inspection: {workspace}")
    except Exception as error:
        report["failure"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
