"""Mock LLM — deterministic single-sentence summary."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from app.providers.base import LLMProvider, SummaryResult


class MockLLM(LLMProvider):
    name = "mock"

    async def summarize(self, transcript: str, *, max_tokens: int = 512) -> SummaryResult:
        await asyncio.sleep(0.05)
        text = f"Mock summary of {len(transcript)}-char transcript: hello-world topic discussed briefly."
        return SummaryResult(
            text=text,
            provider=self.name,
            model="mock-1",
            prompt_tokens=len(transcript) // 4,
            completion_tokens=len(text) // 4,
        )

    async def summarize_stream(self, transcript: str, *, max_tokens: int = 512) -> AsyncIterator[str]:
        result = await self.summarize(transcript, max_tokens=max_tokens)
        for chunk in result.text.split(" "):
            await asyncio.sleep(0.01)
            yield chunk + " "
