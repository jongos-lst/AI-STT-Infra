"""Auth: Firebase / Google JWT verification, with a dev bypass.

In dev (docker-compose) we set `AUTH_DISABLED=true` and inject a fixed
principal. In staging/prod the `Authorization: Bearer <id_token>` header is
verified against Google's public keys via `google.oauth2.id_token`.
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Header, HTTPException, status

from app.core.config import settings


@dataclass(frozen=True)
class Principal:
    tenant_id: str
    user_id: str
    email: str | None = None

    @property
    def is_dev_principal(self) -> bool:
        return self.user_id == "dev-user"


_DEV = Principal(tenant_id="dev-tenant", user_id="dev-user", email="dev@local")


def _verify_jwt(token: str) -> Principal:
    """Verify a Firebase ID token signed by Google. Returns the Principal or 401s."""
    # Lazy import — keeps unit tests fast and `google.auth` out of the dev
    # docker layer when AUTH_DISABLED=true.
    from google.auth.transport import requests as g_requests
    from google.oauth2 import id_token

    try:
        claims = id_token.verify_firebase_token(
            token, g_requests.Request(), settings.jwt_audience
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token"
        ) from exc

    if claims.get("iss") != settings.jwt_issuer:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="issuer mismatch")
    if claims.get("aud") != settings.jwt_audience:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="audience mismatch")

    sub = claims.get("sub")
    if not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing subject")

    # Firebase custom claims preferred; fall back to the user's sub (single-
    # tenant-per-user model). Real multi-tenant Firebase setups populate
    # `tenant_id` via Identity Platform.
    tenant_id = claims.get("tenant_id") or claims.get("firebase", {}).get("tenant") or sub
    return Principal(tenant_id=tenant_id, user_id=sub, email=claims.get("email"))


async def current_principal(authorization: str | None = Header(default=None)) -> Principal:
    if settings.auth_disabled:
        return _DEV
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token"
        )
    return _verify_jwt(authorization.split(" ", 1)[1])
