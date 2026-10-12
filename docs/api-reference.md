# API reference

The FastAPI service is intended for local use. During frontend development, Vite proxies API requests to `http://127.0.0.1:8000`. The API does not provide authentication; bind it to loopback as shown in the development instructions.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Report API availability. Does not indicate model readiness. |
| `GET` | `/settings` | Return saved categories, or defaults if no settings file exists. |
| `PUT` | `/settings` | Validate and save categories. |
| `POST` | `/monitor/start` | Establish a baseline and start monitoring. |
| `POST` | `/monitor/stop` | Stop scheduling new attempts. An active attempt may finish. |
| `GET` | `/status` | Return monitoring, model, and configuration status. |
| `GET` | `/results` | Return current-process results. |

## Settings

`GET /settings` returns an object with a `categories` array:

```json
{
  "categories": [
    {"name": "Work", "description": "Work documents and projects"}
  ]
}
```

`PUT /settings` accepts the same shape and returns the validated settings. There must be 1 to 50 categories. A name is required, limited to 120 characters, and must be a valid unique folder name; `NeedsReview` is reserved. Descriptions are limited to 2,000 characters. Invalid settings return HTTP 422. If the ready model rejects a schema that exceeds its input budget, the request returns HTTP 422 and saved settings remain unchanged. Before model readiness, exact tokenizer-budget validation is deferred to processing.

If no settings file exists, the API returns the default Work, Personal, and Research categories. The path is selected by `DOWNLOAD_CLASSIFY_SETTINGS_PATH`, defaulting to `~/.download-classify/categories.json`.

## Monitor control

`POST /monitor/start` and `POST /monitor/stop` take no request body. Start returns the status representation described below. It returns HTTP 422 if the configured folder is not an existing non-symlink directory or an attempt is still finishing.

Stop prevents new attempts but does not cancel an active classification or movement. Starting or restarting takes a fresh baseline, so files already present are ignored.

## Status response

`GET /status` returns an object with these fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `folder` | string | Configured monitored folder. |
| `monitoring` | boolean | Whether scans are active. |
| `processing` | string or null | Filename of the active attempt, if any. |
| `model_status` | string | Model lifecycle state, such as `not-loaded`, `loading`, `ready`, or `unavailable`. |
| `model_error` | string or null | Model loading error, if any. |
| `monitor_error` | string or null | Monitor scanning error, if any. |
| `movement_enabled` | boolean | Whether automatic movement is enabled. |
| `mode` | string | `automatic` or `suggestions-only`. |

`GET /health` only confirms the API responds; check `model_status` separately for readiness.

## Results response

`GET /results` returns an array of result objects accumulated by the current backend process. Results are cleared by process restart and are not a durable history. Fields include:

| Field | Type | Meaning |
| --- | --- | --- |
| `filename` | string | Source filename. |
| `outcome` | string | `moved`, `needs-review`, `skipped`, `failed`, or `suggestion-only`. |
| `suggestion` | string or null | Selected topic or `NeedsReview`, when available. |
| `mode` | string | Operating mode captured for the attempt. |
| `destination` | string or null | Destination path after a successful move. |
| `recorded` | boolean or null | Whether a successful movement was recorded in the JSONL trace. |
| `recording_error` | string or null | Error recording a completed movement. Does not imply the move was undone. |
| `scores` | object or null | Independent score for each configured category. |
| `reason` | string or null | Explanation, including unsupported format or processing failure. |
| `truncated` | boolean or null | Whether the bounded opening was truncated. |
| `encoded_tokens` | integer or null | Encoded input token count when available. |
| `categories` | object or null | Category names and descriptions captured for this attempt. |
| `top_two_gap` | number or null | Difference between the top two scores when available. |

Scores are not correctness probabilities. The decision thresholds and bounded-input behavior are described in the [architecture](architecture.md) and [model validation guide](model-validation.md).

## Configuration and errors

The backend reads these environment variables at startup:

- `DOWNLOAD_CLASSIFY_FOLDER`: monitored directory; defaults to `~/DownloadClassifyDemo`.
- `DOWNLOAD_CLASSIFY_SETTINGS_PATH`: settings JSON path; defaults to `~/.download-classify/categories.json`.
- `DOWNLOAD_CLASSIFY_MOVEMENT_LOG`: movement trace path; defaults to `movements.jsonl` beside settings.
- `DOWNLOAD_CLASSIFY_MODE`: `automatic` by default, or `suggestions-only`.

The backend must use one worker process. Automatic filesystem movement is supported on macOS and Linux. On Linux, libc must expose `renameat2` and the kernel/filesystem must support `RENAME_NOREPLACE`; otherwise movement fails safely without moving the source. Native Windows is not supported because runtime file and directory handling uses POSIX operations. See the [development guide](development.md) for startup and verification commands.
