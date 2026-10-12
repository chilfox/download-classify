# Download Classify - local readiness baseline

The app is a minimal local connectivity baseline, not the organizer. The API health response means only that the API is available; it does not indicate model readiness or document-classification functionality.

## Prerequisites

Install [uv](https://docs.astral.sh/uv/) and Node.js/npm. Python 3.12 is managed by uv. From the repository root:

```sh
uv python install 3.12
uv sync --extra test --python 3.12
(cd frontend && npm ci)
```

## Run locally

In separate terminals, from the repository root:

```sh
uv run --extra test uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

```sh
cd frontend && npm run dev
```

Open http://127.0.0.1:5173. The frontend proxies `/health` to the API at http://127.0.0.1:8000/health. API and frontend bind to loopback only. Stop the API to see the visible connection-error state.

## Baseline checks

```sh
uv run --extra test pytest
cd frontend && npm run check && npm run build
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

See [model acceptance](docs/model-acceptance.md) and the [recorded real results](docs/model-acceptance-results.json) for candidate-score semantics, thresholds, CPU latency, and the input-policy decision pending user approval. The acceptance run is offline and never moves documents. Confidence values are not calibrated probabilities. This setup was exercised on the current macOS machine; clean-install reproducibility and Ubuntu compatibility are not claimed.
