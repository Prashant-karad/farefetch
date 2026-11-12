from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.db import engine
from app.redis_client import redis_client
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routers import admin, agents, catalog, dashboard, demo, edge, internal, product, purchases, topups, usage, wallet


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()
    await redis_client.aclose()


app = FastAPI(title="Fairfetch Platform API", version="1.0.0", lifespan=lifespan)
for r in (agents, internal, purchases, wallet, topups, usage, catalog, admin, dashboard, demo, product):
    app.include_router(r.router)
if settings.edge_proxy_gateway:
    app.include_router(edge.router)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


@app.get("/health")
async def health():
    checks: dict[str, str] = {}
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {type(exc).__name__}"
    try:
        await redis_client.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {type(exc).__name__}"
    healthy = all(v == "ok" for v in checks.values())
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={"status": "ok" if healthy else "degraded", "checks": checks},
    )
