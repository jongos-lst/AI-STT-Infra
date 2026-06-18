"""Provider ports. Adapters live in providers/{stt,llm}/<vendor>.py.

NEVER import a vendor SDK outside an adapter — that is the contract that keeps
provider swaps cheap and the test suite hermetic.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass


@dataclass(frozen=True)
class TranscriptResult:
    text: str
    language: str | None = None
    duration_seconds: float | None = None
    provider: str = ""
    raw_uri: str | None = None


@dataclass(frozen=True)
class SummaryResult:
    text: str
    provider: str = ""
    model: str = ""
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class STTProvider(ABC):
    name: str = "unset"

    @abstractmethod
    async def transcribe(self, audio_uri: str, *, language: str | None = None) -> TranscriptResult: ...


class LLMProvider(ABC):
    name: str = "unset"

    @abstractmethod
    async def summarize(self, transcript: str, *, max_tokens: int = 512) -> SummaryResult: ...

    async def summarize_stream(self, transcript: str, *, max_tokens: int = 512) -> AsyncIterator[str]:
        """Optional streaming. Defaults to single chunk."""
        result = await self.summarize(transcript, max_tokens=max_tokens)
        yield result.text
