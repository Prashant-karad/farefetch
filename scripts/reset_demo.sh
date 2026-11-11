#!/usr/bin/env bash
# Fresh demo state: empty ledger, seeded publishers/articles, new agent API key written to .env.
# The wallet starts at $0: fund it with PayPal in the app (or `make dev-credit` for local testing only).
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"; cd "$ROOT"
mkdir -p .backup
docker compose exec -T postgres pg_dump -U app agentgate > ".backup/agentgate-$(date +%Y%m%d-%H%M%S).sql" || true
docker compose exec -T postgres psql -U app -d postgres -qc "DROP DATABASE IF EXISTS agentgate WITH (FORCE);" -c "CREATE DATABASE agentgate OWNER app;"
docker compose exec -T redis redis-cli FLUSHALL > /dev/null
(cd platform && .venv/bin/alembic upgrade head > /dev/null)
OUT="$(cd platform && .venv/bin/python -m scripts.seed)"
KEY="$(echo "$OUT" | grep 'API key' | sed 's/.*: //')"
sed -i "s|^DEMO_AGENT_API_KEY=.*|DEMO_AGENT_API_KEY=$KEY|" .env
(cd platform && .venv/bin/python -m scripts.setup_demo)
echo "Demo reset. New agent API key saved to .env. Restart 'make dev' so the platform picks it up."
