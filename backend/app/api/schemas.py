"""Request/response schemas. Pydantic v2."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.core.config import settings

AUDIO_MIME_TYPES = {"audio/mpeg", "audio/mp4", "audio/wav", "audio/webm", "audio/ogg", "audio/flac"}


class CreateTaskRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str
    audio_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    audio_bytes: int = Field(gt=0, le=settings.max_audio_bytes)

    @field_validator("content_type")
    @classmethod
    def _check_mime(cls, v: str) -> str:
        if v not in AUDIO_MIME_TYPES:
            raise ValueError(f"unsupported content_type {v}")
        return v


class CreateTaskResponse(BaseModel):
    task_id: UUID
    upload_url: str
    upload_method: Literal["PUT", "POST"] = "PUT"
    upload_headers: dict[str, str]
    expires_in_seconds: int


class CompleteUploadRequest(BaseModel):
    """Client tells us the upload finished; we move the task to QUEUED."""


class TaskResponse(BaseModel):
    task_id: UUID
    status: str
    error: str | None = None
    transcript: str | None = None
    summary: str | None = None
    metadata: dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime


class HealthResponse(BaseModel):
    status: Literal["ok"]
    env: str
    version: str
