# Download Classify

Download Classify is a local app that organizes new TXT, Markdown, and text-based PDF documents by topic. Define topic categories in the web dashboard, then let a local GLiNER2 model classify new files in a folder you choose.

Clear classifications move into their topic folders. Uncertain classifications move to `NeedsReview`. Unsupported files and processing failures stay where they are.

> **Safety:** Automatic movement is the default. Try the app only with disposable documents in a dedicated folder, not your real Downloads folder. The app does not delete or overwrite files and has no undo feature. Document contents stay local. See the [user guide](docs/user-guide.md) before using it.

## Try it locally

Requires macOS or Linux, [uv](https://docs.astral.sh/uv/), and Node.js/npm. Python 3.12 is managed by uv. On Linux, automatic movement requires a libc exposing `renameat2` and a kernel/filesystem supporting `RENAME_NOREPLACE`; if unavailable, movement fails safely and leaves the source in place. Native Windows is not supported because runtime file handling depends on POSIX APIs. From the repository root:

```sh
uv python install 3.12
uv sync --extra model-check --python 3.12
(cd frontend && npm ci)
```

Create a dedicated disposable inbox:

```sh
DEMO=$(mktemp -d "${TMPDIR:-/tmp}/download-classify-demo.XXXXXX")
mkdir "$DEMO/inbox"
echo "Demo folder: $DEMO"
```

In one terminal, start the backend, substituting the printed path for `<demo-folder>`:

```sh
DOWNLOAD_CLASSIFY_FOLDER="<demo-folder>/inbox" \
DOWNLOAD_CLASSIFY_SETTINGS_PATH="<demo-folder>/categories.json" \
DOWNLOAD_CLASSIFY_MOVEMENT_LOG="<demo-folder>/movements.jsonl" \
  uv run --extra model-check uvicorn backend.app:app --host 127.0.0.1 --port 8000 --workers 1
```

In another terminal:

```sh
cd frontend && npm run dev
```

Open the URL printed by Vite, normally <http://127.0.0.1:5173>. Save categories in the dashboard and select **Start monitoring** before adding files. Only new, stable, root-level files are considered. Files present when monitoring starts are ignored. The model downloads its checkpoint the first time it is needed. Stop both services with Ctrl-C when finished.

For detailed setup, usage, supported-file behavior, and safety limitations, read the [user guide](docs/user-guide.md).

## Documentation

- [User guide](docs/user-guide.md) - configure categories, monitor a folder, and understand results.
- [Development guide](docs/development.md) - develop, run checks, and validate changes.
- [Architecture](docs/architecture.md) - understand the app's components and processing flow.
- [API reference](docs/api-reference.md) - endpoint and data contract reference.
- [Workflow validation](docs/demo-validation.md) - validate the full workflow with disposable fixtures.
- [Model validation](docs/model-validation.md) - independently validate the local model and its input policy.

## Project checks

From the repository root:

```sh
uv lock --check
uv run --extra test pytest -W error
(cd frontend && npm run check && npm run build)
```

These checks do not download or initialize model weights. Real-model checks and the full disposable workflow are documented in the [development guide](docs/development.md) and their dedicated validation guides.
