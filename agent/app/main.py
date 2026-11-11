"""Fairfetch research agent.

  question -> discover sources (catalog) -> hit the gateway, read the 402 previews
  -> decide pay/skip WITH REASONS (AI, budget-aware) -> buy passes (idempotent)
  -> read the content -> write a cited answer -> license guard -> signed receipt.

Run from agent/:
  python -m app.main "When should I sow soybean in Pune, and how do I test soil first?"
  python -m app.main "..." --sloppy      # deliberately copies text to show the license guard
"""

import argparse
import hashlib
import json
import re
from pathlib import Path

import httpx

from app import config, llm

AUTH = {"Authorization": f"Bearer {config.API_KEY}"}
_WORD = re.compile(r"[a-z0-9]+")


def usd(units: int) -> str:
    return f"${units // 10_000}.{units % 10_000:04d}"


def say(icon: str, text: str) -> None:
    print(f"{icon} {text}")


def jaccard(a: str, b: str) -> float:
    sa, sb = set(_WORD.findall(a.lower())), set(_WORD.findall(b.lower()))
    return len(sa & sb) / max(1, len(sa | sb))


# ---------- 1. Discover ----------
def discover(question: str, limit: int) -> list[dict]:
    resp = httpx.get(f"{config.PLATFORM_URL}/v1/catalog", params={"q": question, "limit": limit}, timeout=15)
    resp.raise_for_status()
    return resp.json()


# ---------- 2. Ask the gateway (402 = price list) ----------
def probe(path: str) -> dict:
    resp = httpx.get(f"{config.GATEWAY_URL}{path}", headers=AUTH, timeout=15)
    if resp.status_code != 402:
        raise RuntimeError(f"Expected 402 from gateway for {path}, got {resp.status_code}: {resp.text[:200]}")
    return resp.json()


# ---------- 3. Decide ----------
def decide(question: str, offers: list[dict], budget: dict, balance: int) -> list[dict]:
    """Returns [{resource_id, buy, reason}]. AI first; deterministic fallback."""
    listing = [{
        "resource_id": o["resource_id"], "title": o["title"], "kind": o.get("kind"),
        "price_usd": o["price"]["display"], "price_units": o["price"]["amount"],
        "license": o["license"]["id"], "preview": o["preview"]["excerpt"],
    } for o in offers]
    data = llm.generate_json(
        "You are a research agent with a strict budget, deciding which paid sources to BUY to answer a question. "
        "Buy only sources likely to add information the others don't. Skip near-duplicates (keep the cheaper or "
        "more original one), skip off-topic ones, and never exceed the limits.\n"
        f"QUESTION: {question}\nBUDGET: max per item {usd(budget['max_per_item'])}, max per day "
        f"{usd(budget['max_per_day'])}; wallet balance {usd(balance)}.\nSOURCES:\n{json.dumps(listing, indent=1)}\n"
        'Return JSON {"decisions": [{"resource_id": str, "buy": bool, "reason": str (one sentence)}]}'
    )
    if data and isinstance(data.get("decisions"), list):
        known = {o["resource_id"] for o in offers}
        decisions = [d for d in data["decisions"] if d.get("resource_id") in known]
        if decisions:
            for d in decisions:
                d["by"] = "llm"
            return decisions

    # Fallback: rank by relevance, skip near-duplicates and over-limit prices.
    decisions, chosen, spent = [], [], 0
    for o in offers:
        price, preview = o["price"]["amount"], o["preview"]["excerpt"]
        dup = next((c for c in chosen if jaccard(preview, c["preview"]["excerpt"]) > 0.45), None)
        if dup:
            reason, buy = f"Near-duplicate of '{dup['title']}' which is already selected.", False
        elif price > budget["max_per_item"]:
            reason, buy = f"Price {o['price']['display']} is above the per-item limit.", False
        elif spent + price > balance:
            reason, buy = "Not enough wallet balance left.", False
        elif len(chosen) >= 3:
            reason, buy = "Three sources already cover the question.", False
        else:
            reason, buy = f"Relevant preview at {o['price']['display']}; adds information for the answer.", True
        if buy:
            chosen.append(o)
            spent += price
        decisions.append({"resource_id": o["resource_id"], "buy": buy, "reason": reason, "by": "heuristic"})
    return decisions


# ---------- 4. Buy (idempotent) ----------
def idempotency_key(task_id: str, resource_id: str) -> str:
    """Deterministic: same task + same resource = same key, so a crash/retry can never double-charge."""
    return hashlib.sha256(f"{task_id}:{resource_id}".encode()).hexdigest()[:40]


def buy(task_id: str, resource_id: str, reason: str) -> dict:
    for attempt in range(3):  # retry network errors with the SAME key
        try:
            resp = httpx.post(f"{config.PLATFORM_URL}/v1/purchases", timeout=20,
                              headers={**AUTH, "Idempotency-Key": idempotency_key(task_id, resource_id)},
                              json={"resource_id": resource_id, "reason": reason})
            body = resp.json()
            if resp.status_code >= 400:
                raise RuntimeError(body.get("detail", body))
            return body
        except httpx.TransportError:
            if attempt == 2:
                raise
    raise RuntimeError("unreachable")


# ---------- 5. Read ----------
def read(path: str, pass_token: str) -> str:
    resp = httpx.get(f"{config.GATEWAY_URL}{path}", headers={**AUTH, "X-Access-Pass": pass_token}, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return data.get("body") or json.dumps(data)


# ---------- 6. Write ----------
def write_answer(question: str, sources: list[dict], sloppy: bool) -> str:
    if sloppy:
        # Deliberately bad: copies sentences verbatim and forgets citations.
        parts = [" ".join(re.split(r"(?<=[.!?])\s+", s["text"])[:2]) for s in sources]
        return "Here is what I found. " + " ".join(parts)
    block = "\n\n".join(f"[{s['resource_id']}] {s['title']} (license {s['license']['id']}: "
                        f"max {s['license']['max_quote_words']} consecutive copied words)\n{s['text']}"
                        for s in sources)
    text = llm.generate_text(
        "Answer the question for a farmer in 120-200 words using ONLY the sources. Write in your own words; "
        "do NOT copy more consecutive words than each license allows. Cite every source you use inline with "
        f"its marker, e.g. [res_x].\n\nQUESTION: {question}\n\nSOURCES:\n{block}"
    )
    if text:
        return text.strip()
    # No LLM: a minimal, license-safe summary.
    lines = []
    for s in sources:
        keywords = sorted({w for w in _WORD.findall(s["text"].lower()) if len(w) > 6})[:8]
        lines.append(f"- {s['title']} [{s['resource_id']}] covers: {', '.join(keywords)}.")
    return f"Relevant findings for: {question}\n" + "\n".join(lines)


# ---------- 7. License guard ----------
def guard(answer: str, grant_ids: list[str]) -> dict:
    resp = httpx.post(f"{config.PLATFORM_URL}/v1/usage/check", headers=AUTH, timeout=90,
                      json={"answer": answer, "grant_ids": grant_ids, "auto_fix": True})
    resp.raise_for_status()
    return resp.json()


def run(question: str, limit: int, sloppy: bool) -> dict:
    if not config.API_KEY:
        raise SystemExit("Set DEMO_AGENT_API_KEY in .env")
    task_id = hashlib.sha256(question.strip().lower().encode()).hexdigest()[:16]
    say("🧭", f"Task {task_id}: {question}")
    say("🧠", f"Reasoning: {'Gemini' if llm.enabled() else 'heuristic fallback (set GEMINI_API_KEY for AI)'}")

    me = httpx.get(f"{config.PLATFORM_URL}/v1/me", headers=AUTH, timeout=15).json()
    wallet = httpx.get(f"{config.PLATFORM_URL}/v1/wallet", headers=AUTH, timeout=15).json()
    budget = me.get("budget") or {"max_per_item": 500, "max_per_day": 10_000}
    say("👛", f"Wallet {wallet['balance_display']} | per item ≤ {usd(budget['max_per_item'])}, "
              f"per day ≤ {usd(budget['max_per_day'])}")

    candidates = discover(question, limit)
    say("🔎", f"Found {len(candidates)} candidate sources")
    offers = []
    for c in candidates:
        offer = probe(c["path"])
        offer["path"] = c["path"]
        offers.append(offer)
        say("  402", f"{offer['title']} — {offer['price']['display']} ({offer['license']['id']})")

    decisions = decide(question, offers, budget, wallet["balance"])
    by_id = {o["resource_id"]: o for o in offers}
    sources, report = [], []
    for d in decisions:
        offer = by_id[d["resource_id"]]
        if not d.get("buy"):
            say("⏭️ ", f"SKIP {offer['title']}: {d['reason']}")
            report.append({**d, "title": offer["title"], "outcome": "skipped"})
            continue
        try:
            purchase = buy(task_id, offer["resource_id"], d["reason"])
        except RuntimeError as exc:
            say("⛔", f"Could not buy {offer['title']}: {exc}")
            report.append({**d, "title": offer["title"], "outcome": f"failed: {exc}"})
            continue
        note = "already owned, no charge" if purchase["already_owned"] else f"paid {usd(purchase['price'])}"
        say("💳", f"BUY {offer['title']} ({note}): {d['reason']}")
        text = read(offer["path"], purchase["pass_token"])
        sources.append({"resource_id": offer["resource_id"], "title": offer["title"], "license": offer["license"],
                        "grant_id": purchase["grant_id"], "text": text})
        report.append({**d, "title": offer["title"], "outcome": note, "grant_id": purchase["grant_id"]})

    if not sources:
        say("🤷", "No sources bought; nothing to answer from.")
        return {"task_id": task_id, "decisions": report}

    draft = write_answer(question, sources, sloppy)
    say("✍️ ", "Draft answer written; running the license guard ...")
    result = guard(draft, [s["grant_id"] for s in sources])
    for v in result["violations_found"]:
        say("🚨", f"{v['type']} on {v['resource_id']}: {v['message']}")
    if result["violations_found"]:
        say("🛠️ ", f"Fixed by: {result['fixed_by']}")
    say("✅" if result["passed"] else "❌", f"License check {'PASSED' if result['passed'] else 'FAILED'} — "
                                          f"signed receipt {result['receipt_id']}")
    print("\n" + "=" * 70 + "\nFINAL ANSWER\n" + "=" * 70 + "\n" + result["answer"] + "\n")

    out = {"task_id": task_id, "question": question, "decisions": report, "draft": draft,
           "final_answer": result["answer"], "receipt": {k: result[k] for k in
           ("receipt_id", "passed", "fixed_by", "violations_found", "signature")}}
    Path("runs").mkdir(exist_ok=True)
    Path(f"runs/{task_id}.json").write_text(json.dumps(out, indent=2))
    say("💾", f"Saved runs/{task_id}.json")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Fairfetch research agent")
    ap.add_argument("question")
    ap.add_argument("--limit", type=int, default=6)
    ap.add_argument("--sloppy", action="store_true", help="copy text verbatim to demonstrate the license guard")
    args = ap.parse_args()
    run(args.question, args.limit, args.sloppy)
