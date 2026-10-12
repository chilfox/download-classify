# Download Classify - readiness setup

This repository currently contains a model-feasibility check, not the organizer application. The smoke check downloads and runs the real `fastino/gliner2-multi-v1` checkpoint locally; it does not start or depend on an application service. Model weights and document text stay local after the permitted initial checkpoint download.

## Install the model-check environment

Requires macOS and [uv](https://docs.astral.sh/uv/). Python 3.12 is installed/selected by uv:

```sh
uv python install 3.12
uv sync --python 3.12
```

## Run the real model check

```sh
uv run --python 3.12 python scripts/model_smoke.py
```

This uses CPU inference and prints raw category candidates/confidences for one Traditional Chinese and one English sample. The first run downloads model weights and may take several minutes. Confidence values are model scores, not calibrated probabilities; do not infer that scores sum to one. The smoke check is deliberately separate from ordinary tests and application startup.

The local environment (`.venv`) and model/cache/runtime artifacts are excluded from version control. Only macOS local setup is in scope; Ubuntu compatibility and fresh-machine reproducibility have not been verified.
