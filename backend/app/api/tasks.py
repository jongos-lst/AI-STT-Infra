"""Task API: create, complete upload, get."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import enforce_rate_limit, get_session
from app.api.schemas import (
    CompleteUploadRequest,
    CreateTaskRequest,
    CreateTaskResponse,
    TaskResponse,
)
from app.core.auth import Principal
from app.core.config import settings
from app.core.observability import inject_trace_context, tracer
from app.domain.task import Task, TaskStatus
from app.infra.gcs import signed_upload_url
from app.infra.redis_client import cache_get, cache_set
from app.infra.repository import AuditRepository, OutboxRepository, TaskRepository

router = APIRouter(prefix="/v1/tasks", tags=["tasks"])


def _audio_object_path(task: Task) -> str:
    filename = task.metadata.get("filename", "audio")
    return f"{task.tenant_id}/{task.id}/{filename}"


@router.post("", response_model=CreateTaskResponse, status_code=201)
async def create_task(
    body: CreateTaskRequest,
    p: Principal = Depends(enforce_rate_limit),
    s: AsyncSession = Depends(get_session),
) -> CreateTaskResponse:
    with tracer().start_as_current_span("create_task"):
        repo = TaskRepository(s)
        audit = AuditRepository(s)

        task = Task.new(
            tenant_id=p.tenant_id,
            audio_sha256=body.audio_sha256,
            audio_bytes=body.audio_bytes,
            filename=body.filename,
        )
        await repo.create(task)
        await audit.write(
            tenant_id=p.tenant_id,
            actor=p.user_id,
            action="task.create",
            target_type="task",
            target_id=str(task.id),
            payload={"filename": body.filename, "bytes": body.audio_bytes},
        )

        target = signed_upload_url(
            settings.gcs_bucket_audio,
            _audio_object_path(task),
            content_type=body.content_type,
            content_length=body.audio_bytes,
        )
        return CreateTaskResponse(
            task_id=task.id,
            upload_url=target.url,
            upload_method=target.method,  # type: ignore[arg-type]
            upload_headers=target.headers,
            expires_in_seconds=settings.signed_url_ttl_seconds,
        )


@router.post("/{task_id}/complete", response_model=TaskResponse)
async def complete_upload(
    task_id: UUID,
    _body: CompleteUploadRequest,
    p: Principal = Depends(enforce_rate_limit),
    s: AsyncSession = Depends(get_session),
) -> TaskResponse:
    with tracer().start_as_current_span("complete_upload"):
        repo = TaskRepository(s)
        outbox = OutboxRepository(s)
        task = await repo.get(task_id, tenant_id=p.tenant_id)

        audio_uri = f"gs://{settings.gcs_bucket_audio}/{_audio_object_path(task)}"
        task.audio_uri = audio_uri
        task.move_to(TaskStatus.QUEUED)
        await repo.update_status(task.id, task.status, audio_uri=audio_uri)

        # Outbox pattern: same transaction as the status update.
        attrs = inject_trace_context({"tenant_id": p.tenant_id, "task_id": str(task.id)})
        await outbox.enqueue(
            task_id=task.id,
            topic=settings.pubsub_topic_stt,
            payload={"task_id": str(task.id), "tenant_id": p.tenant_id, "audio_uri": audio_uri},
            attributes=attrs,
        )

        return _to_response(task)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: UUID,
    p: Principal = Depends(enforce_rate_limit),
    s: AsyncSession = Depends(get_session),
) -> TaskResponse:
    cache_key = f"task:{p.tenant_id}:{task_id}"
    cached = await cache_get(cache_key)
    if cached:
        return TaskResponse.model_validate(cached)

    repo = TaskRepository(s)
    task = await repo.get(task_id, tenant_id=p.tenant_id)
    transcript = await repo.latest_transcript(task_id)
    summary = await repo.latest_summary(task_id)
    resp = TaskResponse(
        task_id=task.id,
        status=task.status.value,
        error=task.error,
        transcript=transcript.text if transcript else None,
        summary=summary.text if summary else None,
        metadata=task.metadata,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )
    if task.status.value in {"DONE", "FAILED"}:
        await cache_set(cache_key, resp.model_dump(mode="json"), ttl=60)
    return resp


def _to_response(t: Task) -> TaskResponse:
    return TaskResponse(
        task_id=t.id,
        status=t.status.value,
        error=t.error,
        metadata=t.metadata,
        created_at=t.created_at,
        updated_at=t.updated_at,
    )
