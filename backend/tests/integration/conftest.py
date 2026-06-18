"""Integration fixtures: real Postgres + Redis from docker-compose (or CI).

These tests are slow and require services; mark them with @pytest.mark.integration
so the unit-only path stays fast.
"""
from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Make sure tests use the compose-network DB URL when run locally.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_stt",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("APP_ENV", "dev")
os.environ.setdefault("AUTH_DISABLED", "true")

# Skip the whole file if Postgres isn't reachable.
import asyncpg


async def _can_connect() -> bool:
    try:
        conn = await asyncpg.connect(
            host="localhost", port=5432, user="postgres", password="postgres", database="ai_stt",
        )
        await conn.close()
        return True
    except Exception:
        return False


@pytest_asyncio.fixture(scope="session", loop_scope="session", autouse=True)
async def _require_services() -> AsyncIterator[None]:
    if not await _can_connect():
        pytest.skip("Postgres not reachable on localhost:5432 — run `docker compose up postgres redis pubsub-emulator gcs`")
    yield
    # Dispose engine cleanly at the end of the session so async connections
    # don't try to close themselves on a torn-down loop.
    from app.infra.db import engine
    await engine.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def db() -> AsyncIterator[AsyncSession]:
    """Fresh session per test; truncates all app tables before yielding."""
    from app.infra.db import SessionLocal

    async with SessionLocal() as s:
        await s.execute(text("TRUNCATE TABLE tasks, transcripts, summaries, outbox, audit_log RESTART IDENTITY CASCADE"))
        await s.commit()
        yield s


@pytest.fixture
def tenant() -> str:
    return "tenant-int-test"
