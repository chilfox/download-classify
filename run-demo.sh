#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

for command in uv npm; do
  if ! command -v "$command" >/dev/null 2>&1; then
    printf 'Missing required command: %s\nInstall uv and Node.js/npm, then run this script again.\n' "$command" >&2
    exit 1
  fi
done

OS="$(uname -s)"
if [[ "$OS" != "Darwin" && "$OS" != "Linux" ]]; then
  printf 'This demo supports macOS and Linux, not %s. Native Windows is unsupported.\n' "$OS" >&2
  exit 1
fi

if [[ ! -d frontend/node_modules ]]; then
  echo 'Installing frontend dependencies...'
  (cd frontend && npm ci)
fi

if [[ -n "${TMPDIR:-}" ]]; then
  DEMO="$(mktemp -d "${TMPDIR%/}/download-classify-demo.XXXXXX")"
else
  DEMO="$(mktemp -d /tmp/download-classify-demo.XXXXXX)"
fi
mkdir "$DEMO/inbox"
printf 'Disposable demo folder: %s\n' "$DEMO"
printf 'Documents placed in this inbox may be moved into topic folders.\n' >&2

API_PID=''
FRONTEND_PID=''
cleanup() {
  trap - EXIT INT TERM
  [[ -z "$FRONTEND_PID" ]] || kill "$FRONTEND_PID" 2>/dev/null || true
  [[ -z "$API_PID" ]] || kill "$API_PID" 2>/dev/null || true
  [[ -z "$FRONTEND_PID" ]] || wait "$FRONTEND_PID" 2>/dev/null || true
  [[ -z "$API_PID" ]] || wait "$API_PID" 2>/dev/null || true
  echo "Services stopped. Demo files are still at: $DEMO"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

DOWNLOAD_CLASSIFY_FOLDER="$DEMO/inbox" \
DOWNLOAD_CLASSIFY_SETTINGS_PATH="$DEMO/categories.json" \
DOWNLOAD_CLASSIFY_MOVEMENT_LOG="$DEMO/movements.jsonl" \
  uv run --extra model-check uvicorn backend.app:app --host 127.0.0.1 --port 8000 --workers 1 &
API_PID=$!

(cd frontend && npm run dev -- --host 127.0.0.1) &
FRONTEND_PID=$!

printf '\nStarting Download Classify. Open http://127.0.0.1:5173\n'
printf 'Press Ctrl-C to stop both services.\n\n'

# Keep the script in the foreground and surface either service exiting.
while kill -0 "$API_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null; do
  sleep 1
done

if ! kill -0 "$API_PID" 2>/dev/null; then
  wait "$API_PID" || true
  echo 'Backend stopped unexpectedly.' >&2
else
  wait "$FRONTEND_PID" || true
  echo 'Frontend stopped unexpectedly.' >&2
fi
exit 1
