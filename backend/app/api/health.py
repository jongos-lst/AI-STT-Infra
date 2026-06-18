"""Liveness + readiness. Cloud Run hits /healthz, LB hits /readyz."""
from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app import __version__
from app.api.schemas import HealthResponse
from app.core.config import settings
from app.infra.db import engine
from app.infra.redis_client import redis

router = APIRouter(tags=["health"])


@router.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    return HealthResponse(status="ok", env=settings.app_env, version=__version__)


@router.get("/readyz")
async def readyz() -> dict[str, str]:
    checks: dict[str, str] = {}
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as e:  # noqa: BLE001
        checks["postgres"] = f"fail: {e}"
    try:
        await redis().ping()
        checks["redis"] = "ok"
    except Exception as e:  # noqa: BLE001
        checks["redis"] = f"fail: {e}"
    return checks
