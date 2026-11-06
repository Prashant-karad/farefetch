from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# One engine for the whole app. It manages a POOL of database connections.
engine = create_async_engine(
    settings.database_url,
    pool_size=5,         # keep up to 5 connections open and reuse them
    max_overflow=10,     # allow 10 extra temporary connections under load
    pool_pre_ping=True,  # check a connection is alive before using it
)

# Factory that creates a new session (a unit of work) when asked.
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """Parent class for all our table models (Part 2)."""


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: gives each request its own session, then closes it."""
    async with SessionLocal() as session:
        yield session
