# Development guide

This guide covers local setup, running the application, and project verification. The supported development and acceptance environment is the current macOS machine; this is not a claim of clean-install reproducibility or compatibility with other operating systems.

## Requirements and setup

Install Node.js/npm and [uv](https://docs.astral.sh/uv/). From the repository root:

```sh
uv python install 3.12
uv sync --extra test --python 3.12
(cd frontend && npm ci)
```

The ordinary backend/test dependencies do not install the model stack. To run with the real local model, install the optional extra:

```sh
uv sync --extra model-check --python 3.12
```

## Run the application

Use a dedicated disposable directory. Create it and its inbox:

```sh
DEMO=$(mktemp -d /tmp/download-classify-demo.XXXXXX)
mkdir "$DEMO/inbox"
echo "$DEMO"
```

In one terminal, from the repository root, set the three paths to the directory printed above:

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

Use the local Vite URL printed in the terminal. Do not use real Downloads or non-disposable documents. For frontend-only work, the ordinary frontend and API setup does not require model quality validation. Stop the services with Ctrl-C.

## Checks

Run from the repository root:

```sh
uv lock --check
uv run --extra test pytest -W error
(cd frontend && npm run check && npm run build)
```

These checks do not download, initialize, or assess model weights. Backend tests use a model boundary and are not evidence of model quality.

## Real-model validation

For model integration changes, run the independent real-model smoke check. The initial run downloads the checkpoint:

```sh
uv sync --extra model-check --python 3.12
uv run --extra model-check --python 3.12 python scripts/model_smoke.py
```

The smoke check verifies model loading and basic inference only. For labeled fixture evaluation without movement:

```sh
uv run --extra model-check --python 3.12 python scripts/model_acceptance.py \
  --output /tmp/model-acceptance-results.json
```

For a full workflow acceptance using the real monitor, API, model, and filesystem movement, use the [workflow validation guide](demo-validation.md). It is macOS-only and uses disposable fixtures. See the [model validation guide](model-validation.md) for score semantics, input constraints, and evidence limitations. Never treat API health or ordinary test success as model-quality evidence.

## Related technical documentation

- [Architecture](architecture.md)
- [API reference](api-reference.md)
- [Workflow validation](demo-validation.md)
- [Model validation](model-validation.md)
