from contextlib import asynccontextmanager

import httpx
from fastapi import BackgroundTasks, FastAPI, Header, Request
from fastapi.responses import JSONResponse, Response

from app import platform_client as pc
from app.config import settings
from app.passes import PassError, verify_pass

origin = httpx.AsyncClient(base_url=settings.origin_url, timeout=10.0)
PUBLIC_PLATFORM = settings.public_platform_url or settings.platform_url


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await origin.aclose()
    await pc.http.aclose()
    await pc.redis_client.aclose()


app = FastAPI(title="Fairfetch Gateway", version="1.0.0", lifespan=lifespan)


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
            "kind": resource.get("kind"),
            "price": {"amount": resource["price"], "unit": "usd_0.0001", "display": format_usd(resource["price"])},
            "license": resource["license"],
            "preview": {"excerpt": resource["preview"], "word_count": resource["word_count"]},
            "purchase": {
                "method": "POST",
                "url": f"{PUBLIC_PLATFORM}/v1/purchases",
                "body": {"resource_id": resource["resource_id"]},
                "headers": ["Authorization: Bearer <api key>", "Idempotency-Key: <unique per purchase>"],
                "authenticated": agent is not None,
            },
        },
    )


async def forward_to_origin(path: str) -> Response:
    """Reverse proxy: fetch the real content from the publisher's server."""
    upstream = await origin.get(path)
    return Response(content=upstream.content, status_code=upstream.status_code,
                    media_type=upstream.headers.get("content-type"))


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/.well-known/fairfetch.json")
async def terms():
    """Machine-readable price list, like robots.txt for paid content: agents can plan a budget before knocking."""
    try:
        resp = await pc.http.get("/v1/catalog", params={"limit": 50})
        resp.raise_for_status()
    except httpx.HTTPError:
        return error(503, "platform_unavailable", "Price list unavailable. Try again shortly.", {"Retry-After": "5"})
    return {
        "protocol": "fairfetch/1",
        "how_to_pay": {"status_code": 402, "purchase_url": f"{PUBLIC_PLATFORM}/v1/purchases",
                       "pass_header": "X-Access-Pass", "pass_format": "JWT (ES256)"},
        "currency": "USD", "unit": "usd_0.0001",
        "resources": [{"path": r["path"], "title": r["title"], "kind": r["kind"], "publisher": r["publisher"],
                       "price": r["price"], "price_display": format_usd(r["price"]), "license": r["license_id"]}
                      for r in resp.json()],
    }


async def protect(path: str, request: Request, background: BackgroundTasks,
                  authorization: str | None, x_access_pass: str | None):
    user_agent = request.headers.get("user-agent")

    def log(result: str, agent_id: str | None = None, resource_id: str | None = None) -> None:
        background.add_task(pc.log_access, path=path, result=result,
                            agent_id=agent_id, resource_id=resource_id, user_agent=user_agent)

    # 1. Is anything for sale here?
    try:
        resource = await pc.get_resource(path)
    except httpx.HTTPError:
        return error(503, "platform_unavailable", "Pricing service unavailable. Try again shortly.", {"Retry-After": "5"})
    if resource is None:
        log("not_found")
        return error(404, "resource_not_found", f"Nothing for sale at {path}")
    resource_id = resource["resource_id"]

    # 2. Who is asking? (No key is allowed: unknown bots still get the price list.)
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
            return error(401, "missing_api_key", "Send the pass together with the API key of the agent that bought it",
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

        # 4. Valid pass: fetch the real content from the publisher.
        try:
            response = await forward_to_origin(path)
        except httpx.HTTPError:
            return error(502, "origin_unreachable", "The publisher's site did not respond")
        response.headers["X-Fairfetch-Grant"] = claims["jti"]
        response.headers["X-Fairfetch-License"] = claims["lic"]
        response.headers["Cache-Control"] = "private, no-store"
        log("granted", agent_id, resource_id)
        return response

    # 5. No pass: here is the price list.
    log("payment_required", agent_id, resource_id)
    return payment_required(resource, agent, "payment_required", "Buy an access pass to read this resource.")


@app.get("/blog/{slug}")
async def protected_article(slug: str, request: Request, background: BackgroundTasks,
                            authorization: str | None = Header(default=None),
                            x_access_pass: str | None = Header(default=None)):
    return await protect(f"/blog/{slug}", request, background, authorization, x_access_pass)


@app.get("/api/{name}")
async def protected_api(name: str, request: Request, background: BackgroundTasks,
                        authorization: str | None = Header(default=None),
                        x_access_pass: str | None = Header(default=None)):
    return await protect(f"/api/{name}", request, background, authorization, x_access_pass)
