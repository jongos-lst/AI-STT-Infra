"""OpenRouter chat completion adapter.

OpenRouter exposes an OpenAI-compatible /chat/completions endpoint, so we reuse
the openai SDK and just swap base_url + api_key. Model defaults to
openai/gpt-5-nano and is configurable via OPENROUTER_LLM_MODEL.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.errors import ProviderError
from app.providers.base import LLMProvider, SummaryResult

_SYSTEM = (
    "You are a meeting and audio note assistant. Summarize the transcript into 3-5 "
    "bullet points covering the topics discussed, decisions made, and any action items. "
    "Be concise. Do not invent details."
)


class OpenRouterChat(LLMProvider):
    name = "openrouter-chat"

    def __init__(self) -> None:
        if not settings.openrouter_api_key:
            raise ProviderError("OPENROUTER_API_KEY is not set")
        from openai import AsyncOpenAI
        self._model = settings.openrouter_llm_model
        self._client = AsyncOpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            default_headers={
                "HTTP-Referer": settings.openrouter_referer,
                "X-Title": settings.openrouter_title,
            },
        )

    @retry(reraise=True, stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, max=8))
    async def summarize(self, transcript: str, *, max_tokens: int = 512) -> SummaryResult:
        try:
            resp = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": transcript},
                ],
                max_tokens=max_tokens,
                temperature=0.2,
            )
        except Exception as e:
            raise ProviderError(f"openrouter chat failure: {e}") from e
        usage = resp.usage
        return SummaryResult(
            text=resp.choices[0].message.content or "",
            provider=self.name,
            model=self._model,
            prompt_tokens=getattr(usage, "prompt_tokens", None),
            completion_tokens=getattr(usage, "completion_tokens", None),
        )

    async def summarize_stream(self, transcript: str, *, max_tokens: int = 512) -> AsyncIterator[str]:
        stream = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": transcript},
            ],
            max_tokens=max_tokens,
            temperature=0.2,
            stream=True,
        )
        async for event in stream:
            piece = event.choices[0].delta.content if event.choices else None
            if piece:
                yield piece
