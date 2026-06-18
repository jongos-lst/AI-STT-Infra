"""OpenAI Whisper adapter — downloads audio from GCS, sends to API."""
from __future__ import annotations

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.errors import ProviderError
from app.providers.base import STTProvider, TranscriptResult


class OpenAIWhisper(STTProvider):
    name = "openai-whisper"

    def __init__(self) -> None:
        if not settings.openai_api_key:
            raise ProviderError("OPENAI_API_KEY is not set")
        # Lazy import keeps the SDK out of unrelated test paths.
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, max=8),
        retry=retry_if_exception_type(Exception),
    )
    async def transcribe(self, audio_uri: str, *, language: str | None = None) -> TranscriptResult:
        from app.infra.gcs import open_for_read  # lazy import to avoid cycle
        try:
            async with open_for_read(audio_uri) as stream:
                resp = await self._client.audio.transcriptions.create(
                    model="whisper-1",
                    file=("audio", stream, "audio/mpeg"),
                    language=language,
                    response_format="verbose_json",
                )
        except Exception as e:  # noqa: BLE001
            raise ProviderError(f"whisper failure: {e}") from e
        return TranscriptResult(
            text=resp.text,
            language=getattr(resp, "language", language),
            duration_seconds=getattr(resp, "duration", None),
            provider=self.name,
        )
