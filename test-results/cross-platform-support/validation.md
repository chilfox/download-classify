# Cross-platform support validation

Execution date: 2026-10-12. Scope: `.scratch/cross-platform-support/spec.md`.

## Implemented support

Automatic movement uses macOS `renameatx_np(RENAME_EXCL)` or Linux libc `renameat2(RENAME_NOREPLACE)`, with the same verified directory descriptors, source signatures, symlink rejection, and collision retries. There is no overwrite-capable or copy/delete fallback. Missing runtime, kernel, or filesystem capabilities fail safely with suggestions-only guidance. Numbered collision filenames reserve space within the destination's filename limit, including for multibyte stems.

Native Windows is excluded because document opening and directory traversal require POSIX facilities (`O_NOFOLLOW`, directory descriptors, and descriptor-relative operations). Windows dependency installation was not verified; this is not a claim that every dependency is incompatible with Windows.

## macOS evidence

- macOS 26.5.2, build 25F84, Darwin 25.5.0, arm64; Python 3.12.11.
- `uv lock --check`: passed without dependency or lockfile changes.
- `uv run --extra test pytest -W error`: 82 passed. Fixed-score integration tests isolate filesystem behavior, not model quality. Coverage includes TXT/Markdown/PDF, topic and NeedsReview movement, suggestions-only, collisions and competing destination creation, symlinks and unsafe directories, source/root changes, and movement recording failures.
- `(cd frontend && npm run check && npm run build)`: passed.
- `bash -n run-demo.sh`: passed. Actual launcher startup returned HTTP 200 from backend `/status` on port 8000 and frontend `/` on port 5173. Sending SIGTERM exited the launcher with status 143, stopped both services, and retained the disposable directory. No frontend behavior or API contract changed.
- `uv run --extra test --extra model-check python scripts/demo_acceptance.py --output /tmp/download-classify-cross-platform-macos.json`: passed with the real local CPU model and cached weights. 11/12 fixture predictions correct; 11 correct topic moves and 1 NeedsReview move. Original bytes and 12 movement records verified, existing/colliding/unsupported files retained, stopped arrivals ignored, and suggestions-only retained the source. This is fixture evidence, not a general model-quality claim.

## Linux evidence

Actual Linux validation is recorded below after execution; macOS results and mocked syscall failures do not establish Linux runtime acceptance.

## Limits

The failure-boundary tests simulate unavailable libc symbols and unsupported operations on both platform branches; they establish safe failure behavior, not execution of Linux syscalls. No native Windows execution, universal kernel/filesystem support, hostile-writer protection, desktop packaging, or clean-install reproducibility claim is made. Real-model runs may emit existing dependency warnings; ordinary Python tests run with warnings as errors. Disposable paths in raw artifacts are provenance, not portable instructions.
