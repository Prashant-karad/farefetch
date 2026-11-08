from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import AccessLog, License, Resource
from app.services.auth import authenticate_api_key, require_internal

# Every route in this router requires the internal token.
router = APIRouter(prefix="/internal", tags=["internal"], dependencies=[Depends(require_internal)])


@router.get("/resources/lookup")
async def lookup_resource(path: str = Query(...), session: AsyncSession = Depends(get_session)):
    row = (
        await session.execute(
            select(Resource, License)
            .join(License, Resource.license_id == License.id)
            .where(Resource.path == path)
        )
    ).first()
    if row is None:
        raise HTTPException(404, detail={"code": "resource_not_found", "message": f"No resource at {path}"})
    resource, lic = row
    return {
        "resource_id": resource.id,
        "publisher_id": resource.publisher_id,
        "title": resource.title,
        "kind": resource.kind,
        "price": resource.price,
        "preview": resource.preview,
        "word_count": resource.word_count,
        "license": {
            "id": lic.id,
            "type": lic.type,
            "max_quote_words": lic.max_quote_words,
            "attribution_required": lic.attribution_required,
            "ttl_hours": lic.ttl_hours,
        },
    }


class VerifyKeyRequest(BaseModel):
    api_key: str


@router.post("/agents/verify")
async def verify_agent(body: VerifyKeyRequest, session: AsyncSession = Depends(get_session)):
    agent = await authenticate_api_key(session, body.api_key)
    if agent is None:
        raise HTTPException(401, detail={"code": "invalid_api_key", "message": "API key is not valid"})
    return {"agent_id": agent.id, "owner_id": agent.owner_id, "name": agent.name}


class AccessLogIn(BaseModel):
    path: str
    result: Literal["payment_required", "granted", "unauthenticated", "forbidden", "invalid_pass", "not_found"]
    agent_id: str | None = None
    resource_id: str | None = None
    user_agent: str | None = None


@router.post("/access-logs", status_code=202)
async def create_access_log(body: AccessLogIn, session: AsyncSession = Depends(get_session)):
    session.add(AccessLog(**body.model_dump()))
    await session.commit()
    return {"status": "accepted"}