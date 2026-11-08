from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Account, Topup
from app.services import paypal_client
from app.services.ledger import post_transaction
from app.services.paypal_client import PayPalError

UNITS_PER_DOLLAR = 10_000


class TopupError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


async def start_topup(session: AsyncSession, *, owner_id: str, amount: Decimal) -> dict:
    units = int(amount * UNITS_PER_DOLLAR)

    # 1. Save our record FIRST and commit, so it exists even if the PayPal call fails or hangs.
    topup = Topup(owner_id=owner_id, amount=units, status="created")
    session.add(topup)
    await session.commit()

    # 2. Call PayPal OUTSIDE any database transaction (never hold locks during network calls).
    try:
        order = await paypal_client.create_order(
            topup_id=topup.id,
            amount_value=f"{amount:.2f}",
            return_url=f"{settings.public_base_url}/v1/topups/paypal/return",
            cancel_url=f"{settings.public_base_url}/v1/topups/paypal/cancel",
        )
        approve_url = paypal_client.approval_link(order)
    except PayPalError:
        topup.status = "failed"
        await session.commit()
        raise TopupError(502, "paypal_unavailable", "Could not create a PayPal order. Try again.")

    # 3. Remember PayPal's order ID so we can match the return/capture to this top-up.
    topup.paypal_order_id = order["id"]
    await session.commit()
    return {"topup_id": topup.id, "status": topup.status, "amount": units,
            "paypal_order_id": order["id"], "approve_url": approve_url}


async def complete_topup(session: AsyncSession, *, order_id: str) -> Topup:
    topup = await session.scalar(select(Topup).where(Topup.paypal_order_id == order_id))
    if topup is None:
        raise TopupError(404, "topup_not_found", "No top-up for this PayPal order")
    if topup.status == "completed":
        return topup  # already done (page refreshed, or webhook got there first)
    await session.commit()  # end the read transaction before the network call

    # 1. Capture: this is when money actually moves at PayPal. Idempotent via PayPal-Request-Id.
    try:
        capture = await paypal_client.capture_order(order_id)
    except PayPalError:
        raise TopupError(502, "capture_failed", "PayPal could not capture this payment.")

    # 2. Never trust, always verify: status, currency, amount, and that it's OUR order.
    unit = capture["purchase_units"][0]
    cap = unit["payments"]["captures"][0]
    if capture.get("status") != "COMPLETED" or cap.get("status") != "COMPLETED":
        raise TopupError(409, "capture_not_completed", f"Capture status is {cap.get('status')}")
    captured = int(Decimal(cap["amount"]["value"]) * UNITS_PER_DOLLAR)
    if cap["amount"]["currency_code"] != "USD" or captured != topup.amount or unit.get("reference_id") != topup.id:
        raise TopupError(409, "capture_mismatch", "Captured payment does not match the top-up")

    # 3. Lock our row and credit the wallet exactly once.
    topup = await session.scalar(select(Topup).where(Topup.id == topup.id).with_for_update())
    if topup.status == "completed":
        return topup
    wallet = await session.scalar(
        select(Account).where(Account.type == "agent_wallet", Account.owner_id == topup.owner_id)
    )
    await post_transaction(
        session, type="topup", reference=topup.id,
        entries=[("acc_paypal_clearing", -topup.amount), (wallet.id, topup.amount)],
        idempotency_key=f"topup:{topup.id}",
    )
    topup.status = "completed"
    topup.completed_at = datetime.now(timezone.utc)
    await session.commit()
    return topup