from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.db import engine
from app.redis_client import redis_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Code before `yield` runs once at startup.
    yield
    # Code after `yield` runs once at shutdown: close connections cleanly.
    await engine.dispose()
    await redis_client.aclose()


app = FastAPI(
    title="Agent License Gateway — Platform API",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    """Reports whether this service can reach the things it depends on."""
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

    healthy = all(value == "ok" for value in checks.values())
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={"status": "ok" if healthy else "degraded", "checks": checks},
    )
