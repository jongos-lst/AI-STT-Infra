from __future__ import annotations

import httpx
import pytest
import respx

from app.core.config import settings
from app.core.errors import ProviderError
from app.providers.llm.openrouter_chat import OpenRouterChat

CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"


def _completion(text: str, model: str, prompt_tokens: int = 50, completion_tokens: int = 30) -> dict:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 0,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


@pytest.mark.asyncio
async def test_parses_summary_and_tokens():
    model = settings.openrouter_llm_model
    with respx.mock(assert_all_called=True) as router:
        router.post(CHAT_URL).mock(
            return_value=httpx.Response(200, json=_completion("a clean summary", model))
        )
        result = await OpenRouterChat().summarize("here is the transcript")

    assert result.text == "a clean summary"
    assert result.provider == "openrouter-chat"
    assert result.model == model
    assert result.prompt_tokens == 50
    assert result.completion_tokens == 30


@pytest.mark.asyncio
async def test_4xx_is_retried_then_mapped_to_provider_error():
    with respx.mock() as router:
        router.post(CHAT_URL).mock(
            return_value=httpx.Response(400, json={"error": {"message": "bad"}})
        )
        with pytest.raises(ProviderError):
            await OpenRouterChat().summarize("x")
        assert router.calls.call_count >= 3


@pytest.mark.asyncio
async def test_no_api_key_raises_at_construction(monkeypatch):
    from app.core.config import settings as live_settings
    monkeypatch.setattr(live_settings, "openrouter_api_key", None)
    with pytest.raises(ProviderError):
        OpenRouterChat()
