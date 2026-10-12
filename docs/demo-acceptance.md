# Complete macOS demonstration acceptance

## Observed outcome

Ticket 05 independently exercised the integrated backend on 2026-10-12, based on `6d05e35` (integration including tickets 03/04). The completed automatic workflow passed with the real pinned `fastino/gliner2-multi-v1` checkpoint, CPU, cached weights and no model substitution. The public API was exercised with FastAPI TestClient, its real lifespan/background monitor, one-second stability scans, and a fresh temporary filesystem. A separate Uvicorn/Vite/desktop Chromium pass repeated the 12 fixtures through the browser-connected runtime.

| Measure | Observed |
| --- | --- |
| Top-scoring prediction accuracy | 11/12 (91.7%), target >=10 met |
| Automatic topic-movement coverage | 11/12 (91.7%) |
| Correct automatic topic moves | 11/11 |
| Actual uncertain movement | 1/12 to NeedsReview |
| Moved bytes and JSONL trace | All 12 verified |
| Unsupported PDF and ZIP | Both skipped with explanation; original bytes untouched |
| Real-model suggestions-only probe | Invoice suggestion; source untouched, no destination/trace |

The clinical-trial manuscript `10.md`, labeled Academic research, top-predicts Medical report but fails the fixed score/gap thresholds and actually reaches NeedsReview. Do not count its safe uncertainty routing as a correct topic prediction. English prediction accuracy is 5/6 and Traditional Chinese 6/6. TXT files reach distinct Invoice, Travel itinerary, Medical report and Academic research destinations despite sharing an extension. The `01.txt` collision preserved the existing document and moved the arriving bytes to `Invoice/01 (1).txt`.

The raw [API/filesystem report](demo-acceptance-results.json) contains the captured category descriptions, every candidate score, encoded-token counts, expected labels, predictions, outcomes, destinations, SHA-256 hashes, status, and original/destination/time/result records. Its absolute temporary paths are observed provenance, not portable instructions. All 12 short fixtures used 241-280 tokens with no truncation. Categories and the source fixture manifest are committed under `fixtures/model-acceptance/`.

Environment: current Apple Silicon MacBook, macOS 26.5.2 / Darwin 25.5.0 arm64, Python 3.12.11, gliner2 2.1.0, torch 2.14.1, transformers 5.19.0. Checkpoint revision: `ce747d79a8e362d3dee0b0b26d1201f7f1a8615a`. Ordinary pytest does not import/initialize this model and is not quality evidence.

## Reproduce

From the repository root after installing uv, Node/npm and Python 3.12:

```sh
uv sync --extra model-check --extra test --python 3.12
(cd frontend && npm ci)
# Initial weight download is permitted only in setup:
uv run --extra model-check python scripts/model_smoke.py
# Completed bounded API/monitor/movement workflow, cached local model:
uv run --extra model-check --extra test python scripts/demo_acceptance.py \
  --output /tmp/download-classify-demo-results.json
# Separate classification/input-budget evidence, not movement acceptance:
uv run --extra model-check python scripts/model_acceptance.py \
  --output /tmp/download-classify-independent-model.json
uv lock --check
uv run --extra test pytest -W error
(cd frontend && npm run check && npm run build)
```

The completed-workflow driver retains and prints its fresh disposable directory. It never uses real Downloads or existing user documents. Processing sets HF offline mode and disables telemetry. Missing cached weights produce failure, not a synthetic suggestion. Follow README startup instructions for a separately running browser demo. Use exactly the manifest category descriptions to reproduce the numerical model evidence.

## Monitoring and filesystem verification

All **43 existing tests passed with warnings treated as errors**, through the approved public API + temporary filesystem seam, replacing only the model boundary. The tests were read and inspected; no missing critical safety behavior or blocking implementation defect was found, so no application changes or redundant new tests were needed.

- `test_monitoring.py`: start/restart baseline and exclusions, stable-arrival processing while a document is changing, unchanged-file deduplication, explicit read/UTF-8/model errors, model reuse, responsive status/stop while inference is blocked, restart refusal during an active attempt, captured categories and subsequent-only edits, lifecycle drain, stale-source discard and stable retry.
- `test_movement.py`: clear/uncertain movement, source/destination safety and symlink rejection, identity changes, same-size edits with restored mtime, collisions (including arrivals during inference/concurrent collisions), exact source-byte preservation, JSONL records and visible trace failures, fallback and current-session results.
- `test_settings.py`: folder-name validation and persistence. Exact tokenizer-budget validation has independent real-model evidence, not just the controlled boundary.

The real-model completed-workflow driver additionally checks baseline preservation, stop/restart baseline, multiple subsequent scans without repeated results, same-extension topic destinations, preserved collision bytes and 12 valid movement records. Timing-critical stop/category-change/source-change cases use the controlled model boundary tests, not unverifiable claims about racing a fast real CPU inference.

## Desktop browser evidence

A fresh headless desktop Chromium session at **1280x1000** connected to Uvicorn on loopback port 8000 and Vite on 5177. A local CDP driver performed actual DOM interactions, with screenshots visually inspected (not a committed E2E framework):

- Edited and saved Invoice demo, then restored Invoice; attempted reserved NeedsReview and saw the explicit red validation error without replacing saved settings.
- Started monitoring, observed watching/ready status, added all 12 real fixtures plus unsupported PDF, observed 11 topic moves, one NeedsReview, one skipped PDF, trace status and score/token disclosures; checked each moved file against fixture bytes.
- Stopped monitoring; stopped the backend without reloading the browser. Visible connection error and stale-data warning appeared, all 13 current-run results remained, and Start was disabled.
- Category/editor alignment, typography, spacing, destination wrapping and result cards were inspected. No clipping or horizontal overflow was observed; no blocking layout defect. Desktop only, no mobile acceptance.

Current-machine evidence (temporary, not promised as permanent artifacts):

- `/tmp/dc-ticket05-browser-{top,validation,results,error}.png`
- `/tmp/dc-ticket05-browser-{success,error}.txt`
- `/tmp/dc-ticket05-browser-results.json`, `/tmp/dc-ticket05-movements.jsonl`
- `/tmp/dc-ticket05-browser.mjs`, `/tmp/dc-ticket05-browser-error.mjs`
- `/tmp/ticket05-api.log`, `/tmp/ticket05-vite.log`

All verification servers/browser processes were stopped after acceptance. Disposable documents/evidence remain for local inspection.

## Independent checks and limitations

- `uv lock --check`: passed.
- `uv run --extra test pytest -W error`: **43 passed**.
- Frontend TypeScript check and production build: passed. npm install audited 70 packages with zero vulnerabilities; it reported allow-scripts notices for esbuild/fsevents, but build completed.
- Independent real-model smoke: passed; load/download 4.80s, Chinese inference 0.07s, English 0.05s. `/tmp/ticket05-smoke.log`. The smoke's Chinese medical example predicts Invoice with its limited three-label schema; this is not the labeled acceptance result.
- Independent non-moving acceptance: 11/12 predictions and 11/12 qualifying coverage again; `/tmp/ticket05-independent-model.json` and `.log`. Its two 210,000-byte English/Chinese probes preserve bytes and fit Unicode-safe excerpts to 511 encoded tokens. These are resource/input-safety probes, not long-document quality validation.
- Real-model dependencies emitted extractor/model-type compatibility logging and torch's `torch.jit.script` FutureWarning; loading/inference succeeded. Smoke also disclosed unauthenticated HF setup requests. Warnings are not silently suppressed.

Automatic movement is verified on this macOS machine only. No production safety, Ubuntu compatibility or clean-install reproducibility claim. The hand-authored 12-document set is not a representative held-out corpus; independent sigmoid scores are not correctness probabilities. Approved opening-excerpt movement uses at most 64 KiB and a complete prompt <=512 encoded tokens, with visible truncation disclosure; long-document quality remains unvalidated. Stable scans are a heuristic, not protection against a hostile writer retaining descriptors. NeedsReview is handled manually in Finder; no undo or automatic restoration exists. No hidden non-moving fallback is used. No acceptance blocker remains.
