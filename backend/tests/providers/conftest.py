"""Provider tests don't hit the real OpenAI API.

Network is intercepted by respx. GCS is patched to return a tiny in-memory blob.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest


@pytest.fixture(autouse=True)
def _fake_openai_key(monkeypatch: pytest.MonkeyPatch) -> None:
    # The adapter raises on import if the key is empty.
    from app.core.config import settings
    monkeypatch.setattr(settings, "openai_api_key", "sk-test-not-real")


@asynccontextmanager
async def _gcs_bytes(_audio_uri: str) -> AsyncIterator[bytes]:
    yield b"\x00" * 100   # 100 silent bytes


@pytest.fixture
def patch_gcs(monkeypatch: pytest.MonkeyPatch):
    # whisper.py does a lazy `from app.infra.gcs import open_for_read`,
    # so patch the source module.
    monkeypatch.setattr("app.infra.gcs.open_for_read", _gcs_bytes)
