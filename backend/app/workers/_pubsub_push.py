"""Shared helpers for Pub/Sub push handlers.

Pub/Sub push delivers an HTTP POST with a base64-encoded message body. We decode
it, restore trace context from attributes, and dispatch to the handler.
"""
from __future__ import annotations

import base64
import json
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Request
from pydantic import BaseModel


class PubSubMessage(BaseModel):
    message_id: str
    publish_time: str | None = None
    data: dict[str, Any]
    attributes: dict[str, str]
    delivery_attempt: int


async def parse_push(req: Request) -> PubSubMessage:
    body = await req.json()
    msg = body["message"]
    data = json.loads(base64.b64decode(msg["data"]).decode())
    return PubSubMessage(
        message_id=msg["messageId"],
        publish_time=msg.get("publishTime"),
        data=data,
        attributes=msg.get("attributes", {}),
        delivery_attempt=int(body.get("deliveryAttempt", 1)),
    )


HandlerFn = Callable[[PubSubMessage], Awaitable[None]]
