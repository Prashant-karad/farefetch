from contextlib import asynccontextmanager

import httpx
from fastapi import BackgroundTasks, FastAPI, Header, Request
from fastapi.responses import JSONResponse, Response

from app import platform_client as pc
from app.config import settings

# Client for the publisher's real website (the "origin").
origin = httpx.AsyncClient(base_url=settings.origin_url, timeout=10.0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await origin.aclose()
    await pc.http.aclose()
    await pc.redis_client.aclose()


app = FastAPI(title="Fairfetch Gateway", version="0.2.0", lifespan=lifespan)


def error(status: int, code: str, message: str, headers: dict | None = None) -> JSONResponse:
    """One consistent error shape, so agents can react to `code` programmatically."""
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}}, headers=headers)


def bearer_token(authorization: str | None) -> str | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return authorization.removeprefix("Bearer ").strip() or None


def format_usd(units: int) -> str:
    """Display only. 1 unit = $0.0001. Integer math, no floats."""
    return f"${units // 10_000}.{units % 10_000:04d}"


async def forward_to_origin(path: str) -> Response:
    """Reverse proxy: fetch the real content from the publisher's server. Used from M3."""
    upstream = await origin.get(path)
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type"),
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/blog/{slug}")
async def protected_article(
    slug: str,
    request: Request,
    background: BackgroundTasks,
    authorization: str | None = Header(default=None),
    x_access_pass: str | None = Header(default=None),
):
    path = f"/blog/{slug}"
    user_agent = request.headers.get("user-agent")

    # 1. Is anything for sale at this path?
    resource = await pc.get_resource(path)
    if resource is None:
        background.add_task(pc.log_access, path=path, result="not_found", user_agent=user_agent)
        return error(404, "resource_not_found", f"Nothing for sale at {path}")
    resource_id = resource["resource_id"]

    # 2. Who is asking? No key is allowed: unknown bots still get the price list.
    raw_key = bearer_token(authorization)
    agent = await pc.verify_agent(raw_key) if raw_key else None
    if raw_key and agent is None:
        background.add_task(pc.log_access, path=path, result="unauthenticated",
                            resource_id=resource_id, user_agent=user_agent)
        return error(401, "invalid_api_key", "API key is not valid", {"WWW-Authenticate": "Bearer"})
    agent_id = agent["agent_id"] if agent else None

    # 3. Do they have a pass? (M3 replaces this with real signature verification.)
    if x_access_pass:
        background.add_task(pc.log_access, path=path, result="invalid_pass",
                            agent_id=agent_id, resource_id=resource_id, user_agent=user_agent)
        return error(401, "invalid_pass", "Access passes are verified from M3 onwards")

    # 4. No pass: tell them the price, the license, and how to buy.
    background.add_task(pc.log_access, path=path, result="payment_required",
                        agent_id=agent_id, resource_id=resource_id, user_agent=user_agent)
    return JSONResponse(
        status_code=402,
        content={
            "error": {"code": "payment_required", "message": "Buy an access pass to read this resource."},
            "resource_id": resource_id,
            "title": resource["title"],
            "price": {"amount": resource["price"], "unit": "usd_0.0001", "display": format_usd(resource["price"])},
            "license": resource["license"],
            "preview": {"excerpt": resource["preview"], "word_count": resource["word_count"]},
            "purchase": {
                "method": "POST",
                "url": f"{settings.platform_url}/v1/purchases",
                "body": {"resource_id": resource_id},
                "authenticated": agent is not None,
            },
        },
    )