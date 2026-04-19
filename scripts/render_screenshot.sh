#!/usr/bin/env bash
set -euo pipefail
if [ "$#" -ne 2 ]; then
  echo "usage: $0 <html-path> <output-png>" >&2
  exit 1
fi
HTML_PATH=$(realpath "$1")
OUT_PATH=$(realpath "$2")
HTML_DIR=$(dirname "$HTML_PATH")
HTML_NAME=$(basename "$HTML_PATH")
PORT=${GO_BENCH_SCREENSHOT_PORT:-8876}
mkdir -p "$(dirname "$OUT_PATH")"
cd "$HTML_DIR"
python3 -m http.server "$PORT" >/tmp/go-bench-screenshot-http.log 2>&1 &
PID=$!
trap 'kill $PID 2>/dev/null || true' EXIT
sleep 1
npx playwright screenshot --browser chromium "http://127.0.0.1:${PORT}/${HTML_NAME}" "$OUT_PATH" >/tmp/go-bench-screenshot.log 2>&1
kill "$PID" 2>/dev/null || true
wait "$PID" 2>/dev/null || true
trap - EXIT
