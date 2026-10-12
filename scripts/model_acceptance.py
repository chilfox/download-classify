#!/usr/bin/env python3
"""Independent, local-only, non-moving model acceptance. Not part of pytest."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import statistics
import time

# No network requests, including telemetry, during document processing.
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

ROOT = Path(__file__).resolve().parents[1]
MODEL_ID = "fastino/gliner2-multi-v1"
REVISION = "ce747d79a8e362d3dee0b0b26d1201f7f1a8615a"
MIN_SCORE = 0.80
MIN_GAP = 0.20
MAX_BYTES = 64 * 1024


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((ROOT / "fixtures/model-acceptance/manifest.json").read_text())
    report = {
        "model": MODEL_ID, "revision": REVISION, "device": "cpu",
        "platform": platform.platform(), "machine": platform.machine(),
        "versions": {name: importlib.metadata.version(name) for name in ("gliner2", "torch", "transformers")},
        "thresholds": {"minimum_score": MIN_SCORE, "minimum_gap": MIN_GAP},
        "score_semantics": "Independent sigmoid logits, temperature 1; not calibrated probabilities; do not sum to one.",
        "categories": manifest["categories"], "results": [],
        "movement_enabled": False,
    }
    try:
        from gliner2 import GLiNER2
        started = time.perf_counter()
        model = GLiNER2.from_pretrained(MODEL_ID, revision=REVISION, local_files_only=True).to("cpu").eval()
        report["load_seconds"] = time.perf_counter() - started
        schema = model.create_schema().classification(
            "document_topic", manifest["categories"], multi_label=True,
            cls_threshold=0.0, class_act="sigmoid",
        )
        limit = model.encoder.config.max_position_embeddings
        report["input_limits"] = {
            "tokenizer_model_max_length": model.processor.tokenizer.model_max_length,
            "encoder_max_position_embeddings": limit,
            "selected_encoded_token_budget": limit,
            "budget_note": "512 is the conservative configured context budget, not a hard architectural ceiling for relative attention.",
            "max_bytes": MAX_BYTES,
            "policy": "No truncation or sampling. Reject over-budget input before inference. User policy pending.",
        }
        for sample in manifest["samples"]:
            with (ROOT / "fixtures/model-acceptance" / sample["file"]).open("rb") as source:
                data = source.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise ValueError("Acceptance fixture exceeds read budget")
            text = data.decode("utf-8")
            # The public processor includes category descriptions, special tokens,
            # classification prefix and document subwords in this exact count.
            batch = model.processor.collate_fn_inference([(text, schema.build())], max_len=None)
            count = batch.input_ids.shape[1]
            if count > limit:
                raise ValueError(f"Acceptance fixture exceeds encoder budget: {count} > {limit}")
            started = time.perf_counter()
            output = model.extract(text, schema, include_confidence=True, max_len=None)
            elapsed = time.perf_counter() - started
            candidates = output["document_topic"]
            scores = {item["label"]: item["confidence"] for item in candidates}
            if set(scores) != set(manifest["categories"]):
                raise ValueError("Model failed to return every candidate score")
            ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
            gap = ranked[0][1] - ranked[1][1] if len(ranked) > 1 else None
            clear = ranked[0][1] >= MIN_SCORE and (gap is None or gap >= MIN_GAP)
            report["results"].append({
                **sample, "input_bytes": len(data), "encoded_tokens": count,
                "scores": scores, "prediction": ranked[0][0], "top_two_gap": gap,
                "correct": ranked[0][0] == sample["expected"],
                "would_move": clear, "inference_seconds": elapsed,
            })
        # Probe tokenizer behavior safely without an encoder pass on long text.
        probes = {}
        for language, text in {"English": "Invoice payment due. " * 1000, "Traditional Chinese": "發票付款期限。" * 1000}.items():
            full = model.processor.collate_fn_inference([(text, schema.build())], max_len=None)
            capped = model.processor.collate_fn_inference([(text, schema.build())], max_len=512)
            probes[language] = {"characters": len(text), "full_encoded_tokens": full.input_ids.shape[1], "word_cap_512_encoded_tokens": capped.input_ids.shape[1]}
        report["overlong_probes"] = probes
        probe_text = "Invoice payment due. " * 100
        probe_batch = model.processor.collate_fn_inference([(probe_text, schema.build())], max_len=None)
        started = time.perf_counter()
        probe_output = model.extract(probe_text, schema, include_confidence=True, max_len=None)
        report["above_configured_context_probe"] = {
            "encoded_tokens": probe_batch.input_ids.shape[1],
            "output": probe_output, "inference_seconds": time.perf_counter() - started,
            "note": "Synthetic non-moving probe only; success does not validate long-document quality.",
        }
        results = report["results"]
        clear_results = [r for r in results if r["would_move"]]
        latencies = [r["inference_seconds"] for r in results]
        report["summary"] = {
            "correct": sum(r["correct"] for r in results), "total": len(results),
            "automatic_coverage_count": len(clear_results),
            "automatic_correct_count": sum(r["correct"] for r in clear_results),
            "median_inference_seconds": statistics.median(latencies),
            "max_inference_seconds": max(latencies),
        }
        report["recommended_mode"] = (
            "automatic for complete bounded inputs only, pending user input-policy approval"
            if report["summary"]["correct"] >= 10 and clear_results and all(r["correct"] for r in clear_results)
            else "suggestions-only"
        )
    except Exception as exc:
        report["failure"] = f"{type(exc).__name__}: {exc}"
        report["recommended_mode"] = "unavailable: leave files untouched"
        raise
    finally:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(report.get("summary", report.get("failure")), indent=2))


if __name__ == "__main__":
    main()
