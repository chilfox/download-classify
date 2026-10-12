#!/usr/bin/env python3
"""Check bounded PDF extraction and real local-model inference without file changes."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.model import LocalModel, MODEL_ID, REVISION
from backend.model_input import ENCODED_TOKEN_BUDGET, read_opening

CATEGORIES = {
    "Invoice": "Bills, payment requests, receipts, and financial transactions.",
    "Academic research": "Scientific papers, studies, research findings, and scholarly analysis.",
    "Travel itinerary": "Flight, hotel, transportation, and trip schedule information.",
}


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", nargs="?", type=Path, default=ROOT / "fixtures/pdf/invoice.pdf",
                        help="PDF to inspect (default: fixtures/pdf/invoice.pdf)")
    args = parser.parse_args()
    path = args.pdf.resolve()
    original_digest = file_digest(path)
    started = time.perf_counter()
    opening = read_opening(path)
    extraction_seconds = time.perf_counter() - started

    model = LocalModel()
    started = time.perf_counter()
    model.load()
    load_seconds = time.perf_counter() - started
    started = time.perf_counter()
    scores, model_truncated, tokens = model.classify(opening, CATEGORIES)
    inference_seconds = time.perf_counter() - started

    assert set(scores) == set(CATEGORIES), f"Unexpected candidate labels: {sorted(scores)}"
    assert all(isinstance(score, (int, float)) and 0 <= score <= 1 for score in scores.values()), scores
    assert all(math.isfinite(score) for score in scores.values()), scores
    assert 0 < tokens <= ENCODED_TOKEN_BUDGET, tokens
    assert file_digest(path) == original_digest, "PDF changed during smoke check"
    print(json.dumps({
        "pdf": str(path), "model": MODEL_ID, "revision": REVISION, "device": "cpu",
        "scores": scores, "encoded_tokens": tokens,
        "truncated": opening.read_truncated or model_truncated,
        "timings_seconds": {"pdf_extraction": extraction_seconds, "model_load": load_seconds,
                             "inference": inference_seconds},
        "note": "Smoke check only; inference success is not evidence of classification quality.",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
