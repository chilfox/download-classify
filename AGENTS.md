## Project introduction

Download Classify is a small local app that keeps downloaded documents organized by topic rather than file extension. Development and acceptance take place on the current macOS MacBook. Users define categories with names and descriptions in a local web dashboard. A local GLiNER2 multilingual model reads newly arriving documents and moves them into category folders. Uncertain classifications go to `NeedsReview`; unsupported files and processing failures stay untouched.

This is a two-hour hackathon MVP, not a production file manager. Use disposable documents in a dedicated test folder for demos. Ubuntu compatibility is not part of this MVP's acceptance criteria and has not been verified. Support text-based PDF, TXT, and Markdown only. Keep document contents local, never delete or overwrite files, and avoid adding features beyond the agreed scope.

The stack is React + TypeScript + Vite for the frontend and Python + FastAPI for the backend. The implementation spec is `.scratch/download-classify-mvp/spec.md`.

## Agent skills

### Issue tracker

Issues and specs live as markdown files under `.scratch/<feature>/`. See `docs/agents/issue-tracker.md`.

### Domain docs

single-context. See `docs/agents/domain.md`.
