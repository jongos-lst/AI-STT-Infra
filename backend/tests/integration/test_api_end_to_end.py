"""Black-box test: hit the API gateway running in docker-compose at localhost:8080.

Skips if the gateway isn't up. Verifies the same path the user's browser walks:
create task → upload audio → complete → poll for DONE.
"""
from __future__ import annotations

import os
import time
import uuid

import httpx
import pytest

BASE = os.environ.get("API_BASE_URL", "http://localhost:8080")

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def client():
    try:
        r = httpx.get(f"{BASE}/healthz", timeout=2.0)
        r.raise_for_status()
    except Exception as e:
        pytest.skip(f"API not reachable at {BASE}: {e}")
    with httpx.Client(base_url=BASE, timeout=10.0) as c:
        yield c


def _hex64(seed: str) -> str:
    # produce a deterministic-but-unique 64-hex string per test invocation
    return (seed + uuid.uuid4().hex)[:64].ljust(64, "0")


def test_full_pipeline_reaches_done(client: httpx.Client) -> None:
    # 1. create task
    create = client.post(
        "/v1/tasks",
        json={
            "filename": "int.wav",
            "content_type": "audio/wav",
            "audio_sha256": _hex64("a"),
            "audio_bytes": 44,
        },
    )
    assert create.status_code == 201, create.text
    body = create.json()
    task_id = body["task_id"]

    # 2. upload (44-byte silent WAV)
    silence = bytes.fromhex(
        "52494646240000005741564566" "6d7420100000000100010044ac"
        "00008858010002001000646174" "6100000000"
    )
    up = httpx.request(body["upload_method"], body["upload_url"], content=silence,
                        headers=body["upload_headers"], timeout=10.0)
    assert up.status_code in (200, 201), up.text

    # 3. complete
    complete = client.post(f"/v1/tasks/{task_id}/complete", json={})
    assert complete.status_code == 200, complete.text
    assert complete.json()["status"] in {"QUEUED", "STT_RUNNING", "STT_DONE", "LLM_RUNNING", "DONE"}

    # 4. poll
    deadline = time.time() + 30
    last = None
    while time.time() < deadline:
        last = client.get(f"/v1/tasks/{task_id}").json()
        if last["status"] in {"DONE", "FAILED"}:
            break
        time.sleep(1)

    assert last is not None
    assert last["status"] == "DONE", last
    assert last["transcript"]
    assert last["summary"]


def test_unknown_task_returns_404(client: httpx.Client) -> None:
    r = client.get(f"/v1/tasks/{uuid.uuid4()}")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_rejects_unsupported_content_type(client: httpx.Client) -> None:
    r = client.post(
        "/v1/tasks",
        json={
            "filename": "x.txt",
            "content_type": "text/plain",
            "audio_sha256": _hex64("z"),
            "audio_bytes": 10,
        },
    )
    assert r.status_code == 422
