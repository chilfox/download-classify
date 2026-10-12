## Project introduction

Download Classify is a small local app that keeps downloaded documents organized by topic rather than file extension. Development and acceptance take place on the current macOS MacBook. Users define categories with names and descriptions in a local web dashboard. A local GLiNER2 multilingual model reads newly arriving documents and moves them into category folders. Uncertain classifications go to `NeedsReview`; unsupported files and processing failures stay untouched.

This is a two-hour hackathon MVP, not a production file manager. Use disposable documents in a dedicated test folder for demos. Ubuntu compatibility is not part of this MVP's acceptance criteria and has not been verified. Support text-based PDF, TXT, and Markdown only. Keep document contents local, never delete or overwrite files, and avoid adding features beyond the agreed scope.

The stack is React + TypeScript + Vite for the frontend and Python + FastAPI for the backend. The implementation spec is `.scratch/download-classify-mvp/spec.md`.

## Session start

Before implementation, read `README.md` and the relevant specification, inspect `git status`, and run the documented baseline checks. For documentation-only changes, checks may be skipped with an explicit reason. Do not regenerate the scaffold or reinstall dependencies unnecessarily.

## Testing and verification

Run from the repository root after implementation (setup commands are in `README.md`):

```sh
uv lock --check
uv run --extra test pytest -W error
(cd frontend && npm run check && npm run build)
```

The pytest test exercises the public HTTP health API without model weights or inference. Frontend checks verify types and compilation, not browser connectivity. For connectivity changes, start both services using the README commands and open `http://127.0.0.1:5173`: confirm `API status: ok`, then stop the backend and reload to confirm a visible `Connection error`.

Run real-model validation separately, only when model integration changes or its feasibility needs rechecking:

```sh
uv run --extra model-check --python 3.12 python scripts/model_smoke.py
```

This may download weights. Record actual outputs and limitations; API health and passing stub-free baseline tests do not establish model quality or organizer completion. Current readiness evidence is in `.scratch/mvp-readiness/spec.md`.

## Agent skills

### Issue tracker

Issues and specs live as markdown files under `.scratch/<feature>/`. See `docs/agents/issue-tracker.md`.

### Domain docs

single-context. See `docs/agents/domain.md`.
