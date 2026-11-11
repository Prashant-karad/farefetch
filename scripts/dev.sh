#!/usr/bin/env bash
# Start origin, platform and gateway together; Ctrl+C stops all three.
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
mkdir -p "$ROOT/.logs"
trap 'kill 0' EXIT INT TERM

( cd "$ROOT/demo-sites/blog" && "$ROOT/gateway/.venv/bin/uvicorn" server:app --host 127.0.0.1 --port 8002 \
    > "$ROOT/.logs/origin.log" 2>&1 ) &
( cd "$ROOT/platform" && .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8001 \
    > "$ROOT/.logs/platform.log" 2>&1 ) &
( cd "$ROOT/gateway" && .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 \
    > "$ROOT/.logs/gateway.log" 2>&1 ) &

echo "origin   :8002 (private)   logs: .logs/origin.log"
echo "platform :8001             logs: .logs/platform.log   dashboard: http://127.0.0.1:8001/dashboard"
echo "gateway  :8000             logs: .logs/gateway.log"
echo "Ctrl+C to stop all."
wait
