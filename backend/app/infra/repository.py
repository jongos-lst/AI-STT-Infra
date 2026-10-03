"""Tenant-aware repository. ALL reads/writes filter by tenant_id here, not in routes.

This is the only place that touches the ORM models. Workers and route handlers
talk to repositories, never to SessionLocal directly (except for the outbox sweeper,
which has its own narrow scope).
"""
from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.domain.task import Task, TaskStatus
from app.infra.models import (
    AuditRow,
    OutboxRow,
    SummaryRow,
    TaskRow,
    TranscriptRow,
)


def _row_to_task(r: TaskRow) -> Task:
    return Task(
        id=r.id,
        tenant_id=r.tenant_id,
        status=TaskStatus(r.status),
        audio_uri=r.audio_uri,
        audio_sha256=r.audio_sha256,
        audio_bytes=r.audio_bytes,
        error=r.error,
        metadata=r.metadata_ or {},
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


class TaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def create(self, task: Task) -> Task:
        row = TaskRow(
            id=task.id,
            tenant_id=task.tenant_id,
            status=task.status.value,
            audio_uri=task.audio_uri,
            audio_sha256=task.audio_sha256,
            audio_bytes=task.audio_bytes,
            error=task.error,
            metadata_=task.metadata,
        )
        self.s.add(row)
        await self.s.flush()
        return _row_to_task(row)

    async def get(self, task_id: UUID, *, tenant_id: str) -> Task:
        row = await self.s.get(TaskRow, task_id)
        if not row or row.tenant_id != tenant_id:
            raise NotFoundError(f"task {task_id}")
        return _row_to_task(row)

    async def get_no_tenant(self, task_id: UUID, *, for_update: bool = False) -> Task:
        """For workers: messages already authenticated by Pub/Sub OIDC."""
        row = await self._get_row(task_id, for_update=for_update)
        return _row_to_task(row)

    async def update_status(
        self,
        task_id: UUID,
        status: TaskStatus,
        *,
        audio_uri: str | None = None,
        error: str | None = None,
    ) -> Task:
        row = await self._get_row(task_id, for_update=True)
        self._move_row(row, status, error=error)
        if audio_uri is not None:
            row.audio_uri = audio_uri
        return _row_to_task(row)

    async def _get_row(self, task_id: UUID, *, for_update: bool) -> TaskRow:
        # Refresh a cached ORM identity after acquiring the lock: a different
        # delivery may have committed since this transaction first read it.
        row = await self.s.get(
            TaskRow, task_id, with_for_update=for_update, populate_existing=for_update,
        )
        if not row:
            raise NotFoundError(f"task {task_id}")
        return row

    @staticmethod
    def _move_row(row: TaskRow, status: TaskStatus, *, error: str | None = None) -> None:
        task = _row_to_task(row)
        task.move_to(status, error=error)
        row.status = task.status.value
        row.updated_at = task.updated_at
        row.error = task.error

    async def record_stage_failure(
        self, task_id: UUID, *, stage: Literal["stt", "llm"], error: str, max_failures: int,
    ) -> TaskStatus | None:
        """Count a failed execution under a row lock; ignore late deliveries.

        The caller commits this together with the terminal DLQ outbox event.
        Counts live in the DB because Pub/Sub deliveryAttempt is best-effort and
        may be absent or reset; a worker restart must not reset the budget.
        """
        row = await self._get_row(task_id, for_update=True)
        ready, running = (
            (TaskStatus.QUEUED, TaskStatus.STT_RUNNING) if stage == "stt"
            else (TaskStatus.STT_DONE, TaskStatus.LLM_RUNNING)
        )
        if TaskStatus(row.status) not in (ready, running):
            return None
        if stage == "stt":
            row.stt_failures += 1
            failures = row.stt_failures
        else:
            row.llm_failures += 1
            failures = row.llm_failures
        target = TaskStatus.FAILED if failures >= max_failures else running
        self._move_row(row, target, error=error)
        return target

    async def upsert_transcript(
        self,
        task_id: UUID,
        attempt_id: str,
        *,
        provider: str,
        text: str,
        language: str | None,
        duration_seconds: float | None,
        raw_uri: str | None,
    ) -> None:
        stmt = pg_insert(TranscriptRow).values(
            task_id=task_id,
            attempt_id=attempt_id,
            provider=provider,
            text=text,
            language=language,
            duration_seconds=duration_seconds,
            raw_uri=raw_uri,
        ).on_conflict_do_nothing(index_elements=["task_id", "attempt_id"])
        await self.s.execute(stmt)

    async def upsert_summary(
        self,
        task_id: UUID,
        attempt_id: str,
        *,
        provider: str,
        model: str,
        text: str,
        prompt_tokens: int | None,
        completion_tokens: int | None,
    ) -> None:
        stmt = pg_insert(SummaryRow).values(
            task_id=task_id,
            attempt_id=attempt_id,
            provider=provider,
            model=model,
            text=text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        ).on_conflict_do_nothing(index_elements=["task_id", "attempt_id"])
        await self.s.execute(stmt)

    async def latest_transcript(self, task_id: UUID) -> TranscriptRow | None:
        stmt = (
            select(TranscriptRow)
            .where(TranscriptRow.task_id == task_id)
            .order_by(TranscriptRow.created_at.desc())
            .limit(1)
        )
        return (await self.s.execute(stmt)).scalar_one_or_none()

    async def latest_summary(self, task_id: UUID) -> SummaryRow | None:
        stmt = (
            select(SummaryRow)
            .where(SummaryRow.task_id == task_id)
            .order_by(SummaryRow.created_at.desc())
            .limit(1)
        )
        return (await self.s.execute(stmt)).scalar_one_or_none()


class OutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def enqueue(self, *, task_id: UUID, topic: str, payload: dict[str, Any], attributes: dict[str, str]) -> None:
        self.s.add(OutboxRow(task_id=task_id, topic=topic, payload=payload, attributes=attributes))


class AuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def write(self, *, tenant_id: str, actor: str, action: str, target_type: str, target_id: str, payload: dict[str, Any]) -> None:
        self.s.add(AuditRow(
            tenant_id=tenant_id,
            actor=actor,
            action=action,
            target_type=target_type,
            target_id=target_id,
            payload=payload,
        ))
