# Saved verification evidence

This directory holds intentionally committed acceptance reports and raw results for particular milestones. They are historical evidence, not application configuration, user history, or automatically refreshed test output.

- `download-classify-mvp/`: model-only and completed API/monitor/movement acceptance reports, with their raw JSON. Original observations and JSON data are preserved.
- Maintained commands and policies belong in `docs/model-validation.md` and `docs/demo-validation.md`.
- Executable validation belongs in `scripts/`; labeled inputs belong in `fixtures/`.

Write routine rerun output to `/tmp` as documented in the guides. Only commit new reports deliberately, with execution provenance and limitations; do not overwrite a saved milestone just because tests were rerun. Temporary screenshot paths in existing reports may no longer exist.
