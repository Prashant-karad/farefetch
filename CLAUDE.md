# Fairfetch — project context for Claude Code

PayPal AI Hackathon entry (Devpost). **Deadline: Fri Nov 13 2026, 1:30 AM IST** (Nov 12, 12:00 PM PST).
Repo: github.com/Prashant-karad/farefetch (Codespace path /workspaces/farefetch).

## What it is
A payment + license layer for AI agents. Publishers sit behind a gateway that returns HTTP 402 with price,
license and preview. Agents pay from a PayPal-funded wallet, read with a signed time pass, and their answer
passes a **license guard** (verbatim copying, missing citation, expired use → auto-fix → signed usage
receipt). Publishers are paid with PayPal Payouts. Differentiator: proof of fair use AFTER payment.

## Services
| Service | Port | Folder | Notes |
|---|---|---|---|
| Origin (publisher site + data API) | 8002 | demo-sites/blog | keep private, bind 127.0.0.1 |
| Platform (wallet, ledger, purchases, PayPal, guard, dashboard) | 8001 | platform | owns PostgreSQL; bind 0.0.0.0 |
| Gateway (402, pass verification, reverse proxy) | 8000 | gateway | Redis cache; never touches the DB |
| Research agent (CLI) | — | agent | `make agent`, `make agent-sloppy` |

PostgreSQL + Redis via `docker-compose.yml` at repo root. Each service has its own `.venv`.
Commands: see `Makefile` (`make help`). `make dev` starts all three services, logs in `.logs/`.

## Rules that must not be broken
- Money is integer units: 1 unit = $0.0001. Never floats.
- Only `platform/app/services/ledger.py::post_transaction` moves money; entries must sum to zero;
  ledger is append-only, corrections are reversal transactions. `make ledger-check` must return 0 rows.
- Money-moving requests are idempotent (`Idempotency-Key`, unique constraints, `PayPal-Request-Id`).
- Never call PayPal inside an open DB transaction: commit first, call, then update.
- Layers: routers (HTTP only) → services (rules) → models. `license_core.py` stays dependency-free.
- Passes: ES256 JWT; platform signs (private key), gateway verifies (public key only).
- Never commit `.env` or `keys/`.
- Commit messages: no "Co-Authored-By: Claude" line.

## Config
`.env` at repo root (see `.env.example`). AI: `LLM_PROVIDER=groq`, `GROQ_API_KEY`,
`LLM_MODEL=openai/gpt-oss-120b`. Every AI step has a deterministic fallback.
PayPal: sandbox, **US** business account linked to the app; US personal accounts for buyer and publishers.

## Status (Nov 12)
Done: M1 infra/schema, M2 gateway 402, M3 purchases + signed passes, M4 PayPal Checkout top-ups.
Added in the update archive: Payouts, research agent, license guard + receipts, AG Grid dashboard
(/dashboard), paid API resource (/api/mandi-prices), plain-English budget rules, AI price suggestion,
Makefile, README, render.yaml, devcontainer, Groq support.
Live story page: `/live` (platform/app/routers/demo.py + static/live.html). It runs the real agent
(`--events` JSON-lines mode) as a subprocess and streams its trace over SSE. `/` redirects there. DEMO_MODE=false disables it.
Known issue: Codespaces port forwarding failed for 8001, so the PayPal return redirect 404s in the browser;
workaround: `curl "http://127.0.0.1:8001/v1/topups/paypal/return?token=<ORDER_ID>"`.

## Remaining
1. Run and verify every `make` target end to end; fix bugs.
2. Commit + push.
3. Demo video (< 3 min, public YouTube).
4. Devpost submission (description, PayPal + AI usage, AI tools used, run instructions).
Deployment (render.yaml) only if time remains.

## How the user likes to work
Explain what each change does and why, and how it's done in real companies. Give terminal commands.
Be honest about trade-offs and time.

## Progress log (autonomous build, Nov 12 IST)
DONE and pushed:
- Demo content = LEARNING blogs: Code Dojo (pub_code_dojo) + Learn Daily (pub_learn_daily), API /api/job-trends.
- Pages: `/` landing (static/index.html, canvas "gate" animation, live 402), `/app` (static/app.html: Agent owner +
  Publisher with setup wizard/overview/content, demo guide strip), `/live` = under the hood. Shared ff.css / ff.js.
- Backend: routers/product.py (scan, go-live, test-bot, publisher/owner views, rules, knock, licenses),
  routers/demo.py (SSE agent run, state, verify, reset-passes, settle, topup + capture). Gateway /.well-known/fairfetch.json.
- `make reset-demo` (fresh DB, writes agent key to .env; restart `make dev` after), `make dev-credit` (testing only).
- docs/VIDEO_SCRIPT.md, docs/DEVPOST.md. Silent draft recording: .recordings/fairfetch-demo-draft.webm (gitignored).
- Browser-tested (playwright venv in scratchpad): desktop, 400px phone, dark mode; ledger-check 0 rows.
LEFT FOR THE USER: reset-demo → PayPal top-up on camera → record voice video → YouTube → Devpost.
Known limits: scan works for any URL but only the demo site can go live; sites that block bots get a clear message.
