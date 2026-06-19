from __future__ import annotations

import base64
import json
from unittest.mock import patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.core.config import settings
from app.workers._pubsub_push import _expected_audience, parse_push


def _envelope(payload: dict) -> dict:
    return {
        "message": {
            "messageId": "m1",
            "publishTime": "2026-06-19T00:00:00Z",
            "data": base64.b64encode(json.dumps(payload).encode()).decode(),
            "attributes": {"tenant_id": "t-1"},
        },
        "deliveryAttempt": 1,
    }


@pytest.fixture
def push_app():
    """Tiny test app that mirrors a worker's push endpoint."""
    app = FastAPI()

    @app.post("/_pubsub/stt")
    async def handle(req: Request) -> dict[str, str]:
        msg = await parse_push(req)
        return {"task_id": msg.data["task_id"]}

    return app


def test_emulator_mode_skips_verify(monkeypatch, push_app):
    """Local dev: emulator host set → OIDC verification is bypassed."""
    monkeypatch.setattr(settings, "pubsub_emulator_host", "localhost:8085")
    client = TestClient(push_app)
    r = client.post("/_pubsub/stt", json=_envelope({"task_id": "abc"}))
    assert r.status_code == 200
    assert r.json() == {"task_id": "abc"}


def test_missing_bearer_rejected(monkeypatch, push_app):
    """Prod path: no Authorization header → 401."""
    monkeypatch.setattr(settings, "pubsub_emulator_host", None)
    monkeypatch.setattr(settings, "pubsub_push_audience", None)
    client = TestClient(push_app)
    r = client.post("/_pubsub/stt", json=_envelope({"task_id": "abc"}))
    assert r.status_code == 401
    assert "OIDC" in r.json()["detail"]


def test_audience_override_used(monkeypatch):
    """If PUBSUB_PUSH_AUDIENCE is set, it wins over the request URL."""
    monkeypatch.setattr(settings, "pubsub_push_audience", "https://override.example.com/x")

    class FakeURL:
        scheme = "http"
        netloc = "host:port"
        path = "/wrong"

    class FakeReq:
        url = FakeURL()

    assert _expected_audience(FakeReq()) == "https://override.example.com/x"


def test_audience_derived_from_request(monkeypatch):
    monkeypatch.setattr(settings, "pubsub_push_audience", None)

    class FakeURL:
        scheme = "https"
        netloc = "ai-stt-stt-worker-abc-asia-east1.a.run.app"
        path = "/_pubsub/stt"

    class FakeReq:
        url = FakeURL()

    assert _expected_audience(FakeReq()) == "https://ai-stt-stt-worker-abc-asia-east1.a.run.app/_pubsub/stt"


def test_bad_token_rejected(monkeypatch, push_app):
    monkeypatch.setattr(settings, "pubsub_emulator_host", None)
    monkeypatch.setattr(settings, "pubsub_push_audience", "https://x")

    client = TestClient(push_app)
    with patch(
        "google.oauth2.id_token.verify_oauth2_token",
        side_effect=ValueError("bad sig"),
    ):
        r = client.post(
            "/_pubsub/stt",
            json=_envelope({"task_id": "abc"}),
            headers={"Authorization": "Bearer fake"},
        )
    assert r.status_code == 401


def test_valid_token_accepted(monkeypatch, push_app):
    monkeypatch.setattr(settings, "pubsub_emulator_host", None)
    monkeypatch.setattr(settings, "pubsub_push_audience", "https://x")

    client = TestClient(push_app)
    with patch(
        "google.oauth2.id_token.verify_oauth2_token",
        return_value={"sub": "pubsub-invoker@proj.iam.gserviceaccount.com"},
    ):
        r = client.post(
            "/_pubsub/stt",
            json=_envelope({"task_id": "abc"}),
            headers={"Authorization": "Bearer valid"},
        )
    assert r.status_code == 200
    assert r.json() == {"task_id": "abc"}


def test_verify_false_bypasses(monkeypatch):
    """parse_push(req, verify=False) is the unit-test escape hatch."""
    monkeypatch.setattr(settings, "pubsub_emulator_host", None)
    monkeypatch.setattr(settings, "pubsub_push_audience", "https://x")

    app = FastAPI()

    @app.post("/no-verify")
    async def handle(req: Request):
        msg = await parse_push(req, verify=False)
        return {"task_id": msg.data["task_id"]}

    client = TestClient(app)
    r = client.post("/no-verify", json=_envelope({"task_id": "abc"}))
    assert r.status_code == 200
