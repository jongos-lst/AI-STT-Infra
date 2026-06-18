"""Mock STT — used in dev, tests, and as a CI fallback when keys are absent."""
from __future__ import annotations

import asyncio

from app.providers.base import STTProvider, TranscriptResult


class MockSTT(STTProvider):
    name = "mock"

    async def transcribe(self, audio_uri: str, *, language: str | None = None) -> TranscriptResult:
        await asyncio.sleep(0.05)  # mimic some latency
        return TranscriptResult(
            text=f"[mock transcript for {audio_uri}] hello world this is a test transcription.",
            language=language or "en",
            duration_seconds=42.0,
            provider=self.name,
        )
