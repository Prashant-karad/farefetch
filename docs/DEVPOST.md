# Fairfetch — Devpost submission draft

## Tagline
AI agents pay publishers per read with PayPal, and prove they used the work fairly.

## Try it (2 minutes, no setup)
- **Live app:** https://fairfetch-xm1y.onrender.com/app (a short tour opens automatically)
- **Payments are PayPal sandbox.** The app shows a test PayPal login next to "Add $5.00 with PayPal".
0. Click **Take the tour**: every step has a "Do it for me" button.
1. **Publisher → Set up** → click **StudyNest** (a real, separate homework website) → AI prices appear → Continue → **Go live** → **Send a test bot** (real HTTP 402).
2. **Agent owner** → add money with PayPal (test login shown) → ask *"How does photosynthesis work?"* and watch it price, choose, pay StudyNest and answer with credit.
3. Switch to **Careless agent** and ask again: the license check catches the copying and fixes it.
4. **Publisher → Overview** → see who paid and why → **Pay me via PayPal** (real sandbox Payouts batch).
5. **Under the hood:** https://fairfetch-xm1y.onrender.com/live shows every HTTP call of a run, the ledger and signature checks.

## Inspiration
AI assistants now answer questions by reading blogs, tutorials and guides. The sites hit hardest are exactly the
"what is OOP / how do SQL JOINs work / what is compound interest" kind: Stack Overflow lost about a third of its
visitors in a year, Chegg's non-subscriber traffic fell about half, and finance and reference explainers lost about a third. The people who wrote them get no
visit, no credit and no money, so their only choice is to block bots. HTTP has had a status code for this since
1997, `402 Payment Required`, but nobody used it. Paying for access is only half the problem: once an agent has
paid, nothing stops it from pasting your article word for word without credit. We wanted both halves.

## What it does
Fairfetch is a gateway that sits in front of any website.

- **Publishers** paste their website's link (the demo has three real, separately hosted sites: Code Dojo, MoneyWise and StudyNest). Fairfetch reads the sitemap, an AI suggests a price per page based on how
  original it is, and the publisher picks a license (read, quote or data). From then on, an unpaid AI request gets
  **HTTP 402** with the price, license terms and a free preview instead of the page.
- **Agent owners** fund a wallet with **PayPal Checkout** and set spending rules in plain English
  ("never more than 5 cents per article and $1 a day"). The platform enforces them.
- **The agent** reads the 402 previews, decides which sources are worth paying for (and says why), pays, receives
  a signed time-limited pass, and reads through the gateway.
- **The license guard** checks the agent's answer before it ships: verbatim copying beyond the license, missing
  citations, expired passes. It fixes problems automatically (AI rewrite, deterministic fallback) and issues a
  **signed usage receipt** the publisher can verify with a public key.
- **Publishers are paid with PayPal Payouts**, and see who paid, why, and how their work was used.

## How we built it
- **Gateway** (FastAPI): returns 402 price lists, verifies ES256 passes with the public key only, reverse-proxies paid
  reads to each publisher's own, unchanged website, caches lookups in Redis, and publishes a machine-readable price list at
  `/.well-known/fairfetch.json`.
- **Platform** (FastAPI, PostgreSQL, Redis): wallets and a **double-entry ledger** (every transaction sums to zero,
  append-only, wallets can never go negative), idempotent purchases, pass and receipt signing, the license guard,
  PayPal Checkout top-ups and PayPal Payouts.
- **Research agent** (Python): the real agent the demo runs, streaming its trace as JSON lines.
- **Web app**: landing page, publisher and agent-owner views, and an "under the hood" view of every HTTP call,
  in plain HTML, CSS and JavaScript with no framework.

### How we use PayPal
- **Orders v2 (Checkout)** to fund agent wallets: create order → buyer approves → server captures and **verifies
  status, amount, currency and our reference** before crediting the ledger exactly once. `PayPal-Request-Id`
  makes create and capture idempotent, and we never call PayPal inside an open database transaction.
- **Payouts** to pay publishers in one batch, in whole cents; balances under a cent stay owed for the next batch.
  The ledger reserves funds first, and a failed payout posts a reversal.

### How we use AI (Groq, `openai/gpt-oss-120b`)
1. The agent decides what to buy, with a one-sentence reason per source, within budget.
2. The agent writes a cited answer within each license's quote limit.
3. The license guard rewrites violating passages, then re-checks them.
4. Plain-English spending rules become structured limits.
5. Publisher setup: one AI call rates every scanned page's originality and suggests a price with a reason.

Every AI step has a deterministic fallback, so the money and licensing paths never depend on a model being up.

### Sponsor tools used
- **Render:** the live deployment (one web service + Render PostgreSQL + Render Key Value) and the three publisher websites (Render static sites).
- **AG Grid:** the publisher's content table (sort, filter, edit a price in place; the gateway uses it immediately) and the classic dashboard.
- **Postman:** a "be the agent yourself" collection that runs the protocol step by step with tests: 402 → purchase → read → license check → receipt verification ([`docs/postman`](https://github.com/Prashant-karad/farefetch/tree/main/docs/postman)).

### AI tools used to build it
Claude Code (Anthropic) for pair-programming, code review, UI implementation and testing with a headless browser.

## Challenges
- Making money movement safe: idempotency keys derived from task and resource, so a crashed agent can retry
  without paying twice; conditional updates so a wallet can't go negative under concurrency.
- Deciding what "fair use" means in code: longest copied run of words against each license's limit, citations,
  and pass expiry, measured against the publisher's original text and never the agent's copy.
- Explaining a protocol to people: we built three views (publisher, agent owner, under the hood) so each side sees
  only what matters to them.

## Accomplishments
- A full loop: PayPal in, 402, AI decision, signed pass, gateway read, license guard, signed receipt, PayPal out.
- A ledger that always balances (`make ledger-check` returns 0 rows after every run).
- Receipts a publisher can verify without trusting us.

## What we learned
402 is a good fit for agents because an agent can read a price list and reason about it. The harder and more
valuable part is what happens after payment.

## What's next
Cryptographic bot identity (Web Bot Auth), x402 and RSL compatibility, an MCP server so any agent can use
Fairfetch, real DNS onboarding for any domain, owner and publisher login, and refunds when content fails the agent.

## Links
- Live: https://fairfetch-xm1y.onrender.com
- Code and run instructions: https://github.com/Prashant-karad/farefetch
