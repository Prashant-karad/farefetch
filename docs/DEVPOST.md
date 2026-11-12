# Devpost submission: copy each section into the matching field

---

## Project name
Fairfetch

## Elevator pitch (short tagline)
AI agents pay publishers per read with PayPal, and prove they used the work fairly.

## Video demo link
https://www.youtube.com/watch?v=REPLACE_WITH_YOUR_VIDEO_ID

## "Try it out" links
- Live app: https://fairfetch-xm1y.onrender.com
- Source code: https://github.com/Prashant-karad/farefetch
- Demo publisher website (connect it live in the app): https://studynest-94bj.onrender.com

## Built with (tags)
paypal-checkout, paypal-payouts, paypal-orders-v2, python, fastapi, postgresql, redis, groq, gpt-oss-120b, jwt, render, ag-grid, postman, javascript, html, css

---

## About the project (paste everything below into the main description)

### Try it in 2 minutes
**Live app:** https://fairfetch-xm1y.onrender.com/app (a short guided tour opens on your first visit and lights up each thing to click).
Payments run in **PayPal sandbox** (test mode): when you add money, the app shows a test PayPal login right under the button.

1. **Publisher → Set up:** pick **StudyNest** (a real, separately hosted homework website), watch an AI price every page, add a payout email, **Go live**, then **Send a test bot** and see the real `HTTP 402 Payment Required`.
2. **Agent owner:** add money with **PayPal Checkout**, write a budget rule in plain English, and ask *"How does photosynthesis work?"*. The agent checks every price, buys only what adds something (and says why), pays StudyNest, and answers with credit.
3. Switch to **Careless agent** and ask again: the license guard catches the copied text and missing credit, fixes the answer and signs a receipt.
4. **Publisher → Overview:** see who paid and why, then **Pay me via PayPal** (a real sandbox Payouts batch).
5. **Under the hood** (`/live`): every HTTP call of an agent run, the double-entry ledger and signature checks.

### Inspiration
Think about how you look things up today: you ask an AI, it reads Stack Overflow, Chegg or a blog, and hands you the answer. In one year Stack Overflow lost about a third of its visitors and Chegg's non-subscriber traffic fell about half. The people who wrote those answers get no visit, no credit and no money, so their only option is to block bots.

HTTP has had a status code for this since 1997, `402 Payment Required`, but nobody used it. And paying for access is only half the problem: once an agent has paid, nothing stops it from pasting the article word for word without credit. We wanted both halves.

### What it does
Fairfetch is a gateway in front of any website.
- **Publishers** paste their site's address. Fairfetch reads the sitemap, an AI prices every page by how original it is, and the publisher picks a license per page (read, quote or data) and which pages to protect. From then on, an unpaid AI request gets **HTTP 402** with the price, the license terms and a free preview instead of the page.
- **Agent owners** fund a wallet with **PayPal Checkout** and set a budget in plain English ("never more than 5 cents per article and $1 a day"), which the platform enforces.
- **The agent** reads the 402 previews, decides which sources are worth paying for and explains why, pays, receives a signed time-limited pass, and reads the real page through the gateway.
- **The license guard** checks the answer before it ships: copied word runs beyond the license, missing citations, expired passes. It fixes problems automatically and issues a **signed usage receipt** anyone can verify with a public key.
- **Publishers are paid with PayPal Payouts**, and see every paid read, 90% of the price, and the agent's own reason for buying.

### What makes it different
Pay-per-crawl tools charge the bot at the door, and that's it. **Fairfetch also proves what the agent did after it paid**: every answer is checked against the publisher's license and comes with a signed receipt. It is built as three separate parts:
- a **gateway** at the edge that speaks HTTP 402 and only verifies signed passes; it never touches money;
- a **platform** that holds the wallets, a double-entry ledger and the license guard;
- the **agent**, which reasons with AI about what is worth buying.

### How we use PayPal
A single read costs a few cents, far too small for a card payment each time. So:
- **PayPal Checkout (Orders v2)** funds the agent's wallet once: create order → buyer approves → our server captures and **verifies status, amount, currency and our reference** before crediting the ledger exactly once. `PayPal-Request-Id` makes create and capture idempotent, and we never call PayPal inside an open database transaction.
- Each read is then settled instantly on our double-entry ledger (90% to the publisher, 10% fee).
- **PayPal Payouts** sends publishers their earnings in one batch, in whole cents; balances under a cent wait for the next batch. Funds are reserved first, and a failed payout posts a reversal.

### How we use AI
The agent and the platform use **Groq (`openai/gpt-oss-120b`)** for: deciding what to buy and why, writing a cited answer within each license, rewriting copied passages in the license guard, turning plain-English budget rules into limits, and pricing every page of a newly connected website by originality. **Every AI step has a deterministic fallback**, so money and licensing never depend on a model being up.

### How we built it
- **Gateway** (FastAPI): 402 price lists, ES256 pass verification with the public key only, reverse proxy to each publisher's own website, Redis cache, a machine-readable price list at `/.well-known/fairfetch.json`.
- **Platform** (FastAPI, PostgreSQL, Redis): wallets and a **double-entry ledger** (every transaction sums to zero, append-only, wallets can never go negative), idempotent purchases, pass and receipt signing, the license guard, PayPal Checkout and Payouts.
- **Research agent** (Python): the real agent the app runs, streaming its trace as JSON lines to the browser.
- **Three publisher websites** (static sites), the web app, the landing page and the under-the-hood view, in plain HTML, CSS and JavaScript.

### Sponsor tools used
- **Render:** the live app (one web service + Render PostgreSQL + Render Key Value) and the three publisher websites (static sites).
- **AG Grid:** the publisher's content table: sort, filter, and edit a price in place; the gateway charges the new price immediately.
- **Postman:** a "be the agent yourself" collection that walks the protocol with tests: 402 → purchase → read → license check → receipt verification (`docs/postman` in the repo).

### Challenges
- Making money movement safe: idempotency keys derived from task and resource, so a crashed agent can retry without paying twice; conditional updates so a wallet can't go negative under concurrency.
- Deciding what "fair use" means in code: the longest copied run of words against each license's limit, citations and pass expiry, always measured against the publisher's original page and never the agent's copy.
- Explaining a two-sided protocol: separate publisher and agent-owner views with their own identity, plus a guided tour where visitors click every real step themselves.

### Accomplishments we're proud of
- A full loop on real infrastructure: PayPal in → HTTP 402 → AI decision → signed pass → gateway read from a real website → license guard → signed receipt → PayPal out.
- Connecting a brand-new website live, from its URL, in under a minute.
- A ledger that always balances, and receipts a publisher can verify without trusting us.

### What we learned
HTTP 402 suits AI agents well: an agent can read a price list and reason about it. The harder and more valuable part is what happens after payment.

### What's next
Cryptographic bot identity (Web Bot Auth), x402 and RSL compatibility, an MCP server so any agent can use Fairfetch, DNS onboarding for any domain, publisher and owner logins, and refunds when content fails the agent.

---

## Hackathon questions (if the form asks)
- **PayPal products used:** PayPal Checkout (Orders v2: create, approve, capture) and PayPal Payouts, both in the PayPal sandbox.
- **AI model / platform used:** Groq, model `openai/gpt-oss-120b` (agent decisions, cited answers, license-guard rewrites, plain-English budget rules, page pricing).
- **AI tools used to build it:** Claude Code (Anthropic) for pair-programming, testing and the demo video; Sarvam AI (Bulbul v3) for the video narration.
- **Test login for judges:** shown inside the app next to "Add money with PayPal" (sandbox money only).
