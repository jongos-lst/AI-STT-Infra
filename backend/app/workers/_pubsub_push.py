"""Shared helpers for Pub/Sub push handlers.

Pub/Sub push delivers an HTTP POST with a base64-encoded message body and
an `Authorization: Bearer <OIDC id_token>` header signed by the subscription's
configured invoker SA. We:

  1. Verify the OIDC token against Google's public keys (unless the dev
     emulator is in use — it doesn't sign).
  2. Decode the payload + attributes.
  3. Hand off to the worker handler, which restores trace context.

In production Cloud Run also gates ingress via `run.invoker` IAM, so this is
defense in depth — but the in-code check means a misconfigured IAM grant
doesn't open an unauthenticated entry point.
"""
from __future__ import annotations

import base64
import json
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import HTTPException, Request, status
from pydantic import BaseModel

from app.core.config import settings


class PubSubMessage(BaseModel):
    message_id: str
    publish_time: str | None = None
    data: dict[str, Any]
    attributes: dict[str, str]
    delivery_attempt: int


def _expected_audience(req: Request) -> str:
    """Audience Pub/Sub used when signing the push token.

    Pub/Sub uses the push endpoint URL as the audience (we don't override it
    in the subscription config). Cloud Run preserves the original
    scheme+host+path on the proxied request, so we can derive it from `req.url`.
    `PUBSUB_PUSH_AUDIENCE` env overrides for cases where a custom domain or LB
    rewrites the host header.
    """
    if settings.pubsub_push_audience:
        return settings.pubsub_push_audience
    return f"{req.url.scheme}://{req.url.netloc}{req.url.path}"


def _verify_oidc(req: Request) -> None:
    """Verify the `Authorization: Bearer` token Pub/Sub attaches to push.

    Skipped when the Pub/Sub emulator is configured (local dev only).
    """
    if settings.pubsub_emulator_host:
        return

    auth = req.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing pub/sub OIDC token",
        )

    from google.auth.transport import requests as g_requests
    from google.oauth2 import id_token

    try:
        id_token.verify_oauth2_token(
            auth.split(" ", 1)[1],
            g_requests.Request(),
            audience=_expected_audience(req),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid pub/sub OIDC token",
        ) from exc


async def parse_push(req: Request, *, verify: bool = True) -> PubSubMessage:
    """Authenticate (when verify=True) and parse a Pub/Sub push.

    Unit tests pass `verify=False` to bypass OIDC; production paths leave the
    default. Emulator dev runs auto-skip OIDC even with verify=True because
    the emulator does not sign push tokens.
    """
    if verify:
        _verify_oidc(req)

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
