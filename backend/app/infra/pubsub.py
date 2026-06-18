"""Pub/Sub publisher. Workers receive via HTTP push (FastAPI route), so no
subscriber client is needed in this codebase."""
from __future__ import annotations

import json
from functools import lru_cache

from google.cloud import pubsub_v1

from app.core.config import settings


@lru_cache(maxsize=1)
def _publisher() -> pubsub_v1.PublisherClient:
    return pubsub_v1.PublisherClient()


def topic_path(topic: str) -> str:
    return _publisher().topic_path(settings.gcp_project_id, topic)


def publish(topic: str, payload: dict, *, attributes: dict[str, str] | None = None) -> str:
    """Synchronous publish. Returns message ID. Tiny payloads, so blocking is fine."""
    data = json.dumps(payload).encode("utf-8")
    future = _publisher().publish(topic_path(topic), data, **(attributes or {}))
    return future.result(timeout=10)
