#!/usr/bin/env python3
"""Download/load the real GLiNER2 checkpoint and run two CPU classifications."""

from __future__ import annotations

import json
import time

from gliner2 import GLiNER2

MODEL_ID = "fastino/gliner2-multi-v1"
CATEGORIES = {
    "Invoice": "Bills, payment requests, receipts, and financial transactions.",
    "Academic research": "Scientific papers, studies, research findings, and scholarly analysis.",
    "Travel itinerary": "Flight, hotel, transportation, and trip schedule information.",
}
SAMPLES = {
    "Traditional Chinese": "台北市立醫院檢驗報告：患者血液檢查結果顯示血紅素正常，醫師建議三個月後回診追蹤。",
    "English": "Invoice 1048: Acme Research Services billed Northstar Labs $2,400 for laboratory analysis, due September 30, 2026.",
}


def main() -> None:
    print(f"Loading {MODEL_ID} on CPU (first run may download model weights)...", flush=True)
    started = time.perf_counter()
    model = GLiNER2.from_pretrained(MODEL_ID).to("cpu")
    print(f"Model load/download: {time.perf_counter() - started:.2f}s", flush=True)
    schema = model.create_schema().classification(
        "document_topic", CATEGORIES, multi_label=False
    )

    for language, text in SAMPLES.items():
        started = time.perf_counter()
        output = model.extract(text, schema, include_confidence=True)
        elapsed = time.perf_counter() - started
        print(f"\n{language} inference: {elapsed:.2f}s")
        print(json.dumps(output, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
