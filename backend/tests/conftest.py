"""Shared fixtures. Defaults to mock providers; no network calls in unit tests."""
from __future__ import annotations

import os

os.environ.setdefault("APP_ENV", "dev")
os.environ.setdefault("AUTH_DISABLED", "true")
os.environ.setdefault("STT_PROVIDER", "mock")
os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", "")

import pytest


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
