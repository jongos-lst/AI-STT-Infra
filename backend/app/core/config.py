"""Typed settings, loaded once at import time."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["dev", "staging", "prod"] = "dev"
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_stt"
    redis_url: str = "redis://localhost:6379/0"

    gcp_project_id: str = "ai-stt-dev"
    pubsub_emulator_host: str | None = None
    storage_emulator_host: str | None = None
    # Browser-reachable address of the storage host. In dev with fake-gcs-server,
    # services talk to gcs:4443 but the browser must hit localhost:4443.
    gcs_public_url: str | None = None

    pubsub_topic_stt: str = "stt.requested"
    pubsub_topic_llm: str = "llm.requested"
    pubsub_topic_dlq: str = "tasks.dlq"
    pubsub_sub_stt: str = "stt-worker"
    pubsub_sub_llm: str = "llm-worker"

    gcs_bucket_audio: str = "ai-stt-dev-audio"
    gcs_bucket_transcripts: str = "ai-stt-dev-transcripts"

    stt_provider: str = "mock"
    llm_provider: str = "mock"

    openai_api_key: str | None = None
    vertex_location: str = "us-central1"

    jwt_audience: str = "ai-stt-platform"
    jwt_issuer: str = "https://securetoken.google.com/ai-stt-dev"
    # Defaults fail safe: production cannot accidentally run with auth off.
    # docker-compose explicitly sets AUTH_DISABLED=true for local dev.
    auth_disabled: bool = False
    cors_origins: list[str] = Field(
        default_factory=list,
        description="Allowed browser origins for CORS. Per-env; e.g. ['https://stg.ai-stt.example.com'].",
    )
    # Comma-separated audiences accepted on Pub/Sub push tokens. In Cloud Run
    # push the audience is the worker URL. Each worker overrides this via env.
    pubsub_push_audience: str | None = None

    otel_service_name: str = "ai-stt-api"
    otel_exporter_otlp_endpoint: str | None = None

    max_audio_bytes: int = 500 * 1024 * 1024
    signed_url_ttl_seconds: int = 900

    rate_limit_per_minute: int = Field(default=60, description="Per-tenant API calls / minute")

    @property
    def is_prod(self) -> bool:
        return self.app_env == "prod"

    @property
    def is_dev(self) -> bool:
        return self.app_env == "dev"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
