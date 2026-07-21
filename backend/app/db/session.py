"""Async database engine, session factory, and lifecycle helpers."""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.logging import get_logger
from app.db.base import Base

log = get_logger("db")

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a scoped session that always closes."""
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Create tables for the current metadata.

    For the vertical slice we use create_all; Alembic migrations take over
    from Phase 2 when the schema starts evolving across releases.
    """
    # Import models so they register on Base.metadata before create_all.
    from app import models  # noqa: F401  (side-effect import)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    log.info("Database schema ensured")


async def dispose_db() -> None:
    await engine.dispose()
