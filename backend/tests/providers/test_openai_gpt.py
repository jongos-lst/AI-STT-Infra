from __future__ import annotations

import httpx
import pytest
import respx

from app.core.errors import ProviderError
from app.providers.llm.openai_gpt import OpenAIChat

CHAT_URL = "https://api.openai.com/v1/chat/completions"


def _completion(text: str, prompt_tokens: int = 50, completion_tokens: int = 30) -> dict:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 0,
        "model": "gpt-4o-mini",
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
    with respx.mock(assert_all_called=True) as router:
        router.post(CHAT_URL).mock(
            return_value=httpx.Response(200, json=_completion("a clean summary"))
        )
        result = await OpenAIChat().summarize("here is the transcript")

    assert result.text == "a clean summary"
    assert result.provider == "openai-gpt"
    assert result.model == "gpt-4o-mini"
    assert result.prompt_tokens == 50
    assert result.completion_tokens == 30


@pytest.mark.asyncio
async def test_4xx_is_retried_then_mapped_to_provider_error():
    with respx.mock() as router:
        router.post(CHAT_URL).mock(
            return_value=httpx.Response(400, json={"error": {"message": "bad"}})
        )
        with pytest.raises(ProviderError):
            await OpenAIChat().summarize("x")
        # tenacity retries up to 3 attempts; OpenAI SDK may add its own retries.
        assert router.calls.call_count >= 3


@pytest.mark.asyncio
async def test_streaming_yields_chunks():
    # OpenAI streaming uses Server-Sent Events: each line is `data: {json}\n\n`,
    # terminated by `data: [DONE]\n\n`.
    sse = (
        b'data: {"choices":[{"delta":{"content":"foo "}}]}\n\n'
        b'data: {"choices":[{"delta":{"content":"bar"}}]}\n\n'
        b"data: [DONE]\n\n"
    )
    with respx.mock() as router:
        router.post(CHAT_URL).mock(
            return_value=httpx.Response(
                200,
                content=sse,
                headers={"content-type": "text/event-stream"},
            )
        )
        chunks = [c async for c in OpenAIChat().summarize_stream("x")]

    assert "".join(chunks).strip() == "foo bar"
