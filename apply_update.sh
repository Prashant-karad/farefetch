#!/usr/bin/env bash
# Run from the repo root after extracting: bash apply_update.sh
set -euo pipefail
grep -qx ".logs/" .gitignore || echo ".logs/" >> .gitignore
grep -qx "agent/runs/" .gitignore || echo "agent/runs/" >> .gitignore
grep -qx "keys/" .gitignore || echo "keys/" >> .gitignore
chmod +x scripts/dev.sh
echo "Files updated. New settings to add to .env (see .env.example):"
for v in GATEWAY_URL PUBLISHER_A_PAYPAL_EMAIL PUBLISHER_B_PAYPAL_EMAIL GEMINI_API_KEY LLM_MODEL; do
  grep -q "^$v=" .env 2>/dev/null || echo "  missing: $v"
done
