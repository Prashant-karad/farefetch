# Fairfetch

**AI agents pay for content through PayPal, and prove they respected the license.**

Publishers put a gateway in front of their site. AI agents hitting it get **HTTP 402 Payment Required**
with a price, a license, and a free preview. An agent decides with AI whether the content is worth buying,
pays from a **PayPal-funded wallet**, reads the content with a **signed time pass**, and then its answer
goes through a **license guard** that catches verbatim copying, missing citations and expired use,
repairs them, and issues a **signed usage receipt** the publisher can verify. Publishers are paid with
**PayPal Payouts**.

> Paying for access is solved by others. Fairfetch adds the missing half: **proof of fair use after payment.**

## Try it live
**https://fairfetch-xm1y.onrender.com** · open the app: **https://fairfetch-xm1y.onrender.com/app** (a 2-minute tour opens automatically).
Payments run in **PayPal sandbox** (test mode): the app shows a test PayPal login next to the top-up button.
For API testing, import [`docs/postman/fairfetch.postman_collection.json`](docs/postman/fairfetch.postman_collection.json) into Postman.

## See it

| Page | What it shows |
|---|---|
| **`/`** | Landing page: the idea in 30 seconds, with an animated toll gate and a **live 402 fetched from the gateway** |
| **`/app#publisher-setup`** | Publisher setup: paste a URL → real sitemap/RSS scan → AI price per page → licenses → go live → **send a test bot** |
| **`/app#agent`** | Agent owner: PayPal top-up, plain-English spending rules, access-pass tickets, and a chat that runs the **real agent** |
| **`/app#publisher`** | Publisher: earnings odometer, AI visitors who paid (and why), signed usage receipts, **PayPal Payouts** |
| **`/live`** | Under the hood: every HTTP call of an agent run on a network map, the double-entry ledger, signature verification |

The demo publishers are **Code Dojo** (programming tutorials with original benchmarks) and **Learn Daily**
(study and career how-tos): the kind of writing AI assistants answer from every day. Articles are sample content.

## How it works

```
 Agent ──GET article──► Gateway :8000 ──(402 + price, license, preview)──► Agent
   │                       │  verifies ES256 pass, Redis cache, access logs
   │                       └──(valid pass)──► Origin site :8002 (unchanged publisher site)
   │
   └──► Platform :8001 ── PostgreSQL (double-entry ledger) / Redis
          • POST /v1/topups            PayPal Checkout: order → approve → capture → verify → credit
          • POST /v1/purchases         budget check, row lock, atomic ledger, idempotency, signed pass
          • POST /v1/usage/check       license guard → fix → signed usage receipt
          • POST /v1/admin/payouts/settle   PayPal Payouts batch to publishers
          • GET  /dashboard            AG Grid dashboards (publisher, agent owner, money)
          • /v1/demo/*                 endpoints behind the app (demo only, DEMO_MODE=false disables)
 Gateway :8000 /.well-known/fairfetch.json   machine-readable price list for agents
```

## Where PayPal and AI are used

| | Used for |
|---|---|
| **PayPal Checkout (Orders v2)** | Agent owners fund wallets: create order → buyer approves → server captures and verifies amount/currency/reference before crediting. `PayPal-Request-Id` makes create/capture idempotent. |
| **PayPal Payouts** | Publishers' earnings are settled in one batch. Ledger reserves funds first; a PayPal failure posts reversal transactions. |
| **LLM (Groq by default, Gemini optional)** | 1) agent's pay/skip decisions with reasons, 2) writing the cited answer, 3) license-guard rewrite of violating text, 4) plain-English budget rules → structured limits, 5) content uniqueness → suggested price. Every AI step has a deterministic fallback. |

## Engineering highlights
- **Double-entry ledger**: every transaction sums to zero, append-only, corrections by reversal; wallet can never go negative (atomic conditional `UPDATE` + DB `CHECK`).
- **Idempotency** everywhere money moves (`Idempotency-Key`, unique constraints, PayPal request IDs); the agent derives keys deterministically so crashes can't double-charge.
- **Signed passes (ES256 JWT)**: platform signs with the private key; the gateway verifies with the public key only, bound to agent + path, expiring, revocable via Redis.
- **License guard core** is dependency-free (`platform/app/services/license_core.py`) with unit tests, ready to become a standalone library.

## Run locally (Codespaces or any machine with Docker + Python 3.11+)

```bash
cp .env.example .env          # fill PayPal sandbox + Groq values
make keys                     # ES256 signing key pair
make up                       # PostgreSQL + Redis
make install                  # virtual environments for platform, gateway, agent
make reset-demo               # schema + demo data; writes the agent API key into .env
make dev                      # origin + platform + gateway
```

Open **http://127.0.0.1:8001/** (in Codespaces: forward port 8001 and open its URL). The app has a
**Demo guide** strip that walks through the whole story in six steps.

Then, in another terminal:

```bash
make topup                    # open approve_url, pay with a US sandbox Personal account (or use the app)
make dev-credit               # LOCAL TESTING ONLY: wallet credit without PayPal, labelled DEV-CREDIT
make agent                    # research agent: 402 → decide → buy → read → cited answer → receipt
make agent-sloppy             # copies text on purpose: watch the license guard catch and fix it
make settle                   # PayPal Payouts to publishers
make ledger-check             # must return 0 rows
make test                     # license guard unit tests
```

Classic tables: `http://127.0.0.1:8001/dashboard`

### PayPal sandbox notes
Use **United States** sandbox accounts (a US Business account linked to your app, US Personal accounts
for the buyer and the two publishers). Enable **Payouts** for the app in the developer dashboard.

## Deploy
The live demo runs on **Render** as one web service (`bash deploy/start.sh`: publisher site and gateway on
localhost, platform on the public port, forwarding the gateway's public paths) plus Render PostgreSQL and Key Value.
Build: `pip install -r platform/requirements.txt -r gateway/requirements.txt -r agent/requirements.txt`.
A GitHub Actions job pings `/health` every 5 minutes so the free instance stays awake.

## Next steps
Cryptographic bot identity (Web Bot Auth), x402 / RSL compatibility, an MCP server so any agent can use
Fairfetch, owner login for the dashboard, refunds for content that failed the agent, and a public benchmark
measuring how often agents violate the licenses they paid for.

## License
MIT
