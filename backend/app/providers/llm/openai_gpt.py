"""OpenAI chat completion adapter, defaults to gpt-4o-mini."""
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

_MODEL = "gpt-4o-mini"


class OpenAIChat(LLMProvider):
    name = "openai-gpt"

    def __init__(self) -> None:
        if not settings.openai_api_key:
            raise ProviderError("OPENAI_API_KEY is not set")
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    @retry(reraise=True, stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, max=8))
    async def summarize(self, transcript: str, *, max_tokens: int = 512) -> SummaryResult:
        try:
            resp = await self._client.chat.completions.create(
                model=_MODEL,
                messages=[
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": transcript},
                ],
                max_tokens=max_tokens,
                temperature=0.2,
            )
        except Exception as e:  # noqa: BLE001
            raise ProviderError(f"gpt failure: {e}") from e
        usage = resp.usage
        return SummaryResult(
            text=resp.choices[0].message.content or "",
            provider=self.name,
            model=_MODEL,
            prompt_tokens=getattr(usage, "prompt_tokens", None),
            completion_tokens=getattr(usage, "completion_tokens", None),
        )

    async def summarize_stream(self, transcript: str, *, max_tokens: int = 512) -> AsyncIterator[str]:
        stream = await self._client.chat.completions.create(
            model=_MODEL,
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
