## Project introduction

Download Classify is a small local app that keeps downloaded documents organized by topic rather than file extension. Development and acceptance target macOS and Linux; record which platforms have actually been exercised and do not infer Linux validation from macOS results. Native Windows is not supported; POSIX file opening and directory-relative movement are runtime blockers. Users define categories with names and descriptions in a local web dashboard. A local GLiNER2 multilingual model reads newly arriving documents and moves them into category folders. Uncertain classifications go to `NeedsReview`; unsupported files and processing failures stay untouched.

Use disposable documents in a dedicated test folder for demos. Support TXT, Markdown, and text-only PDF. PDF extraction is local, in memory, and has no OCR; preserve document contents locally, never delete or overwrite files, and avoid adding features beyond the agreed scope.

The stack is React + TypeScript + Vite for the frontend and Python + FastAPI for the backend.

## Session workflow

- Before editing, read `README.md` and the relevant spec; inspect `git status` and preserve unrelated changes.
- After code changes, run from the repository root:
  - `uv lock --check`
  - `uv run --extra test pytest -W error`
  - `(cd frontend && npm run check && npm run build)`
- For frontend/connectivity changes, verify success and connection-error states in a browser.
- Linux automatic movement requires libc `renameat2` and kernel/filesystem `RENAME_NOREPLACE`; unsupported environments must fail safely. Native Windows is out of scope because runtime document and directory operations require POSIX facilities.
- Use `${TMPDIR:-/tmp}` or Python's `tempfile` for disposable paths; do not treat `/tmp` as the only platform convention.
- For model-integration changes, run the independent real-model smoke check. Commands are in `README.md`; never treat API/test success as model-quality evidence.
- Documentation-only changes may skip checks with an explicit reason.

## Agent skills

### Issue tracker

Issues and specs live as markdown files under `.scratch/<feature>/`. See `docs/agents/issue-tracker.md`.

### Domain docs

single-context. See `docs/agents/domain.md`.
