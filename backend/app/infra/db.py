"""Async SQLAlchemy engine + session. One engine per process."""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=False,
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Transactional scope. Commits on success, rolls back on raise, always closes."""
    async with SessionLocal() as s:
        try:
            yield s
            await s.commit()
        except Exception:
            await s.rollback()
            raise
