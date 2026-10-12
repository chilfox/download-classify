# Download Classify - local monitoring and suggestions

This slice monitors newly arriving TXT/Markdown documents and shows local GLiNER2 suggestions. **It does not move, delete, or modify any source files.** Automatic organization is approved for the disposable demo but is implemented in the subsequent movement ticket, not this suggestions-only slice. The API health response means only that the API is available; model readiness is reported separately.

## Prerequisites

Install [uv](https://docs.astral.sh/uv/) and Node.js/npm. Python 3.12 is managed by uv. From the repository root:

```sh
uv python install 3.12
uv sync --extra test --python 3.12
(cd frontend && npm ci)
```

## Run locally

First install/cache the optional model using the smoke command below. In separate terminals, from the repository root:

```sh
mkdir -p /tmp/download-classify-demo
DOWNLOAD_CLASSIFY_FOLDER=/tmp/download-classify-demo \
  uv run --extra model-check uvicorn backend.app:app --host 127.0.0.1 --port 8000 --workers 1
```

```sh
cd frontend && npm run dev
```

Open the URL printed by Vite (normally http://127.0.0.1:5173). The frontend proxies settings, monitoring, status, results, and health to the API at http://127.0.0.1:8000. API and frontend bind to loopback only. Stop the API to see the visible connection-error and stale-data state.

Save topic categories, explicitly start monitoring, then add disposable documents. The model loads once on the background worker, using cached weights only with telemetry disabled. The folder defaults to `~/DownloadClassifyDemo` if `DOWNLOAD_CLASSIFY_FOLDER` is unset and must exist before starting. Settings default to `~/.download-classify/categories.json`; override with `DOWNLOAD_CLASSIFY_SETTINGS_PATH` for disposable runs.

## Monitoring behavior and API

- One backend process with **one worker**, one serial processing thread, and no movement in this slice. Status requests stay responsive during loading/inference; shutdown stops new work and waits for the active attempt to finish.
- Every start/restart establishes an existing-entry baseline. Only new regular root files with unchanged size and modification time across consecutive scans (one-second interval) are considered. This is a completion heuristic, not a guarantee a downloader has finished.
- Subdirectories, symlinks, hidden/`~$` entries, and `.crdownload`, `.part`, `.partial`, `.download`, `.tmp`, `.temp` suffixes are excluded. All PDFs and other unsupported formats are reported and left untouched. Source reads reject symlinks at open time.
- Settings are captured per attempt. Source changes during reading/inference discard the stale result and require fresh stability before retry. Unchanged files, including failures, are not repeatedly processed. There is no manual retry feature.
- Stop prevents new attempts, but an active attempt may finish. Restart waits for that attempt to finish and takes a fresh baseline. Current-run results survive monitor stop/start, but not a backend process restart.
- Model scores include every configured candidate and are independent sigmoid scores, **not correctness percentages**. Fixed thresholds are 0.80 top score and 0.20 top-two gap. One topic still requires 0.80; uncertainty suggests NeedsReview, with no movement.
- Opening-excerpt results visibly disclose truncation. The complete schema/prefix/specials/excerpt fits at most 512 encoded tokens, with a 64 KiB opening read. Long-document quality remains unvalidated. Invalid UTF-8, unusable text, reading/inference failures, empty topic configuration, and over-budget schemas produce explicit errors, never fake success.
- Once the model is ready, saving an over-budget schema returns HTTP 422 without replacing settings. Before readiness, exact tokenizer-budget validation is deferred to processing; the first affected attempt reports any budget failure explicitly.

Public operations: `GET /health`, `GET /settings`, `PUT /settings`, `POST /monitor/start`, `POST /monitor/stop`, `GET /status`, and `GET /results`. The single-page dashboard polls status/results every second. Results show filename, suggestion, all available scores, captured categories, excerpt/token metadata, and failure reasons. No document contents or filenames leave the local application.

## Checks

```sh
uv lock --check
uv run --extra test pytest -W error
(cd frontend && npm run check && npm run build)
```

These checks do not install, download, or initialize model dependencies or weights. For separate model validation only, install the optional extra and run the documented smoke script:

```sh
uv sync --extra model-check --python 3.12
uv run --extra model-check --python 3.12 python scripts/model_smoke.py
```

The first model check downloads the real checkpoint; see `.scratch/mvp-readiness/spec.md` for the baseline observed model outcome and limitations. For the independent 12-document, non-moving acceptance run (requires cached weights):

```sh
uv run --extra model-check --python 3.12 python scripts/model_acceptance.py --output /tmp/model-acceptance-results.json
```

See [model acceptance](docs/model-acceptance.md) and the [recorded real results](docs/model-acceptance-results.json) for candidate-score semantics, thresholds, CPU latency, and the approved Unicode-safe opening-excerpt policy. The user authorized excerpt-based automatic topic/NeedsReview movement at the same thresholds, with visible truncation disclosure; long-document quality is unvalidated. `backend/model_input.py` bounds opening reads to 64 KiB and fits the complete prompt to 512 encoded tokens without modifying source contents. The acceptance run verifies this preparation offline and never moves documents. Confidence values are not calibrated probabilities. This setup was exercised on the current macOS machine; clean-install reproducibility and Ubuntu compatibility are not claimed.
