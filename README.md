# Fairfetch

**AI agents pay for content through PayPal, and prove they respected the license.**

Publishers put a gateway in front of their site. AI agents hitting it get **HTTP 402 Payment Required**
with a price, a license, and a free preview. An agent decides with AI whether the content is worth buying,
pays from a **PayPal-funded wallet**, reads the content with a **signed time pass**, and then its answer
goes through a **license guard** that catches verbatim copying, missing citations and expired use,
repairs them, and issues a **signed usage receipt** the publisher can verify. Publishers are paid with
**PayPal Payouts**.

> Paying for access is solved by others. Fairfetch adds the missing half: **proof of fair use after payment.**

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
```

## Where PayPal and AI are used

| | Used for |
|---|---|
| **PayPal Checkout (Orders v2)** | Agent owners fund wallets: create order → buyer approves → server captures and verifies amount/currency/reference before crediting. `PayPal-Request-Id` makes create/capture idempotent. |
| **PayPal Payouts** | Publishers' earnings are settled in one batch. Ledger reserves funds first; a PayPal failure posts reversal transactions. |
| **Gemini (LLM)** | 1) agent's pay/skip decisions with reasons, 2) writing the cited answer, 3) license-guard rewrite of violating text, 4) plain-English budget rules → structured limits, 5) content uniqueness → suggested price. Every AI step has a deterministic fallback. |

## Engineering highlights
- **Double-entry ledger**: every transaction sums to zero, append-only, corrections by reversal; wallet can never go negative (atomic conditional `UPDATE` + DB `CHECK`).
- **Idempotency** everywhere money moves (`Idempotency-Key`, unique constraints, PayPal request IDs); the agent derives keys deterministically so crashes can't double-charge.
- **Signed passes (ES256 JWT)**: platform signs with the private key; the gateway verifies with the public key only, bound to agent + path, expiring, revocable via Redis.
- **License guard core** is dependency-free (`platform/app/services/license_core.py`) with unit tests, ready to become a standalone library.

## Run locally (Codespaces or any machine with Docker + Python 3.11+)

```bash
cp .env.example .env          # fill PayPal sandbox + Gemini values
make keys                     # ES256 signing key pair
make up                       # PostgreSQL + Redis
make install                  # virtual environments for platform, gateway, agent
make migrate && make seed     # schema + demo data (copy the printed API key into .env)
make setup                    # paid API resource + publisher PayPal emails
make dev                      # origin + platform + gateway
```

Then, in another terminal:

```bash
make topup                    # open approve_url, pay with a US sandbox Personal account
make agent                    # research agent: 402 → decide → buy → read → cited answer → receipt
make agent-sloppy             # copies text on purpose: watch the license guard catch and fix it
make settle                   # PayPal Payouts to publishers
make ledger-check             # must return 0 rows
make test                     # license guard unit tests
```

Dashboard: `http://127.0.0.1:8001/dashboard`

### PayPal sandbox notes
Use **United States** sandbox accounts (a US Business account linked to your app, US Personal accounts
for the buyer and the two publishers). Enable **Payouts** for the app in the developer dashboard.

## Deploy
`render.yaml` is a Render Blueprint (PostgreSQL, Key Value, origin, platform, gateway). Fill the
`sync: false` variables (PayPal keys, `PASS_PRIVATE_KEY` / `PASS_PUBLIC_KEY` as PEM text, public URLs).

## Next steps
Cryptographic bot identity (Web Bot Auth), x402 / RSL compatibility, an MCP server so any agent can use
Fairfetch, owner login for the dashboard, refunds for content that failed the agent, and a public benchmark
measuring how often agents violate the licenses they paid for.

## License
MIT
