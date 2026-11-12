"""Endpoints behind the product pages: landing (/), the app (/app) with its Publisher and Agent-owner views.

Demo identity: the app acts as the seeded demo agent's owner and as one publisher at a time. A real product
would put these behind login; here they are disabled with DEMO_MODE=false (see require_demo).
"""

import asyncio
import html as htmlmod
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models import (AccessGrant, AccessLog, Account, Agent, BudgetPolicy, License, LedgerEntry, Payout,
                        Publisher, Purchase, Resource, Topup, UsageReceipt)
from app.redis_client import redis_client
from app.routers.demo import demo_agent, require_demo, usd
from app.services import llm, pricing
from app.services.budget_rules import parse_rule

STATIC = Path(__file__).resolve().parents[1] / "static"
router = APIRouter(tags=["product"], dependencies=[Depends(require_demo)])


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def landing():
    return HTMLResponse((STATIC / "index.html").read_text(encoding="utf-8"))


@router.get("/app", response_class=HTMLResponse, include_in_schema=False)
async def app_page():
    return HTMLResponse((STATIC / "app.html").read_text(encoding="utf-8"))


@router.get("/v1/demo/config")
async def config():
    """What the app needs to know about this deployment. The test buyer is only ever exposed for PayPal sandbox."""
    sandbox = "sandbox" in settings.paypal_base_url
    buyer = None
    if sandbox and settings.paypal_test_buyer_email:
        buyer = {"email": settings.paypal_test_buyer_email, "password": settings.paypal_test_buyer_password}
    return {"test_mode": sandbox, "test_buyer": buyer}


def ago(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


# =====================================================================================
# Landing: one real 402, fetched live from the gateway
# =====================================================================================
@router.get("/v1/demo/knock")
async def knock(path: str = "/blog/python-speed-benchmark"):
    """What an AI bot sees when it knocks without paying. Straight from the gateway."""
    if not re.fullmatch(r"/(blog|api)/[a-z0-9-]+", path):
        raise HTTPException(400, detail={"code": "bad_path", "message": "Path must look like /blog/<slug>"})
    t0 = time.perf_counter()
    async with httpx.AsyncClient(timeout=5) as c:
        r = await c.get(f"{settings.gateway_url}{path}", headers={"User-Agent": "ExampleAIBot/1.0"})
    return {"request": f"GET {path}", "user_agent": "ExampleAIBot/1.0", "status": r.status_code,
            "reason": "Payment Required" if r.status_code == 402 else r.reason_phrase,
            "ms": round((time.perf_counter() - t0) * 1000), "body": r.json()}


# =====================================================================================
# Publisher: setup (scan -> price -> go live -> test)
# =====================================================================================
class ScanRequest(BaseModel):
    url: str = Field(min_length=4, max_length=500)
    publisher_id: str | None = None


_TAG = re.compile(r"<[^>]+>")
_SKIP = re.compile(r"<(script|style|nav|footer|header|noscript)[^>]*>.*?</\1>", re.S | re.I)
_ASSET = re.compile(r"\.(css|js|png|jpe?g|gif|svg|ico|webp|pdf|zip|xml|json|woff2?)(\?|$)", re.I)


def page_text(raw: str, content_type: str) -> tuple[str | None, str]:
    """(title, readable text) from a page: our origin's JSON, or any HTML page."""
    if "json" in content_type:
        try:
            data = json.loads(raw)
            if isinstance(data, dict) and "body" in data:
                return data.get("title"), data["body"]
            return None, json.dumps(data)[:3000]
        except ValueError:
            pass
    m = re.search(r"<title[^>]*>(.*?)</title>", raw, re.S | re.I)
    title = htmlmod.unescape(m.group(1)).strip() if m else None
    text = htmlmod.unescape(_TAG.sub(" ", _SKIP.sub(" ", raw)))
    return title, re.sub(r"\s+", " ", text).strip()


async def discover_pages(client: httpx.AsyncClient, base: str) -> tuple[str, list[str], str | None]:
    """Find a site's pages the way a crawler would: sitemap.xml, then RSS, then links on the home page."""
    site_name = None
    try:
        r = await client.get(urljoin(base, "/sitemap.xml"))
        if r.status_code == 200 and "<loc>" in r.text:
            locs = [urljoin(base, l.strip()) for l in re.findall(r"<loc>(.*?)</loc>", r.text, re.S)]
            if "<sitemapindex" in r.text:  # an index of sitemaps: open the first few child sitemaps
                children = [l for l in locs if ".xml" in l][:3]
                locs = []
                for child in children:
                    try:
                        cr = await client.get(child)
                        locs += [l.strip() for l in re.findall(r"<loc>(.*?)</loc>", cr.text, re.S)]
                    except httpx.HTTPError:
                        continue
            locs = [l for l in locs if ".xml" not in l and urlparse(l).path not in ("", "/")]
            if locs:
                try:
                    site_name, _ = page_text((await client.get(base)).text, "text/html")
                except httpx.HTTPError:
                    pass
                return "sitemap.xml", locs, site_name
    except httpx.HTTPError:
        pass
    for feed in ("/feed", "/rss.xml", "/feed.xml", "/atom.xml", "/index.xml"):
        try:
            r = await client.get(urljoin(base, feed))
            links = re.findall(r"<link>(https?://[^<]+)</link>", r.text) or re.findall(r'<link[^>]+href="(https?://[^"]+)"', r.text)
            links = list(dict.fromkeys(l for l in links if urlparse(l).path not in ("", "/") and not _ASSET.search(urlparse(l).path)))
            if r.status_code == 200 and links:
                return f"RSS feed ({feed})", links, None
        except httpx.HTTPError:
            continue
    r = await client.get(base)
    site_name, _ = page_text(r.text, r.headers.get("content-type", ""))
    host = urlparse(str(r.url)).netloc
    links = []
    for href in re.findall(r'href="([^"#]+)"', r.text):
        u = urljoin(str(r.url), href)
        p = urlparse(u)
        if p.netloc == host and p.path.count("/") >= 1 and len(p.path) > 8 and not _ASSET.search(p.path) and u not in links:
            links.append(u)
    return "links on the home page", links, site_name


@router.post("/v1/demo/scan")
async def scan(body: ScanRequest, session: AsyncSession = Depends(get_session)):
    """Real scan of a website: find its pages, read them, and let the AI suggest a price for each."""
    url = body.url.strip()
    publisher_filter = body.publisher_id
    display_host = None
    if re.sub(r"^https?://", "", url).strip("/").lower() in ("codedojo.dev", "www.codedojo.dev"):
        # Code Dojo is the publisher this deployment hosts; its site runs privately behind the gateway
        url, publisher_filter, display_host = settings.origin_url, "pub_code_dojo", "codedojo.dev"
    if "://" not in url:
        url = "https://" + url
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise HTTPException(400, detail={"code": "bad_url", "message": "Enter a website address like https://example.com"})
    base = f"{parsed.scheme}://{parsed.netloc}"
    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=6, follow_redirects=True,
                                     headers={"User-Agent": "FairfetchSetupScanner/1.0 (+https://github.com/Prashant-karad/farefetch)"}) as client:
            method, urls, site_name = await discover_pages(client, base)
            urls = urls[:40]

            # Our demo site: only this publisher's pages (the origin hosts two publishers)
            known = {r.path: r for r in (await session.scalars(select(Resource))).all()}
            if publisher_filter:
                urls = [u for u in urls if urlparse(u).path not in known
                        or known[urlparse(u).path].publisher_id == publisher_filter]
            urls = urls[:10]

            blocked = []

            async def fetch(u: str):
                try:
                    r = await client.get(u)
                    if r.status_code in (401, 403, 429):
                        blocked.append(u)
                        return None
                    title, text = page_text(r.text, r.headers.get("content-type", ""))
                    return {"url": u, "path": urlparse(u).path, "title": title or urlparse(u).path, "text": text}
                except httpx.HTTPError:
                    return None
            pages = [p for p in await asyncio.gather(*(fetch(u) for u in urls)) if p and len(p["text"]) > 40]
    except httpx.HTTPError as exc:
        raise HTTPException(502, detail={"code": "site_unreachable", "message": f"Could not reach {base}: {type(exc).__name__}"})
    if not pages and blocked:
        raise HTTPException(403, detail={"code": "site_blocks_bots", "message":
            f"{parsed.netloc} blocks automated readers (HTTP 403). That is the problem Fairfetch solves: "
            "instead of blocking bots, the site can charge them. Try the demo site to see setup end to end."})
    if not pages:
        raise HTTPException(404, detail={"code": "no_pages", "message": "No readable pages found (no sitemap, feed or links)"})

    # One AI call prices every page; deterministic fallback if the model is unavailable
    listing = [{"i": i, "title": p["title"][:120], "excerpt": p["text"][:500]} for i, p in enumerate(pages)]
    ai = await llm.generate_json(
        "You price web pages for AI agents that want to read them. For each page rate how UNIQUE and VALUABLE it "
        "is to an AI answering questions, 0 (generic, available everywhere) to 100 (original data or tests, hard "
        "to find elsewhere). Give a short reason (max 12 words) a publisher would understand.\n"
        f"PAGES:\n{json.dumps(listing)}\n"
        'Return JSON {"pages": [{"i": int, "uniqueness": int, "reason": str}]}'
    )
    ai_by_i = {}
    if ai and isinstance(ai.get("pages"), list):
        ai_by_i = {p.get("i"): p for p in ai["pages"] if isinstance(p, dict) and isinstance(p.get("uniqueness"), int)}

    out = []
    for i, p in enumerate(pages):
        if i in ai_by_i:
            score, reason, source = max(0, min(100, ai_by_i[i]["uniqueness"])), str(ai_by_i[i].get("reason", ""))[:160], "ai"
        else:
            score, reason = pricing.heuristic_uniqueness(p["text"], [q["text"] for q in pages if q is not p])
            source = "heuristic"
        price = pricing.price_for(score)
        res = known.get(p["path"])
        out.append({
            "path": p["path"], "url": p["url"], "title": p["title"], "words": len(p["text"].split()),
            "excerpt": " ".join(p["text"].split()[:26]) + " …",
            "kind": "api" if p["path"].startswith("/api/") else "article",
            "uniqueness": score, "suggested_price": price, "suggested_display": usd(price), "reason": reason,
            "priced_by": source, "resource_id": res.id if res else None,
            "current_price": res.price if res else None, "current_license": res.license_id if res else None,
        })
    out.sort(key=lambda x: -x["uniqueness"])
    if display_host:
        site_name, base = "Code Dojo", f"https://{display_host}"
        for page in out:
            page["url"] = base + page["path"]
    return {"site": site_name or parsed.netloc, "base": base, "found_via": method, "pages": out,
            "ms": round((time.perf_counter() - t0) * 1000), "ai_model": f"{llm.provider()} ({llm.model()})" if ai_by_i else None,
            "connectable": any(p["resource_id"] for p in out)}


class GoLiveItem(BaseModel):
    resource_id: str
    price: int = Field(ge=10, le=5000)
    license_id: str


class GoLiveRequest(BaseModel):
    items: list[GoLiveItem] = Field(min_length=1, max_length=100)


@router.post("/v1/demo/go-live")
async def go_live(body: GoLiveRequest, session: AsyncSession = Depends(get_session)):
    """Apply the chosen prices and licenses. The gateway picks them up immediately (cache invalidated)."""
    licenses = {l.id for l in (await session.scalars(select(License))).all()}
    changed = []
    for item in body.items:
        res = await session.get(Resource, item.resource_id)
        if res is None or item.license_id not in licenses:
            raise HTTPException(400, detail={"code": "bad_item", "message": f"Unknown resource or license: {item.resource_id}"})
        res.price, res.license_id = item.price, item.license_id
        changed.append(res.path)
    await session.commit()
    for path in changed:
        await redis_client.delete(f"gw:resource:{path}")
    return {"live": len(changed), "paths": changed}


class TestBotRequest(BaseModel):
    path: str = Field(pattern=r"^/(blog|api)/[a-z0-9-]+$")


@router.post("/v1/demo/test-bot")
async def test_bot(body: TestBotRequest):
    """Sends a real unpaid AI-bot request through the gateway and returns exactly what came back."""
    t0 = time.perf_counter()
    async with httpx.AsyncClient(timeout=5) as c:
        r = await c.get(f"{settings.gateway_url}{body.path}", headers={"User-Agent": "ExampleAIBot/1.0 (test)"})
    try:
        payload = r.json()
    except ValueError:
        payload = {"raw": r.text[:300]}
    return {"status": r.status_code, "ms": round((time.perf_counter() - t0) * 1000),
            "headers": {k: v for k, v in r.headers.items() if k in ("content-type", "server")}, "body": payload}


@router.get("/v1/demo/licenses")
async def licenses(session: AsyncSession = Depends(get_session)):
    return [{"id": l.id, "type": l.type, "max_quote_words": l.max_quote_words, "ttl_hours": l.ttl_hours,
             "attribution_required": l.attribution_required}
            for l in (await session.scalars(select(License).order_by(License.ttl_hours.desc()))).all()]


# =====================================================================================
# Publisher: overview
# =====================================================================================
@router.get("/v1/demo/publishers")
async def publishers(session: AsyncSession = Depends(get_session)):
    return [{"id": p.id, "name": p.name} for p in (await session.scalars(select(Publisher).order_by(Publisher.name))).all()]


@router.get("/v1/demo/publisher/{publisher_id}")
async def publisher_view(publisher_id: str, session: AsyncSession = Depends(get_session)):
    pub = await session.get(Publisher, publisher_id)
    if pub is None:
        raise HTTPException(404, detail={"code": "publisher_not_found", "message": "No such publisher"})
    acct = await session.scalar(select(Account).where(Account.type == "publisher_payable", Account.owner_id == pub.id))
    earned = await session.scalar(select(func.coalesce(func.sum(LedgerEntry.amount), 0))
                                  .where(LedgerEntry.account_id == acct.id, LedgerEntry.amount > 0))
    resources = (await session.scalars(select(Resource).where(Resource.publisher_id == pub.id)
                                       .order_by(Resource.price.desc()))).all()
    rmap = {r.id: r for r in resources}

    counts: dict[str, dict[str, int]] = {}
    for rid, result, n in (await session.execute(
            select(AccessLog.resource_id, AccessLog.result, func.count())
            .where(AccessLog.resource_id.in_(rmap.keys())).group_by(AccessLog.resource_id, AccessLog.result))).all():
        counts.setdefault(rid, {})[result] = n
    total = lambda key: sum(c.get(key, 0) for c in counts.values())  # noqa: E731

    sales = (await session.execute(
        select(Purchase, Agent).join(Agent).where(Purchase.resource_id.in_(rmap.keys()), Purchase.status == "completed")
        .order_by(Purchase.created_at.desc()).limit(12))).all()

    receipts = []
    for rc in (await session.scalars(select(UsageReceipt).order_by(UsageReceipt.created_at.desc()).limit(30))).all():
        mine = [i for i in (rc.items or []) if i.get("resource_id") in rmap and i.get("used")]
        if not mine:
            continue
        caught = [v for v in (rc.violations or []) if v.get("resource_id") in rmap]
        receipts.append({
            "id": rc.id, "time": ago(rc.created_at), "passed": rc.passed, "caught": len(caught),
            "caught_types": sorted({v["type"] for v in caught}),
            "items": [{"title": rmap[i["resource_id"]].title, "how_used": i.get("how_used"),
                       "longest_copied_run": i.get("longest_copied_run"), "max_quote_words": i.get("max_quote_words"),
                       "cited": i.get("cited")} for i in mine],
        })
        if len(receipts) >= 6:
            break

    payouts = (await session.scalars(select(Payout).where(Payout.publisher_id == pub.id)
                                     .order_by(Payout.created_at.desc()).limit(5))).all()
    paid = sum(p.amount for p in payouts if p.status in ("sent", "completed", "pending", "success"))
    return {
        "id": pub.id, "name": pub.name, "paypal_email": pub.paypal_email,
        "balance": int(acct.balance), "balance_display": usd(acct.balance), "earned": int(earned),
        "earned_display": usd(earned), "paid_display": usd(paid), "payable_now_cents": int(acct.balance) // 100,
        "stats": {"asked_to_pay": total("payment_required"), "paid_reads": total("granted"),
                  "blocked": total("forbidden") + total("invalid_pass") + total("unauthenticated"),
                  "sales": len(sales), "receipts": len(receipts)},
        "visitors": [{"agent": a.name, "title": rmap[p.resource_id].title, "price": usd(p.price),
                      "reason": p.ai_reason, "time": ago(p.created_at)} for p, a in sales],
        "receipts": receipts,
        "payouts": [{"amount": usd(p.amount), "status": p.status, "batch": p.paypal_batch_id,
                     "time": ago(p.created_at)} for p in payouts],
        "content": [{"resource_id": r.id, "title": r.title, "path": r.path, "kind": r.kind, "price": r.price,
                     "price_display": usd(r.price), "license_id": r.license_id,
                     "asked": counts.get(r.id, {}).get("payment_required", 0),
                     "paid_reads": counts.get(r.id, {}).get("granted", 0)} for r in resources],
    }


# =====================================================================================
# Agent owner
# =====================================================================================
@router.get("/v1/demo/owner")
async def owner_view(session: AsyncSession = Depends(get_session)):
    agent = await demo_agent(session)
    wallet = await session.scalar(select(Account).where(Account.type == "agent_wallet", Account.owner_id == agent.owner_id))
    policy = await session.get(BudgetPolicy, agent.id)
    start_of_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    spent_today = await session.scalar(
        select(func.coalesce(func.sum(Purchase.price), 0))
        .where(Purchase.agent_id == agent.id, Purchase.status == "completed", Purchase.created_at >= start_of_day))
    now = datetime.now(timezone.utc)
    passes = (await session.execute(
        select(AccessGrant, Resource, Publisher).join(Resource, AccessGrant.resource_id == Resource.id).join(Publisher)
        .where(AccessGrant.agent_id == agent.id, AccessGrant.status == "active", AccessGrant.expires_at > now)
        .order_by(AccessGrant.expires_at.desc()).limit(8))).all()
    topups = (await session.scalars(select(Topup).where(Topup.owner_id == agent.owner_id)
                                    .order_by(Topup.created_at.desc()).limit(4))).all()
    return {
        "agent": {"id": agent.id, "name": agent.name},
        "wallet": {"balance": int(wallet.balance), "display": usd(wallet.balance)},
        "rules": None if policy is None else {
            "max_per_item": policy.max_per_item, "max_per_item_display": usd(policy.max_per_item),
            "max_per_day": policy.max_per_day, "max_per_day_display": usd(policy.max_per_day),
            "approval_threshold": policy.approval_threshold,
            "approval_display": usd(policy.approval_threshold) if policy.approval_threshold else None},
        "spent_today": int(spent_today), "spent_today_display": usd(spent_today),
        "passes": [{"grant_id": g.id, "title": r.title, "publisher": p.name, "license_id": g.license_id,
                    "path": r.path, "expires_at": g.expires_at.isoformat()} for g, r, p in passes],
        "topups": [{"amount": usd(t.amount), "status": t.status, "order": t.paypal_order_id,
                    "time": ago(t.created_at)} for t in topups],
    }


class RuleRequest(BaseModel):
    rule: str = Field(min_length=3, max_length=500)


@router.put("/v1/demo/rules")
async def set_rules(body: RuleRequest, session: AsyncSession = Depends(get_session)):
    """Owner writes a spending rule in plain English; the AI turns it into limits the platform enforces."""
    agent = await demo_agent(session)
    parsed = await parse_rule(body.rule)
    policy = await session.get(BudgetPolicy, agent.id)
    if policy is None:
        policy = BudgetPolicy(agent_id=agent.id, max_per_item=500, max_per_day=10_000)
        session.add(policy)
    if parsed["max_per_item"]:
        policy.max_per_item = parsed["max_per_item"]
    if parsed["max_per_day"]:
        policy.max_per_day = parsed["max_per_day"]
    if parsed["approval_threshold"] is not None:
        policy.approval_threshold = parsed["approval_threshold"] or None
    await session.commit()
    return {"interpreted_by": f"{llm.provider()} ({llm.model()})" if parsed["source"] == "llm" else "pattern rules",
            "explanation": parsed["explanation"],
            "rules": {"max_per_item_display": usd(policy.max_per_item), "max_per_day_display": usd(policy.max_per_day),
                      "approval_display": usd(policy.approval_threshold) if policy.approval_threshold else None}}
