# Demo video script (target 2:45, hard limit 3:00)

Record at 1920×1080, browser zoom 100%, light mode. Before recording:

1. Record on the live site: https://fairfetch-xm1y.onrender.com (or locally after `make reset-demo` + `make dev`).
2. Open three tabs: `/` (landing), `/app#publisher-setup`, `/app#agent`. Click **Hide tour** for a cleaner frame.
3. Log in to the PayPal sandbox buyer account in the same browser so approval is one click.
4. Do one dry run of the agent question so the AI is warm.

Speak slowly. Every scene has one idea.

| Time | Screen | Do | Say |
|---|---|---|---|
| 0:00–0:15 | `/` hero | Let the gate animation run. | "AI assistants answer our questions by reading what people wrote. The writers get no visit, no credit and no money. Fairfetch changes that deal." |
| 0:15–0:30 | `/` scroll to *Knock. Pay. Prove.* | Scroll slowly through the three steps. Pause on the live 402. | "It's a gateway in front of any website. An AI agent gets a price instead of a page: HTTP 402 Payment Required. It pays from a PayPal-funded wallet. And then it has to prove it used the work fairly." |
| 0:30–0:55 | `/app#publisher-setup` | Click **codedojo.dev**. Prices drop in. Click **Continue**, **Go live**, **Send a test bot**. | "I'm Code Dojo, a programming blog. I paste my link. Fairfetch reads my sitemap, and an AI prices each page by how original it is: my benchmarks cost more than generic tips. I go live, and a test bot now gets 402 with my price." |
| 0:55–1:15 | `/app#agent` wallet | **Add $5.00 with PayPal** → approve in the PayPal tab → **I approved it, add the money**. Then save the rule *"Never more than 5 cents per article and $1 a day"*. | "Now I'm Maya, who runs a study assistant. I fund its wallet with PayPal Checkout, and I set rules in plain English. The AI turns them into limits the platform enforces." |
| 1:15–1:50 | `/app#agent` chat | Click **Make slow Python code faster**. Open **steps** while it runs. | "I ask a question. The agent finds six sources, and every one answers with a price. It buys the two that add something and skips the rest, and says why. It pays, gets signed passes, reads through the gateway, and answers with citations." |
| 1:50–2:05 | `/app#publisher` | Switch role. Show the earnings odometer and the visitor feed. | "Back as the publisher: I can see who paid, what they read, and the agent's own reason for buying." |
| 2:05–2:25 | `/app#agent` | Switch to **Careless agent**, ask *How do I learn Python fast?* Open steps on the red-pen draft. | "Now a careless agent copies sentences straight from the articles. Fairfetch catches the copying and the missing credit, fixes the answer, and signs a receipt." |
| 2:25–2:40 | `/app#publisher` | Click **Pay me via PayPal**. Show the tracker and batch ID. Open a receipt. | "Publishers are paid with PayPal Payouts, and every use comes with a signed receipt they can verify themselves." |
| 2:40–2:50 | `/live` (optional) or landing CTA | Show the ledger panel: *all balanced*. | "Every cent is in a double-entry ledger. Paying gets an agent in. Fairfetch proves it behaved once it was in." |

## Backup lines if something is slow
- While the agent runs: "This is a real agent process making real HTTP calls; nothing here is pre-recorded."
- If PayPal is slow: cut, and resume after capture. Don't show a long spinner.

## After recording
Upload to YouTube as **Public** (or Unlisted only if the rules allow), title: *Fairfetch: AI agents pay publishers with PayPal and prove fair use*.
