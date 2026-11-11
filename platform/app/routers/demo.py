"""Live story page (/live) and the endpoints behind it.

The page drives the REAL system: it starts the real research agent as a subprocess (which talks to the
gateway and platform over HTTP exactly as it does from the CLI) and streams the agent's structured trace
to the browser with Server-Sent Events. Everything else on the page is read back from PostgreSQL.

Demo-only: these endpoints act as the seeded demo agent and the operator. They are disabled when
DEMO_MODE=false. A real product would put them behind owner/publisher login.
"""

import asyncio
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import httpx
import jwt
from cryptography.hazmat.primitives import serialization
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import engine, get_session
from app.models import (AccessGrant, Account, Agent, BudgetPolicy, LedgerEntry, Payout, Publisher, Purchase,
                        Resource, Topup, Transaction)
from app.redis_client import redis_client
from app.services.auth import authenticate_api_key
from app.services.keys import PRIVATE_KEY
from app.services.payouts import settle_publishers
from app.services.paypal_client import PayPalError
from app.services.topups import TopupError, complete_topup, start_topup

ROOT = Path(__file__).resolve().parents[3]
AGENT_DIR = ROOT / "agent"
PAGE = Path(__file__).resolve().parents[1] / "static" / "live.html"
PUBLIC_KEY = serialization.load_pem_private_key(PRIVATE_KEY.encode(), password=None).public_key()
PUBLIC_PEM = PUBLIC_KEY.public_bytes(serialization.Encoding.PEM,
                                     serialization.PublicFormat.SubjectPublicKeyInfo).decode()

_run_lock = asyncio.Lock()  # one agent run at a time: it is one wallet


def require_demo() -> None:
    if not settings.demo_mode:
        raise HTTPException(404, detail={"code": "not_found", "message": "Demo mode is off"})


router = APIRouter(tags=["live demo"], dependencies=[Depends(require_demo)])


def usd(units: int | None) -> str:
    units = int(units or 0)
    sign = "-" if units < 0 else ""
    units = abs(units)
    return f"{sign}${units // 10_000}.{units % 10_000:04d}"


async def demo_agent(session: AsyncSession) -> Agent:
    agent = await authenticate_api_key(session, settings.demo_agent_api_key or "")
    if agent is None:
        raise HTTPException(503, detail={"code": "no_demo_agent", "message": "Set DEMO_AGENT_API_KEY in .env"})
    return agent


@router.get("/live", response_class=HTMLResponse, include_in_schema=False)
async def live_page():
    return HTMLResponse(PAGE.read_text(encoding="utf-8"))


# ---------- Is every part of the system really up? ----------
@router.get("/v1/demo/health")
async def health():
    async def probe(name: str, coro):
        t0 = time.perf_counter()
        try:
            detail = await coro
            return {"name": name, "ok": True, "ms": round((time.perf_counter() - t0) * 1000), "detail": detail}
        except Exception as exc:
            return {"name": name, "ok": False, "ms": None, "detail": type(exc).__name__}

    async def http_ok(url: str) -> str:
        async with httpx.AsyncClient(timeout=3) as c:
            r = await c.get(url)
            r.raise_for_status()
            return url.split("//", 1)[1].split("/", 1)[0]

    async def db() -> str:
        async with engine.connect() as conn:
            return (await conn.exec_driver_sql("SHOW server_version")).scalar().split()[0]

    async def redis() -> str:
        await redis_client.ping()
        return "PING → PONG"

    async def configured(value: str | None, label: str) -> str:
        if not value:
            raise RuntimeError("not configured")
        return label

    checks = await asyncio.gather(
        probe("Gateway", http_ok(f"{settings.gateway_url}/health")),
        probe("Platform", configured("ok", "this server")),
        probe("Publisher origin", http_ok(f"{settings.origin_url}/health")),
        probe("PostgreSQL", db()),
        probe("Redis", redis()),
        probe("PayPal", configured(settings.paypal_client_id,
                                   "sandbox" if "sandbox" in settings.paypal_base_url else "live")),
        probe("AI model", configured(settings.groq_api_key or settings.gemini_api_key,
                                     settings.llm_model or settings.llm_provider)),
    )
    return {"checks": checks}


# ---------- Run the real agent and stream its trace ----------
def agent_command(question: str, sloppy: bool, run_id: str) -> list[str]:
    venv_python = AGENT_DIR / ".venv" / "bin" / "python"
    python = str(venv_python) if venv_python.exists() else sys.executable
    cmd = [python, "-m", "app.main", question, "--events", "--run-id", run_id]
    return cmd + (["--sloppy"] if sloppy else [])


def sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, default=str)}\n\n"


@router.get("/v1/demo/run")
async def run_agent(q: str = "How do I make my slow Python code faster, and which approach gives the biggest speed-up?",
                    sloppy: bool = False):
    """Starts the research agent and streams every step it takes (Server-Sent Events)."""
    q = q.strip()[:300] or "How do I learn Python fast?"

    async def stream():
        if _run_lock.locked():
            yield sse({"event": "error", "message": "Another agent run is in progress. Wait for it to finish."})
            return
        async with _run_lock:
            run_id = f"live-{uuid.uuid4().hex[:12]}"
            proc = await asyncio.create_subprocess_exec(
                *agent_command(q, sloppy, run_id), cwd=AGENT_DIR,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )
            yield sse({"event": "process", "pid": proc.pid, "run_id": run_id,
                       "command": f"python -m app.main \"{q}\" --events" + (" --sloppy" if sloppy else "")})
            try:
                while True:
                    try:
                        line = await asyncio.wait_for(proc.stdout.readline(), timeout=15)
                    except asyncio.TimeoutError:
                        yield ": keep-alive\n\n"  # comment line: keeps proxies from closing the stream
                        continue
                    if not line:
                        break
                    text = line.decode(errors="replace").strip()
                    if text.startswith("{"):
                        yield f"data: {text}\n\n"
                code = await proc.wait()
                if code != 0:
                    err = (await proc.stderr.read()).decode(errors="replace").strip().splitlines()
                    yield sse({"event": "error", "message": err[-1] if err else f"agent exited with {code}"})
                yield sse({"event": "closed", "exit_code": code})
            finally:
                if proc.returncode is None:
                    proc.kill()

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------- What each party sees, straight from the database ----------
ACCOUNT_LABELS = {"platform_revenue": "Fairfetch fee", "paypal_clearing": "PayPal (outside money)"}


@router.get("/v1/demo/state")
async def state(session: AsyncSession = Depends(get_session)):
    agent = await demo_agent(session)
    wallet = await session.scalar(select(Account).where(Account.type == "agent_wallet",
                                                        Account.owner_id == agent.owner_id))
    policy = await session.get(BudgetPolicy, agent.id)
    start_of_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    spent_today = await session.scalar(
        select(func.coalesce(func.sum(Purchase.price), 0))
        .where(Purchase.agent_id == agent.id, Purchase.status == "completed", Purchase.created_at >= start_of_day))

    names = {p.id: p.name for p in (await session.scalars(select(Publisher))).all()}
    publishers = []
    for pub_id, name in sorted(names.items(), key=lambda kv: kv[1]):
        acct = await session.scalar(select(Account).where(Account.type == "publisher_payable",
                                                          Account.owner_id == pub_id))
        earned = await session.scalar(select(func.coalesce(func.sum(LedgerEntry.amount), 0))
                                      .where(LedgerEntry.account_id == acct.id, LedgerEntry.amount > 0))
        paid = await session.scalar(select(func.coalesce(func.sum(Payout.amount), 0))
                                    .where(Payout.publisher_id == pub_id, Payout.status.in_(["sent", "completed"])))
        reads = (await session.execute(
            select(Resource.title, Purchase.price, Purchase.created_at, Purchase.ai_reason)
            .join(Resource).where(Resource.publisher_id == pub_id, Purchase.status == "completed")
            .order_by(Purchase.created_at.desc()).limit(4))).all()
        publishers.append({
            "id": pub_id, "name": name, "balance": int(acct.balance), "balance_display": usd(acct.balance),
            "earned_display": usd(earned), "paid_display": usd(paid),
            "recent_sales": [{"title": t, "price": usd(p), "time": c.isoformat(timespec="seconds"),
                              "reason": r} for t, p, c, r in reads],
        })

    # Last few money events as double-entry rows
    accounts = {a.id: a for a in (await session.scalars(select(Account))).all()}

    def label(acc: Account) -> str:
        if acc.type == "agent_wallet":
            return "Agent wallet"
        if acc.type == "publisher_payable":
            return names.get(acc.owner_id, acc.owner_id)
        return ACCOUNT_LABELS.get(acc.type, acc.type)

    txns = (await session.scalars(select(Transaction).order_by(Transaction.created_at.desc()).limit(8))).all()
    ledger = []
    for t in txns:
        entries = (await session.scalars(select(LedgerEntry).where(LedgerEntry.transaction_id == t.id)
                                         .order_by(LedgerEntry.amount))).all()
        ledger.append({"id": t.id, "type": t.type, "time": t.created_at.isoformat(timespec="seconds"),
                       "sum": sum(e.amount for e in entries),
                       "entries": [{"account": label(accounts[e.account_id]), "amount": e.amount,
                                    "display": usd(e.amount)} for e in entries]})
    unbalanced = (await session.execute(
        select(LedgerEntry.transaction_id).group_by(LedgerEntry.transaction_id)
        .having(func.sum(LedgerEntry.amount) != 0))).all()
    total_entries = await session.scalar(select(func.count(LedgerEntry.id)))

    payouts = [{"publisher": names.get(p.publisher_id), "amount": usd(p.amount), "status": p.status,
                "batch": p.paypal_batch_id, "time": p.created_at.isoformat(timespec="seconds")}
               for p in (await session.scalars(select(Payout).order_by(Payout.created_at.desc()).limit(4))).all()]
    topups = [{"amount": usd(t.amount), "status": t.status, "order": t.paypal_order_id,
               "time": t.created_at.isoformat(timespec="seconds")}
              for t in (await session.scalars(select(Topup).order_by(Topup.created_at.desc()).limit(3))).all()]

    return {
        "agent": {"id": agent.id, "name": agent.name},
        "wallet": {"balance": int(wallet.balance), "display": usd(wallet.balance)},
        "budget": None if policy is None else {
            "max_per_item": policy.max_per_item, "max_per_day": policy.max_per_day,
            "spent_today": int(spent_today), "spent_today_display": usd(spent_today),
            "max_per_item_display": usd(policy.max_per_item), "max_per_day_display": usd(policy.max_per_day)},
        "publishers": publishers,
        "ledger": ledger,
        "ledger_balanced": not unbalanced,
        "ledger_entries_total": total_entries,
        "payouts": payouts,
        "topups": topups,
    }


# ---------- Proof: verify a signature with the PUBLIC key only ----------
class VerifyRequest(BaseModel):
    token: str = Field(max_length=20_000)


@router.post("/v1/demo/verify")
async def verify(body: VerifyRequest):
    """Verifies a pass or usage receipt with the public key, exactly as a publisher or the gateway would."""
    try:
        header = jwt.get_unverified_header(body.token)
        claims = jwt.decode(body.token, PUBLIC_KEY, algorithms=["ES256"], options={"verify_exp": False,
                                                                                    "verify_aud": False})
        return {"valid": True, "header": header, "claims": claims, "public_key": PUBLIC_PEM}
    except jwt.PyJWTError as exc:
        return {"valid": False, "error": str(exc), "public_key": PUBLIC_PEM}


# ---------- Operator controls ----------
@router.post("/v1/demo/reset-passes")
async def reset_passes(session: AsyncSession = Depends(get_session)):
    """Expire the demo agent's active passes so the next run has to pay again."""
    agent = await demo_agent(session)
    result = await session.execute(
        update(AccessGrant).where(AccessGrant.agent_id == agent.id, AccessGrant.status == "active")
        .values(status="expired", expires_at=datetime.now(timezone.utc)))
    await session.commit()
    return {"expired": result.rowcount}


@router.post("/v1/demo/settle")
async def settle(session: AsyncSession = Depends(get_session)):
    try:
        return await settle_publishers(session)
    except PayPalError as exc:
        raise HTTPException(502, detail={"code": "paypal_error", "message": str(exc)[:300]})


@router.post("/v1/demo/topup")
async def topup(session: AsyncSession = Depends(get_session)):
    agent = await demo_agent(session)
    try:
        return await start_topup(session, owner_id=agent.owner_id, amount=Decimal("5.00"))
    except TopupError as exc:
        raise HTTPException(exc.status, detail={"code": exc.code, "message": exc.message})


@router.post("/v1/demo/topup/{order_id}/capture")
async def capture(order_id: str, session: AsyncSession = Depends(get_session)):
    """Same as the PayPal return URL, for when the browser can't reach it (e.g. Codespaces ports)."""
    try:
        t = await complete_topup(session, order_id=order_id)
    except TopupError as exc:
        raise HTTPException(exc.status, detail={"code": exc.code, "message": exc.message})
    return {"status": t.status, "amount": usd(t.amount)}
