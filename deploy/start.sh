#!/usr/bin/env bash
# One hosted service runs all three processes. Only the platform listens on the public $PORT;
# the publisher origin and the gateway stay private on localhost (the platform forwards gateway paths).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PORT="${PORT:-10000}"
export GATEWAY_URL="http://127.0.0.1:8000"
export ORIGIN_URL="http://127.0.0.1:8002"
export PLATFORM_URL="http://127.0.0.1:${PORT}"        # gateway + agent -> platform (private)
export AGENT_PLATFORM_URL="$PLATFORM_URL"
export EDGE_PROXY_GATEWAY=true

(cd "$ROOT/demo-sites/blog" && exec uvicorn server:app --host 127.0.0.1 --port 8002 --log-level warning) &
(cd "$ROOT/gateway" && exec uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level warning) &

cd "$ROOT/platform"
alembic upgrade head
python -m scripts.seed
python -m scripts.setup_demo
python -m scripts.migrate_sites
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --proxy-headers --forwarded-allow-ips='*'
