"""Shared bounded retry policy for authenticated worker deliveries."""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from app.core.config import settings
from app.domain.task import TaskStatus
from app.infra.db import session_scope
from app.infra.repository import OutboxRepository, TaskRepository
from app.workers._pubsub_push import PubSubMessage


async def record_failure(
    task_id: UUID, *, stage: Literal["stt", "llm"], message: PubSubMessage, error: Exception,
) -> Literal["failed", "skipped"] | None:
    """Return None to nack/retry, otherwise return an ACK outcome.

    At exhaustion, FAILED and one DLQ event commit atomically. ACK that delivery
    so the broker doesn't also dead-letter it. Broker DLQ remains the fallback
    for transport failures or an unavailable DB. Publication is at-least-once,
    as with all outbox events; consumers must deduplicate by task_id/stage.
    """
    async with session_scope() as session:
        status = await TaskRepository(session).record_stage_failure(
            task_id, stage=stage, error=str(error), max_failures=settings.worker_max_failures,
        )
        if status is None:
            return "skipped"
        if status == TaskStatus.FAILED:
            await OutboxRepository(session).enqueue(
                task_id=task_id,
                topic=settings.pubsub_topic_dlq,
                payload=dict(message.data),
                attributes={**message.attributes, "failed_stage": stage},
            )
            return "failed"
    return None
