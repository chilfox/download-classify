# User guide

This guide explains how to configure categories, monitor a dedicated folder, and interpret results in Download Classify.

## Before you begin

Download Classify is a local macOS application for new TXT and Markdown documents. It uses a local GLiNER2 model and does not send document contents or filenames to cloud services.

Use a dedicated folder containing disposable test files. Automatic mode is enabled by default and moves files after classification. The app never deletes or overwrites documents, but it has no undo or automatic restoration. Do not point it at your real Downloads folder or files you are actively editing.

For first-time installation and startup, follow [Try it locally](../README.md#try-it-locally).

## Configure categories

1. Open the local dashboard.
2. Add one or more categories, each with a name and a description that explains the topic.
3. Save the categories before starting monitoring.

There must be between 1 and 50 categories. Names must be unique and valid as folder names. `NeedsReview` is reserved for uncertain results. Descriptions can be up to 2,000 characters. Category descriptions help the model distinguish topics; they are not guarantees of classification quality.

Settings are saved locally. By default, they are stored at `~/.download-classify/categories.json`; the `DOWNLOAD_CLASSIFY_SETTINGS_PATH` environment variable changes this location.

## Monitor a folder

1. Make sure the configured folder exists and is the dedicated test folder you intend to use.
2. Select **Start monitoring** in the dashboard.
3. Wait for the local model to load and show its ready state.
4. Add a new TXT or Markdown document directly into the monitored folder.
5. Review its result in the dashboard and inspect the destination folder when it is moved.
6. Select **Stop monitoring** when done.

Starting or restarting monitoring establishes a baseline of files already in the folder. Those existing files are ignored. Only new regular files directly inside the folder are considered; nested folders are not scanned. Temporary download names and symlinks are excluded. A file must have an unchanged size and modification time across consecutive scans before processing, which is a practical completion heuristic rather than a guarantee that a download has finished.

The monitor processes files serially. Stop prevents new attempts, but an active attempt may finish. Wait for it to finish before restarting.

## Understand results

- **Topic name / `moved`:** The model selected a topic and the file was moved into that topic's folder.
- **`NeedsReview`:** The result was uncertain and, in automatic mode, the file was moved into `NeedsReview`. Review it manually in Finder.
- **`skipped`:** The file format is unsupported and the file was left untouched. Only `.txt`, `.md`, and `.markdown` files are supported. PDFs and other formats are not processed.
- **`failed`:** Processing failed. The source is left untouched. The result includes an explanation where available.
- **Movement trace:** Successful moves are recorded locally as JSON Lines beside the settings file by default. A recording error is shown separately; it does not undo a completed move.

The dashboard shows current-process results only. Results do not persist after the backend restarts. There is no history API or retry button. Unchanged files, including failed attempts, are not repeatedly processed during the same monitoring run.

### Scores and excerpts

Scores are independent model scores, not probabilities that a classification is correct. A topic is considered clear when the top score is at least `0.65` and, when there is a second candidate, the gap between the top two scores is at least `0.10`. A single-category setup still requires a score of at least `0.65`.

The model considers a bounded opening excerpt, not necessarily the whole document. The dashboard discloses when the text was truncated. Quality on long documents has not been validated. Do not interpret a high score as a guarantee.

## Suggestions-only mode

To disable movement, start the backend with `DOWNLOAD_CLASSIFY_MODE=suggestions-only`. The dashboard then displays suggestions without moving files. This mode does not make model failures into suggestions: missing weights or inference failures remain failures.

## Connection problems

The dashboard polls the API periodically. If the backend cannot be reached, it displays a connection error and warns that shown status or results may be stale. Confirm that the backend terminal is still running, then reload or wait for polling to recover.

The API health check only reports that the API is available; model readiness is shown separately in the dashboard.
