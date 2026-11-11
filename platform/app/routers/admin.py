"""Operator actions: settle publishers, check payout status, set publisher PayPal emails,
AI price suggestions. Protected by the admin token (we reuse INTERNAL_TOKEN for the demo)."""

import hmac

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models import Publisher, Resource
from app.redis_client import redis_client
from app.services import pricing
from app.services.payouts import refresh_payout_status, settle_publishers
from app.services.paypal_client import PayPalError


async def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    if x_admin_token is None or not hmac.compare_digest(x_admin_token, settings.internal_token):
        raise HTTPException(403, detail={"code": "forbidden", "message": "Admin token required"})


router = APIRouter(prefix="/v1/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.post("/payouts/settle")
async def settle(session: AsyncSession = Depends(get_session)):
    """Pay every publisher their whole-cent earnings through one PayPal Payouts batch."""
    return await settle_publishers(session)


@router.get("/payouts/{paypal_batch_id}")
async def payout_status(paypal_batch_id: str, session: AsyncSession = Depends(get_session)):
    try:
        return await refresh_payout_status(session, paypal_batch_id)
    except PayPalError as exc:
        raise HTTPException(502, detail={"code": "paypal_error", "message": str(exc)[:500]})


class PublisherEmail(BaseModel):
    paypal_email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=320)


@router.put("/publishers/{publisher_id}/paypal-email")
async def set_publisher_email(publisher_id: str, body: PublisherEmail, session: AsyncSession = Depends(get_session)):
    publisher = await session.get(Publisher, publisher_id)
    if publisher is None:
        raise HTTPException(404, detail={"code": "publisher_not_found", "message": "No such publisher"})
    publisher.paypal_email = body.paypal_email
    await session.commit()
    return {"publisher_id": publisher.id, "paypal_email": publisher.paypal_email}


@router.post("/resources/{resource_id}/price-suggestion")
async def price_suggestion(resource_id: str, apply: bool = False, session: AsyncSession = Depends(get_session)):
    """AI rates the content's uniqueness and suggests a price. ?apply=true saves it."""
    resource = await session.get(Resource, resource_id)
    if resource is None:
        raise HTTPException(404, detail={"code": "resource_not_found", "message": "No such resource"})
    async with httpx.AsyncClient(base_url=settings.origin_url, timeout=10.0) as client:
        texts = {}
        for r in (await session.scalars(select(Resource).where(Resource.kind == "article"))).all():
            try:
                resp = await client.get(r.path)
                texts[r.id] = resp.json().get("body", "") if resp.status_code == 200 else r.preview
            except httpx.HTTPError:
                texts[r.id] = r.preview
        if resource.id not in texts:
            try:
                texts[resource.id] = (await client.get(resource.path)).text
            except httpx.HTTPError:
                texts[resource.id] = resource.preview
    others = [t for rid, t in texts.items() if rid != resource.id]
    suggestion = await pricing.suggest(texts[resource.id], others)
    resource.uniqueness_score = suggestion["uniqueness_score"]
    old_price = resource.price
    if apply:
        resource.price = suggestion["suggested_price"]
        await redis_client.delete(f"gw:resource:{resource.path}")  # cache invalidation for the gateway
    await session.commit()
    return {"resource_id": resource.id, "title": resource.title, "old_price": old_price,
            "applied": apply, **suggestion}
