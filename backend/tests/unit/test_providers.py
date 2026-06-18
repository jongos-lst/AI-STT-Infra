from __future__ import annotations

import pytest

from app.providers.registry import get_llm_provider, get_stt_provider


@pytest.mark.asyncio
async def test_mock_stt_returns_deterministic_shape() -> None:
    stt = get_stt_provider("mock")
    r = await stt.transcribe("gs://bucket/path/audio.mp3", language="en")
    assert r.provider == "mock"
    assert r.language == "en"
    assert "audio.mp3" in r.text
    assert r.duration_seconds == 42.0


@pytest.mark.asyncio
async def test_mock_llm_summary_includes_transcript_size() -> None:
    llm = get_llm_provider("mock")
    transcript = "hello " * 100
    r = await llm.summarize(transcript)
    assert r.provider == "mock"
    assert r.model == "mock-1"
    assert str(len(transcript)) in r.text
    assert r.prompt_tokens is not None and r.prompt_tokens > 0


@pytest.mark.asyncio
async def test_mock_llm_streams_chunks() -> None:
    llm = get_llm_provider("mock")
    pieces = [chunk async for chunk in llm.summarize_stream("x" * 50)]
    assert len(pieces) > 1
    assert "".join(pieces).strip() != ""


def test_unknown_provider_raises() -> None:
    with pytest.raises(ValueError):
        get_stt_provider("nope")
    with pytest.raises(ValueError):
        get_llm_provider("nope")
