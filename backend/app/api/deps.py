"""FastAPI dependencies — session, repositories, rate limit."""
from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal, current_principal
from app.core.config import settings
from app.infra.db import SessionLocal
from app.infra.redis_client import rate_limit
from app.infra.repository import AuditRepository, OutboxRepository, TaskRepository


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as s:
        try:
            yield s
            await s.commit()
        except Exception:
            await s.rollback()
            raise


async def get_task_repo(s: AsyncSession = Depends(get_session)) -> TaskRepository:
    return TaskRepository(s)


async def get_outbox_repo(s: AsyncSession = Depends(get_session)) -> OutboxRepository:
    return OutboxRepository(s)


async def get_audit_repo(s: AsyncSession = Depends(get_session)) -> AuditRepository:
    return AuditRepository(s)


async def enforce_rate_limit(p: Principal = Depends(current_principal)) -> Principal:
    ok = await rate_limit(f"rl:{p.tenant_id}", limit=settings.rate_limit_per_minute, window_seconds=60)
    if not ok:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="rate limit exceeded")
    return p
