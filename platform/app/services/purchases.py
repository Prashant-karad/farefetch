from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AccessGrant, Account, Agent, BudgetPolicy, License, Purchase, Resource
from app.services.ledger import InsufficientFunds, post_transaction
from app.services.passes import issue_pass

PLATFORM_FEE_BPS = 1_000  # 10%, in basis points (1 bp = 0.01%)
PLATFORM_REVENUE_ACCOUNT = "acc_platform_revenue"


class PurchaseError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def _pass_response(purchase: Purchase, grant: AccessGrant, resource: Resource, already_owned: bool = False) -> dict:
    token = issue_pass(
        agent_id=grant.agent_id, grant_id=grant.id, resource_id=resource.id,
        path=resource.path, license_id=grant.license_id, expires_at=grant.expires_at,
    )
    return {
        "purchase_id": purchase.id,
        "grant_id": grant.id,
        "resource_id": resource.id,
        "price": purchase.price,
        "already_owned": already_owned,
        "pass_token": token,
        "expires_at": grant.expires_at.isoformat(),
    }


async def _fail(session: AsyncSession, purchase: Purchase, status: int, code: str, message: str):
    """Failures are recorded on the purchase (never in the ledger), then reported."""
    purchase.status = "failed"
    purchase.failure_reason = code
    await session.commit()
    raise PurchaseError(status, code, message)


async def _replay(session: AsyncSession, previous: Purchase, resource_id: str) -> dict:
    """Same Idempotency-Key again: return the original result, never charge twice."""
    if previous.resource_id != resource_id:
        raise PurchaseError(422, "idempotency_key_reused", "This Idempotency-Key was used for a different resource")
    if previous.status == "failed":
        raise PurchaseError(409, "previous_attempt_failed",
                            f"This request already failed ({previous.failure_reason}). Use a new Idempotency-Key.")
    if previous.status == "pending":
        raise PurchaseError(409, "duplicate_request", "This request is still being processed")
    grant = await session.scalar(select(AccessGrant).where(AccessGrant.purchase_id == previous.id))
    resource = await session.get(Resource, previous.resource_id)
    return _pass_response(previous, grant, resource)


async def purchase_pass(
    session: AsyncSession, *, agent: Agent, resource_id: str, idempotency_key: str, ai_reason: str | None
) -> dict:
    now = datetime.now(timezone.utc)

    # 1. Idempotency: seen this key from this agent before?
    previous = await session.scalar(
        select(Purchase).where(Purchase.agent_id == agent.id, Purchase.idempotency_key == idempotency_key)
    )
    if previous is not None:
        return await _replay(session, previous, resource_id)

    # 2. What are they buying?
    resource = await session.get(Resource, resource_id)
    if resource is None:
        raise PurchaseError(404, "resource_not_found", f"No resource {resource_id}")
    license_ = await session.get(License, resource.license_id)

    # 3. Lock the owner's wallet row: purchases by the same owner happen one at a time.
    wallet = await session.scalar(
        select(Account)
        .where(Account.type == "agent_wallet", Account.owner_id == agent.owner_id)
        .with_for_update()
    )
    payable = await session.scalar(
        select(Account).where(Account.type == "publisher_payable", Account.owner_id == resource.publisher_id)
    )

    # 4. Already holding a live pass? Expire stale ones, then hand back the live one free.
    await session.execute(
        update(AccessGrant)
        .where(AccessGrant.agent_id == agent.id, AccessGrant.resource_id == resource.id,
               AccessGrant.status == "active", AccessGrant.expires_at <= now)
        .values(status="expired")
        .execution_options(synchronize_session=False)
    )
    active = await session.scalar(
        select(AccessGrant).where(AccessGrant.agent_id == agent.id, AccessGrant.resource_id == resource.id,
                                  AccessGrant.status == "active")
    )
    if active is not None:
        original = await session.get(Purchase, active.purchase_id)
        await session.commit()
        return _pass_response(original, active, resource, already_owned=True)

    # 5. Record the attempt. Failed attempts are kept too.
    purchase = Purchase(agent_id=agent.id, resource_id=resource.id, price=resource.price,
                        status="pending", idempotency_key=idempotency_key, ai_reason=ai_reason)
    session.add(purchase)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise PurchaseError(409, "duplicate_request", "A request with this Idempotency-Key is already being processed")

    # 6. Budget rules.
    policy = await session.get(BudgetPolicy, agent.id)
    if policy is not None:
        if resource.price > policy.max_per_item:
            await _fail(session, purchase, 403, "over_item_limit", "Price is above this agent's per-item limit")
        if policy.approval_threshold is not None and resource.price > policy.approval_threshold:
            await _fail(session, purchase, 403, "approval_required",
                        "Price is above the owner's approval threshold; ask the owner first")
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)  # UTC day
        spent_today = await session.scalar(
            select(func.coalesce(func.sum(Purchase.price), 0))
            .where(Purchase.agent_id == agent.id, Purchase.status == "completed", Purchase.created_at >= start_of_day)
        )
        if spent_today + resource.price > policy.max_per_day:
            await _fail(session, purchase, 403, "over_daily_budget", "This purchase would exceed today's budget")

    # 7. Move the money: wallet -> publisher (90%) + platform (10%). All or nothing.
    fee = resource.price * PLATFORM_FEE_BPS // 10_000
    try:
        async with session.begin_nested():  # SAVEPOINT: undo only the money part if it fails
            txn = await post_transaction(
                session,
                type="purchase",
                reference=purchase.id,
                entries=[(wallet.id, -resource.price), (payable.id, resource.price - fee),
                         (PLATFORM_REVENUE_ACCOUNT, fee)],
                idempotency_key=f"purchase:{purchase.id}",
            )
    except InsufficientFunds:
        await _fail(session, purchase, 402, "insufficient_funds", "Wallet balance too low. Top up via PayPal.")

    # 8. Issue the time pass.
    grant = AccessGrant(agent_id=agent.id, resource_id=resource.id, purchase_id=purchase.id,
                        license_id=license_.id, expires_at=now + timedelta(hours=license_.ttl_hours))
    session.add(grant)
    purchase.status = "completed"
    purchase.transaction_id = txn.id
    await session.commit()
    return _pass_response(purchase, grant, resource)
