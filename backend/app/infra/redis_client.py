"""Redis: result cache, idempotency keys, rate-limit counters."""
from __future__ import annotations

import json

from redis.asyncio import Redis

from app.core.config import settings

_client: Redis | None = None


def redis() -> Redis:
    global _client
    if _client is None:
        _client = Redis.from_url(settings.redis_url, decode_responses=True)
    return _client


async def cache_set(key: str, value: dict, ttl: int = 60) -> None:
    await redis().set(key, json.dumps(value), ex=ttl)


async def cache_get(key: str) -> dict | None:
    raw = await redis().get(key)
    return json.loads(raw) if raw else None


async def rate_limit(key: str, *, limit: int, window_seconds: int) -> bool:
    """Token-bucket-ish: count requests in a window, return True if allowed."""
    count = await redis().incr(key)
    if count == 1:
        await redis().expire(key, window_seconds)
    return count <= limit
