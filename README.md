# Download Classify - local automatic organization

This app monitors newly arriving TXT/Markdown documents and uses local GLiNER2 scores to move clear classifications into one topic folder and uncertain classifications into `NeedsReview`. **Automatic mode is the default and is approved only for a disposable demo folder.** File contents are never modified, documents are never overwritten, and there are no deletion or undo features. Set `DOWNLOAD_CLASSIFY_MODE=suggestions-only` for the explicitly labeled non-moving fallback. The API health response means only that the API is available; model readiness is reported separately.

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
DEMO=$(mktemp -d /tmp/download-classify-demo.XXXXXX)
mkdir "$DEMO/inbox"
echo "Disposable demo: $DEMO"
DOWNLOAD_CLASSIFY_FOLDER="$DEMO/inbox" \
DOWNLOAD_CLASSIFY_SETTINGS_PATH="$DEMO/categories.json" \
DOWNLOAD_CLASSIFY_MOVEMENT_LOG="$DEMO/movements.jsonl" \
  uv run --extra model-check uvicorn backend.app:app --host 127.0.0.1 --port 8000 --workers 1
```

```sh
cd frontend && npm run dev
```

Open the URL printed by Vite (normally http://127.0.0.1:5173). The frontend proxies settings, monitoring, status, results, and health to the API at http://127.0.0.1:8000. API and frontend bind to loopback only. Stop the API to see the visible connection-error and stale-data state.

Save topic categories, explicitly start monitoring, then add disposable documents. The model loads once on the background worker, using cached weights only with telemetry disabled. The folder defaults to `~/DownloadClassifyDemo` if `DOWNLOAD_CLASSIFY_FOLDER` is unset and must exist before starting. Settings default to `~/.download-classify/categories.json`; override with `DOWNLOAD_CLASSIFY_SETTINGS_PATH` for disposable runs.

## Monitoring behavior and API

- One backend process with **one worker** and one serial processing thread. Status requests stay responsive during loading/inference; shutdown stops new work and waits for the active attempt to finish.
- Every start/restart establishes an existing-entry baseline. Only new regular root files with unchanged size and modification time across consecutive scans (one-second interval) are considered. This is a completion heuristic, not a guarantee a downloader has finished.
- Subdirectories, symlinks, hidden/`~$` entries, and `.crdownload`, `.part`, `.partial`, `.download`, `.tmp`, `.temp` suffixes are excluded. All PDFs and other unsupported formats are reported and left untouched. Source reads reject symlinks at open time.
- Settings are captured per attempt. Source changes during reading/inference discard the stale result and require fresh stability before retry. Unchanged files, including failures, are not repeatedly processed. There is no manual retry feature.
- Stop prevents new attempts, but an active attempt may finish. Restart waits for that attempt to finish and takes a fresh baseline. Current-run results survive monitor stop/start, but not a backend process restart.
- Model scores include every configured candidate and are independent sigmoid scores, **not correctness percentages**. Fixed thresholds are 0.80 top score and 0.20 top-two gap. One topic still requires 0.80. Automatic mode moves clear classifications into the captured topic folder and successful uncertain classifications into NeedsReview. Suggestions-only mode leaves every source untouched; missing model weights remain a failure, never a fake suggestion.
- Movement is macOS-only: descriptor-relative `renameatx_np(RENAME_EXCL)` atomically refuses existing destinations, including late collisions and symlinks. Collisions use numbered filenames. Directory opens reject symlinks in every path component, verify the monitored root identity and destination binding, and recheck source identity/size/mtime/ctime immediately before each rename. There is no overwrite-capable fallback. Root-only scanning excludes destination folders and the configured movement trace.
- Successful movements append original/destination/time/result to `movements.jsonl` beside settings; override with `DOWNLOAD_CLASSIFY_MOVEMENT_LOG` using a `.jsonl` path. Trace opens reject symlinks, non-regular files, hard links, and the moved document's inode. Results distinguish `moved`, `needs-review`, `skipped` (unsupported), `failed`, and `suggestion-only`. A recording failure reports the completed destination and a separate visible error; it does not claim the trace was saved or undo the move. Results survive monitoring stop/start, not process restart; there is no history API.
- Stability checks are a practical heuristic, not transactional protection against a hostile local process. A writer retaining an open descriptor can keep writing after rename, and a process relocating directories in the final syscall window cannot be fully excluded. Use completed disposable downloads in the dedicated demo folder, not actively edited files or real Downloads.
- Opening-excerpt results visibly disclose truncation. The complete schema/prefix/specials/excerpt fits at most 512 encoded tokens, with a 64 KiB opening read. Long-document quality remains unvalidated. Invalid UTF-8, unusable text, reading/inference failures, empty topic configuration, and over-budget schemas produce explicit errors, never fake success.
- Once the model is ready, saving an over-budget schema returns HTTP 422 without replacing settings. Before readiness, exact tokenizer-budget validation is deferred to processing; the first affected attempt reports any budget failure explicitly.

Public operations: `GET /health`, `GET /settings`, `PUT /settings`, `POST /monitor/start`, `POST /monitor/stop`, `GET /status`, and `GET /results`. The single-page dashboard polls status/results every second. Results show filename, operating mode, classification, destination, recording status, all available scores, captured categories, excerpt/token metadata, and failure reasons. No document contents or filenames leave the local application.

## Repeatable disposable demo and completed-workflow acceptance

After caching the model, run from the repository root:

```sh
uv sync --extra model-check --extra test --python 3.12
uv run --extra model-check --extra test python scripts/demo_acceptance.py \
  --output /tmp/download-classify-demo-results.json
```

This macOS-only driver uses the public backend API in-process with its real background monitor and real local model, not a stub or a direct classification-only call. It creates a fresh disposable folder, saves the four fixture categories, starts monitoring, and adds the 12 labeled English/Traditional Chinese TXT/Markdown fixtures. It checks actual topic/NeedsReview moves, all original bytes, collision preservation, unsupported PDF/ZIP bytes and explanations, unchanged-file deduplication, start/restart baselines, and 12 persistent JSONL records. It also explicitly runs a real-model suggestions-only attempt and checks that its source stays untouched. Model failure is a failed run, never a hidden fallback. The printed temporary folder is retained for inspection; remove only that disposable folder yourself when finished.

The recorded completed-workflow run achieved **11/12 correct predictions**, **11/12 automatic topic-movement coverage**, all 11 topic moves correct, and one actual NeedsReview move. See [complete demonstration acceptance](docs/demo-acceptance.md) and [raw API/filesystem results](docs/demo-acceptance-results.json). This script does not replace the independent smoke/input-budget checks or the deterministic monitoring-safety tests.

For a desktop presentation, start the services above, edit/save categories in the dashboard (the exact acceptance descriptions are in `fixtures/model-acceptance/manifest.json`), click **Start monitoring**, wait for model **ready**, then copy disposable fixture files into the displayed inbox. Files already present when starting are intentionally ignored. The default Work/Personal/Research examples differ from the acceptance categories and need not reproduce the recorded scores. Observe topic destinations, an uncertain NeedsReview result, and a disposable PDF's unsupported explanation; click **Stop monitoring** when finished. Stop the backend to demonstrate the visible connection error and stale-data warning. Use Finder to inspect and manually handle NeedsReview documents. There is **no undo or automated restoration**; the JSONL trace is a movement record, not an undo feature. Stop both terminal processes with Ctrl-C.

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
