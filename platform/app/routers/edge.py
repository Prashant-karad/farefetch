"""Single-host deployment: forward the gateway's public paths to the gateway process.

In production you would put a load balancer in front (blog/api paths -> gateway, everything else -> platform).
On a single hosted service the platform plays that role, so agents, judges and Postman use one public address.
Only enabled with EDGE_PROXY_GATEWAY=true; locally the gateway keeps its own port (8000).
"""

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import Response

from app.config import settings

router = APIRouter(include_in_schema=False)
_client = httpx.AsyncClient(timeout=15.0)
FORWARD_REQUEST = ("authorization", "x-access-pass", "user-agent", "accept")
FORWARD_RESPONSE = ("content-type", "cache-control", "retry-after", "www-authenticate",
                    "x-fairfetch-grant", "x-fairfetch-license")


async def _forward(request: Request, path: str) -> Response:
    headers = {k: v for k, v in request.headers.items() if k.lower() in FORWARD_REQUEST}
    upstream = await _client.get(f"{settings.gateway_url}{path}", headers=headers, params=request.query_params)
    return Response(content=upstream.content, status_code=upstream.status_code,
                    headers={k: v for k, v in upstream.headers.items() if k.lower() in FORWARD_RESPONSE})


@router.get("/blog/{slug}")
async def blog(slug: str, request: Request):
    return await _forward(request, f"/blog/{slug}")


@router.get("/api/{name}")
async def api(name: str, request: Request):
    return await _forward(request, f"/api/{name}")


@router.get("/p/{site}/{page}")
async def site_page(site: str, page: str, request: Request):
    return await _forward(request, f"/p/{site}/{page}")


@router.get("/.well-known/fairfetch.json")
async def terms(request: Request):
    return await _forward(request, "/.well-known/fairfetch.json")
