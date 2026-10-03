"""OpenRouter Whisper adapter — proxies OpenAI's Whisper through OpenRouter.

OpenRouter exposes an OpenAI-compatible /audio/transcriptions endpoint, so we
reuse the openai SDK and just swap base_url + api_key. Model defaults to
openai/whisper-large-v3 and is configurable via OPENROUTER_STT_MODEL.
"""
from __future__ import annotations

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.errors import ProviderError
from app.providers.base import STTProvider, TranscriptResult


class OpenRouterWhisper(STTProvider):
    name = "openrouter-whisper"

    def __init__(self) -> None:
        if not settings.openrouter_api_key:
            raise ProviderError("OPENROUTER_API_KEY is not set")
        from openai import AsyncOpenAI
        self._model = settings.openrouter_stt_model
        self._client = AsyncOpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            default_headers=_openrouter_headers(),
        )

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, max=8),
        retry=retry_if_exception_type(Exception),
    )
    async def transcribe(self, audio_uri: str, *, language: str | None = None) -> TranscriptResult:
        from app.infra.gcs import open_for_read
        try:
            async with open_for_read(audio_uri) as stream:
                resp = await self._client.audio.transcriptions.create(
                    model=self._model,
                    file=("audio", stream, "audio/mpeg"),
                    language=language,
                    response_format="verbose_json",
                )
        except Exception as e:
            raise ProviderError(f"openrouter whisper failure: {e}") from e
        return TranscriptResult(
            text=resp.text,
            language=getattr(resp, "language", language),
            duration_seconds=getattr(resp, "duration", None),
            provider=self.name,
        )


def _openrouter_headers() -> dict[str, str]:
    """OpenRouter uses these for attribution leaderboards — optional but tidy."""
    return {
        "HTTP-Referer": settings.openrouter_referer,
        "X-Title": settings.openrouter_title,
    }
