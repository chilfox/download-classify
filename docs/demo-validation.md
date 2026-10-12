# Complete macOS workflow validation guide

## Purpose and commands

Validate the completed public API, real background monitoring, local model and actual filesystem movement together. From the repository root:

```sh
uv sync --extra model-check --extra test --python 3.12
(cd frontend && npm ci)
# Initial weight download is permitted during setup.
uv run --extra model-check python scripts/model_smoke.py
uv run --extra model-check --extra test python scripts/demo_acceptance.py \
  --output /tmp/download-classify-demo-results.json
uv lock --check
uv run --extra test pytest -W error
(cd frontend && npm run check && npm run build)
```

The macOS-only driver uses FastAPI TestClient with the real application lifespan, serial monitor and cached model, without substituting model inference. It creates, prints and retains a fresh disposable folder. Never use real Downloads or existing user documents. Match the category descriptions in `fixtures/model-acceptance/manifest.json` to reproduce the fixture workflow. Missing model weights fail the run rather than silently activating a fallback.

## What to verify

- Report top-topic prediction accuracy and automatic topic-movement coverage separately. Verify uncertain classification reaches NeedsReview, not a forced topic.
- Supported files sharing an extension can reach different topic folders. Verify original bytes after every move, collision preservation, and original/destination/time/result JSONL records.
- Unsupported PDF/ZIP files remain untouched with explanatory results. Suggestions-only results must leave sources untouched and create no movement records.
- Existing-file and restart baselines, unchanged-file deduplication, exclusions, stability, source-change retry, captured settings, and stop-during-processing behavior are covered through the public API plus temporary filesystem tests. Timing-critical cases replace only the model boundary; they are not model-quality evidence.
- Independently run [model validation](model-validation.md) for score/input-budget semantics and labeled model quality. API health and deterministic tests do not replace it.

## Desktop browser acceptance

Follow the isolated startup instructions in [README](../README.md), using separate terminals for backend and frontend. Verify category editing/saving and visible validation errors, start/stop controls, model readiness, monitoring/in-flight status, current-run outcomes, model-score labels, destination/trace status, and excerpt disclosures. Stop the backend to verify a visible connection error and stale-data warning.

Inspect desktop typography, alignment, wrapping and overflow. Mobile layouts and mobile acceptance are out of scope. A manual/headless desktop pass is sufficient; no full browser E2E framework is required. Stop verification services afterward. NeedsReview is handled manually in Finder; there is no undo or automatic restoration.

## Evidence and limitations

Saved MVP observations are in [the complete acceptance report](../test-results/download-classify-mvp/demo-acceptance.md) and [raw API/filesystem results](../test-results/download-classify-mvp/demo-acceptance.json). They record a particular execution, not current runtime state. Absolute temporary paths and screenshot pointers are provenance, not portable instructions or permanent artifact guarantees.

Automatic movement is verified only on the current macOS machine. No production-safety, Ubuntu-compatibility or clean-install claims. Stability scans are a heuristic, not protection against hostile writers. Excerpt-based automatic movement is approved and visibly disclosed, but long-document quality remains unvalidated. Keep sample documents disposable.
