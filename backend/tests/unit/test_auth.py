from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.core.auth import _verify_jwt, current_principal
from app.core.config import settings


@pytest.fixture
def auth_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "auth_disabled", False)
    monkeypatch.setattr(settings, "jwt_audience", "ai-stt-platform")
    monkeypatch.setattr(settings, "jwt_issuer", "https://securetoken.google.com/ai-stt-dev")


@pytest.mark.asyncio
async def test_dev_bypass_when_auth_disabled(monkeypatch):
    monkeypatch.setattr(settings, "auth_disabled", True)
    principal = await current_principal(authorization=None)
    assert principal.is_dev_principal


@pytest.mark.asyncio
async def test_missing_bearer_rejected(auth_on):
    with pytest.raises(HTTPException) as exc:
        await current_principal(authorization=None)
    assert exc.value.status_code == 401

    with pytest.raises(HTTPException) as exc:
        await current_principal(authorization="Basic abc")
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_valid_token_returns_principal(auth_on):
    fake_claims = {
        "sub": "user-123",
        "email": "user@example.com",
        "aud": "ai-stt-platform",
        "iss": "https://securetoken.google.com/ai-stt-dev",
        "tenant_id": "acme-corp",
    }
    with patch(
        "google.oauth2.id_token.verify_firebase_token",
        return_value=fake_claims,
    ):
        p = await current_principal(authorization="Bearer some.jwt.token")
    assert p.user_id == "user-123"
    assert p.tenant_id == "acme-corp"
    assert p.email == "user@example.com"


def test_audience_mismatch_rejected(auth_on):
    with patch(
        "google.oauth2.id_token.verify_firebase_token",
        return_value={
            "sub": "u",
            "aud": "WRONG",
            "iss": "https://securetoken.google.com/ai-stt-dev",
        },
    ), pytest.raises(HTTPException) as exc:
        _verify_jwt("any-token")
    assert exc.value.status_code == 401
    assert "audience" in exc.value.detail.lower()


def test_invalid_token_raises_401(auth_on):
    with patch(
        "google.oauth2.id_token.verify_firebase_token",
        side_effect=ValueError("bad signature"),
    ), pytest.raises(HTTPException) as exc:
        _verify_jwt("garbage")
    assert exc.value.status_code == 401
