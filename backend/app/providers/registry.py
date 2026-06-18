"""Single dispatch point — the only place that maps provider names → adapter instances.

Add a new provider by:
  1. implementing STTProvider or LLMProvider under providers/{stt,llm}/<name>.py
  2. registering it below
That's it. No other file needs to change.
"""
from __future__ import annotations

from app.core.config import settings
from app.providers.base import LLMProvider, STTProvider
from app.providers.llm.mock import MockLLM
from app.providers.llm.openai_gpt import OpenAIChat
from app.providers.stt.mock import MockSTT
from app.providers.stt.openai_whisper import OpenAIWhisper

_STT_REGISTRY: dict[str, type[STTProvider]] = {
    "mock": MockSTT,
    "openai-whisper": OpenAIWhisper,
}

_LLM_REGISTRY: dict[str, type[LLMProvider]] = {
    "mock": MockLLM,
    "openai-gpt": OpenAIChat,
}


def get_stt_provider(name: str | None = None) -> STTProvider:
    key = (name or settings.stt_provider).lower()
    try:
        return _STT_REGISTRY[key]()
    except KeyError as e:
        raise ValueError(f"unknown STT provider: {key}") from e


def get_llm_provider(name: str | None = None) -> LLMProvider:
    key = (name or settings.llm_provider).lower()
    try:
        return _LLM_REGISTRY[key]()
    except KeyError as e:
        raise ValueError(f"unknown LLM provider: {key}") from e
