from contextlib import asynccontextmanager

import httpx
from fastapi import BackgroundTasks, FastAPI, Header, Request
from fastapi.responses import JSONResponse, Response

from app import platform_client as pc
from app.config import settings
from app.passes import PassError, verify_pass

origin = httpx.AsyncClient(base_url=settings.origin_url, timeout=10.0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await origin.aclose()
    await pc.http.aclose()
    await pc.redis_client.aclose()


app = FastAPI(title="Fairfetch Gateway", version="0.3.0", lifespan=lifespan)


def error(status: int, code: str, message: str, headers: dict | None = None) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}}, headers=headers)


def bearer_token(authorization: str | None) -> str | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return authorization.removeprefix("Bearer ").strip() or None


def format_usd(units: int) -> str:
    return f"${units // 10_000}.{units % 10_000:04d}"


def payment_required(resource: dict, agent: dict | None, code: str, message: str) -> JSONResponse:
    """The 402 'price list' an agent needs to decide whether to buy."""
    return JSONResponse(
        status_code=402,
        content={
            "error": {"code": code, "message": message},
            "resource_id": resource["resource_id"],
            "title": resource["title"],
            "price": {"amount": resource["price"], "unit": "usd_0.0001", "display": format_usd(resource["price"])},
            "license": resource["license"],
            "preview": {"excerpt": resource["preview"], "word_count": resource["word_count"]},
            "purchase": {
                "method": "POST",
                "url": f"{settings.platform_url}/v1/purchases",
                "body": {"resource_id": resource["resource_id"]},
                "authenticated": agent is not None,
            },
        },
    )


async def forward_to_origin(path: str) -> Response:
    """Reverse proxy: fetch the real content from the publisher's server."""
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

    def log(result: str, agent_id: str | None = None, resource_id: str | None = None) -> None:
        background.add_task(pc.log_access, path=path, result=result,
                            agent_id=agent_id, resource_id=resource_id, user_agent=user_agent)

    # 1. Is anything for sale here? (If the platform is down and nothing is cached: 503, not 500.)
    try:
        resource = await pc.get_resource(path)
    except httpx.HTTPError:
        return error(503, "platform_unavailable", "Pricing service unavailable. Try again shortly.", {"Retry-After": "5"})
    if resource is None:
        log("not_found")
        return error(404, "resource_not_found", f"Nothing for sale at {path}")
    resource_id = resource["resource_id"]

    # 2. Who is asking?
    raw_key = bearer_token(authorization)
    try:
        agent = await pc.verify_agent(raw_key) if raw_key else None
    except httpx.HTTPError:
        return error(503, "platform_unavailable", "Identity service unavailable. Try again shortly.", {"Retry-After": "5"})
    if raw_key and agent is None:
        log("unauthenticated", resource_id=resource_id)
        return error(401, "invalid_api_key", "API key is not valid", {"WWW-Authenticate": "Bearer"})
    agent_id = agent["agent_id"] if agent else None

    # 3. A pass was presented: verify it.
    if x_access_pass:
        if agent is None:
            log("unauthenticated", resource_id=resource_id)
            return error(401, "missing_api_key",
                         "Send the pass together with the API key of the agent that bought it",
                         {"WWW-Authenticate": "Bearer"})
        try:
            claims = verify_pass(x_access_pass, agent_id=agent_id, path=path)
            if await pc.is_revoked(claims["jti"]):
                raise PassError("pass_revoked", "This pass has been revoked.")
        except PassError as exc:
            if exc.code == "pass_expired":
                log("invalid_pass", agent_id, resource_id)
                return payment_required(resource, agent, "pass_expired", exc.message)
            forbidden = exc.code in {"pass_not_yours", "pass_wrong_resource", "pass_revoked"}
            log("forbidden" if forbidden else "invalid_pass", agent_id, resource_id)
            return error(403 if forbidden else 401, exc.code, exc.message)

        # 4. Valid pass: fetch the real article from the publisher.
        try:
            response = await forward_to_origin(path)
        except httpx.HTTPError:
            return error(502, "origin_unreachable", "The publisher's site did not respond")
        response.headers["X-Fairfetch-Grant"] = claims["jti"]
        response.headers["X-Fairfetch-License"] = claims["lic"]
        response.headers["Cache-Control"] = "private, no-store"  # paid content: no shared caching
        log("granted", agent_id, resource_id)
        return response

    # 5. No pass: here is the price list.
    log("payment_required", agent_id, resource_id)
    return payment_required(resource, agent, "payment_required", "Buy an access pass to read this resource.")