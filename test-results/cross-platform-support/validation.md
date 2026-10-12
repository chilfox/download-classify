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

The independent `uv run --extra model-check python scripts/model_smoke.py` also passed on macOS (loading and basic inference only). Full macOS workflow scores and movement outcomes are preserved in [the raw report](macos-demo-acceptance.json).

## Linux evidence

Linux validation was started in Docker but cancelled at the user's request before a completed report was received. No Linux execution result is included as acceptance evidence. The user explicitly waived further Linux validation for this implementation. Linux support is implemented but not runtime-accepted by this report; macOS results and mocked syscall failures do not establish Linux runtime acceptance.

## Review

Two independent reviews compared the implementation with starting commit `a3b01f3c376b2f6e478ac4f27f0383d6a83f6215`.

- Standards: no hard violations; non-blocking heuristics concerned syscall selection and repeated fixture setup. The platform-specific artifact name intentionally identifies the environment behind the evidence.
- Spec: Linux evidence was pending at review time and was subsequently waived by the user. The reviewer also flagged collision-stem shortening as a possible policy addition. It is retained to preserve the spec's numbered, byte-preserving collision behavior at a genuine filesystem limit, not to add a new organization policy. An added ASCII maximum-length integration case reproduced the failure even on macOS before the fix; the existing multibyte case exercises the corresponding Linux byte-limit difference. Ordinary names and collision numbering remain unchanged.

## Limits

The failure-boundary tests simulate unavailable libc symbols and unsupported operations on both platform branches; they establish safe failure behavior, not execution of Linux syscalls. No native Windows execution, universal kernel/filesystem support, hostile-writer protection, desktop packaging, or clean-install reproducibility claim is made. Real-model runs may emit existing dependency warnings; ordinary Python tests run with warnings as errors. Disposable paths in raw artifacts are provenance, not portable instructions.
