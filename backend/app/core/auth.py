"""Auth: Firebase / Google JWT verification, with a dev bypass."""
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
    """Verify a Firebase/Google ID token. Stub for now — real impl uses google.oauth2.id_token."""
    # Real implementation (added in Phase 6 wiring):
    #   from google.oauth2 import id_token
    #   from google.auth.transport import requests as g_requests
    #   claims = id_token.verify_firebase_token(token, g_requests.Request(), settings.jwt_audience)
    #   return Principal(tenant_id=claims["tenant_id"], user_id=claims["sub"], email=claims.get("email"))
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="real JWT verification wired in deploy")


async def current_principal(authorization: str | None = Header(default=None)) -> Principal:
    if settings.auth_disabled:
        return _DEV
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")
    return _verify_jwt(authorization.split(" ", 1)[1])
