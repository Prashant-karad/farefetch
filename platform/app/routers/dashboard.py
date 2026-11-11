"""Read-only dashboard data + the page itself. Public for the demo (no secrets, only demo data);
a real product would put this behind publisher / owner login."""

from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import (AccessLog, Account, Agent, LedgerEntry, Payout, Publisher, Purchase, Resource,
                        Topup, UsageReceipt)

router = APIRouter(tags=["dashboard"])
PAGE = Path(__file__).resolve().parents[1] / "static" / "dashboard.html"


def usd(units: int | None) -> str:
    units = units or 0
    sign = "-" if units < 0 else ""
    units = abs(units)
    return f"{sign}${units // 10_000}.{units % 10_000:04d}"


@router.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
async def dashboard_page():
    return HTMLResponse(PAGE.read_text(encoding="utf-8"))


@router.get("/v1/dashboard/data")
async def dashboard_data(session: AsyncSession = Depends(get_session)):
    # Publishers: balance owed, lifetime earned, paid out
    publishers = []
    for pub in (await session.scalars(select(Publisher).order_by(Publisher.name))).all():
        acct = await session.scalar(select(Account).where(Account.type == "publisher_payable",
                                                          Account.owner_id == pub.id))
        earned = await session.scalar(select(func.coalesce(func.sum(LedgerEntry.amount), 0))
                                      .where(LedgerEntry.account_id == acct.id, LedgerEntry.amount > 0))
        paid = await session.scalar(select(func.coalesce(func.sum(Payout.amount), 0))
                                    .where(Payout.publisher_id == pub.id, Payout.status.in_(["sent", "completed"])))
        sales = await session.scalar(select(func.count(Purchase.id)).join(Resource)
                                     .where(Resource.publisher_id == pub.id, Purchase.status == "completed"))
        publishers.append({"publisher": pub.name, "paypal_email": pub.paypal_email, "sales": sales,
                           "earned": usd(earned), "paid_out": usd(paid), "balance_owed": usd(acct.balance)})

    # Per-resource usage: requests by outcome, sales, receipts
    access = (await session.execute(
        select(AccessLog.resource_id, AccessLog.result, func.count()).group_by(AccessLog.resource_id, AccessLog.result)
    )).all()
    by_res: dict[str, dict[str, int]] = {}
    for rid, result, n in access:
        by_res.setdefault(rid or "-", {})[result] = n
    resources = []
    for r, pub in (await session.execute(select(Resource, Publisher).join(Publisher).order_by(Resource.path))).all():
        counts = by_res.get(r.id, {})
        resources.append({"title": r.title, "path": r.path, "kind": r.kind, "publisher": pub.name,
                          "price": usd(r.price), "license": r.license_id, "uniqueness": r.uniqueness_score,
                          "402_shown": counts.get("payment_required", 0), "granted": counts.get("granted", 0),
                          "blocked": counts.get("forbidden", 0) + counts.get("invalid_pass", 0)
                          + counts.get("unauthenticated", 0)})

    # Agent-owner view: purchases with the AI's reasons
    purchases = [{
        "time": p.created_at.isoformat(timespec="seconds"), "agent": a.name, "resource": r.title,
        "price": usd(p.price), "status": p.status, "failure_reason": p.failure_reason, "ai_reason": p.ai_reason,
    } for p, a, r in (await session.execute(
        select(Purchase, Agent, Resource).join(Agent).join(Resource).order_by(Purchase.created_at.desc()).limit(200)
    )).all()]

    receipts = [{
        "time": rc.created_at.isoformat(timespec="seconds"), "receipt_id": rc.id, "passed": rc.passed,
        "violations_found": len(rc.violations or []),
        "violation_types": ", ".join(sorted({v.get("type", "") for v in (rc.violations or [])})),
        "items": ", ".join(f"{i.get('resource_id')}:{i.get('how_used')}" for i in (rc.items or [])),
    } for rc in (await session.scalars(select(UsageReceipt).order_by(UsageReceipt.created_at.desc()).limit(100))).all()]

    wallets = [{"owner_id": w.owner_id, "balance": usd(w.balance)} for w in
               (await session.scalars(select(Account).where(Account.type == "agent_wallet"))).all()]
    topups = [{"time": t.created_at.isoformat(timespec="seconds"), "amount": usd(t.amount), "status": t.status,
               "paypal_order_id": t.paypal_order_id}
              for t in (await session.scalars(select(Topup).order_by(Topup.created_at.desc()).limit(50))).all()]
    payouts = [{"time": p.created_at.isoformat(timespec="seconds"), "publisher_id": p.publisher_id,
                "amount": usd(p.amount), "status": p.status, "paypal_batch_id": p.paypal_batch_id}
               for p in (await session.scalars(select(Payout).order_by(Payout.created_at.desc()).limit(50))).all()]

    unbalanced = (await session.execute(
        select(LedgerEntry.transaction_id).group_by(LedgerEntry.transaction_id).having(func.sum(LedgerEntry.amount) != 0)
    )).all()
    return {"publishers": publishers, "resources": resources, "purchases": purchases, "receipts": receipts,
            "wallets": wallets, "topups": topups, "payouts": payouts,
            "ledger_balanced": len(unbalanced) == 0}
