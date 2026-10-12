# Architecture

Download Classify is a local web application with a React + TypeScript + Vite frontend and a Python + FastAPI backend. The backend owns settings, model lifecycle, monitoring, classification, and optional filesystem movement.

## Components

- **Dashboard (`frontend/`)** edits topic categories, controls monitoring, and polls the backend for status and current-run results. Vite proxies API requests to the local backend during development.
- **FastAPI application (`backend/app.py`)** exposes settings, health, monitor control, status, and results operations. It loads category settings and creates the monitor for the configured folder.
- **Monitor (`backend/monitor.py`)** runs one serial background worker. It establishes a baseline when monitoring starts, scans the monitored folder, waits for stable file metadata, and coordinates classification and result recording.
- **Model and input preparation (`backend/model.py`, `backend/model_input.py`)** load the local GLiNER2 model and prepare a bounded, Unicode-safe opening excerpt. Model weights are local; document content is not sent to a cloud service.
- **Decision and movement (`backend/classification.py`, `backend/movement.py`)** apply the shared score thresholds and, in automatic mode, move clear results into topic folders and uncertain successful classifications into `NeedsReview`.

## Processing lifecycle

1. Starting monitoring verifies that the configured folder exists and is not a symlink. The monitor captures the folder identity and names already present as a baseline.
2. Subsequent scans consider new regular root-level files. Temporary download entries, symlinks, subdirectories, and the configured movement trace are excluded.
3. A file is eligible after its size and modification time remain unchanged across consecutive scans. This is a completion heuristic, not a transactional guarantee.
4. For supported files (`.txt`, `.md`, `.markdown`, `.pdf`, case-insensitive), the monitor captures the current categories and reads a bounded opening. PDFs are parsed locally in memory with `pypdf` (`>=6.20,<7`); the resulting text is passed through the existing model-input and scoring path.
5. A top score of at least `0.65` and a top-two gap of at least `0.10` define a clear result. A single category requires the same minimum score but has no runner-up gap. Scores are independent sigmoid scores, not calibrated correctness probabilities.
6. Automatic mode moves clear results to the selected topic and uncertain results to `NeedsReview`. Suggestions-only mode leaves all sources untouched. Unsupported files and processing failures also remain untouched.
7. Successful moves are recorded in a local JSONL trace. A trace failure is reported independently and does not reverse the move.

The worker is serial and runs in one backend process. The app is not designed for multiple worker processes. Status and result requests are served separately from model inference. Stopping monitoring prevents new attempts but allows an active attempt to finish.

## Filesystem and data boundaries

Movement is macOS-only and uses an exclusive, descriptor-relative rename that refuses existing destinations. Collisions receive numbered filenames; the app has no overwrite-capable fallback. It verifies source and directory identities around movement and rejects symlink paths. These safeguards do not make monitoring transactional against hostile local writers or directory relocation in the final system-call window.

TXT/Markdown reads are bounded to a 64 KiB opening. PDF extraction considers at most 20 pages and retains at most 64 KiB UTF-8 extracted text; sources over 10 MiB, decoded streams over 1 MiB, or combined page content over 1 MiB fail. Reaching page or text prefix limits yields disclosed partial text; no text within limits means unread pages may still contain text. There is no hard time or memory guarantee. The complete prompt, schema, and special tokens remain within the existing 512-token budget. Truncation is disclosed. PDF reading order/font mappings can be imperfect, and long-document classification quality is unvalidated. PDFs use no OCR, and extraction creates no text files; movement preserves the original PDF. Original file contents are not modified; the app does not delete files.

Monitoring results are in-memory for the lifetime of the backend process. The movement trace is a record of successful moves, not an undo mechanism or result-history API.

## Configuration

- `DOWNLOAD_CLASSIFY_FOLDER`: monitored folder; defaults to `~/DownloadClassifyDemo` and must exist before monitoring starts.
- `DOWNLOAD_CLASSIFY_SETTINGS_PATH`: category settings JSON; defaults to `~/.download-classify/categories.json`.
- `DOWNLOAD_CLASSIFY_MOVEMENT_LOG`: JSONL movement trace; defaults to `movements.jsonl` beside the settings file.
- `DOWNLOAD_CLASSIFY_MODE`: `automatic` by default, or `suggestions-only` to avoid movement.

See the [API reference](api-reference.md) for the service contract and the [user guide](user-guide.md) for user-visible behavior.
