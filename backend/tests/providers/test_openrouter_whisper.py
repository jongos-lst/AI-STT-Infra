from __future__ import annotations

import httpx
import pytest
import respx

from app.core.errors import ProviderError
from app.providers.stt.openrouter_whisper import OpenRouterWhisper

WHISPER_URL = "https://openrouter.ai/api/v1/audio/transcriptions"


@pytest.mark.asyncio
async def test_parses_verbose_json_response(patch_gcs):
    with respx.mock(assert_all_called=True) as router:
        router.post(WHISPER_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "text": "this is the transcript",
                    "language": "en",
                    "duration": 17.5,
                },
            )
        )
        result = await OpenRouterWhisper().transcribe("gs://bucket/audio.mp3", language="en")

    assert result.text == "this is the transcript"
    assert result.language == "en"
    assert result.duration_seconds == 17.5
    assert result.provider == "openrouter-whisper"


@pytest.mark.asyncio
async def test_5xx_is_retried_then_raises_provider_error(patch_gcs):
    with respx.mock() as router:
        router.post(WHISPER_URL).mock(
            return_value=httpx.Response(503, json={"error": {"message": "down"}})
        )
        with pytest.raises(ProviderError):
            await OpenRouterWhisper().transcribe("gs://bucket/x.mp3")
        assert router.calls.call_count >= 3


@pytest.mark.asyncio
async def test_no_api_key_raises_at_construction(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "openrouter_api_key", None)
    with pytest.raises(ProviderError):
        OpenRouterWhisper()
