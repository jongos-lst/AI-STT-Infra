from __future__ import annotations

import pytest

from app.core.errors import NotFoundError
from app.domain.task import Task, TaskStatus
from app.infra.repository import OutboxRepository, TaskRepository

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]


async def test_create_and_get(db, tenant):
    repo = TaskRepository(db)
    t = Task.new(tenant_id=tenant, audio_sha256="a" * 64, audio_bytes=1024, filename="x.mp3")
    await repo.create(t)
    await db.commit()

    got = await repo.get(t.id, tenant_id=tenant)
    assert got.id == t.id
    assert got.status == TaskStatus.PENDING_UPLOAD
    assert got.metadata["filename"] == "x.mp3"


async def test_get_enforces_tenant_isolation(db):
    repo = TaskRepository(db)
    a = Task.new(tenant_id="tenant-a", audio_sha256="a" * 64, audio_bytes=1, filename="x")
    await repo.create(a)
    await db.commit()

    # Same row, wrong tenant → NotFound. This is THE rule that keeps tenants safe.
    with pytest.raises(NotFoundError):
        await repo.get(a.id, tenant_id="tenant-b")


async def test_state_transition_upsert(db, tenant):
    repo = TaskRepository(db)
    t = Task.new(tenant_id=tenant, audio_sha256="a" * 64, audio_bytes=1, filename="x")
    await repo.create(t)
    await db.commit()

    # PENDING_UPLOAD → QUEUED → STT_RUNNING → STT_DONE
    await repo.update_status(t.id, TaskStatus.QUEUED, audio_uri="gs://bucket/x")
    await repo.update_status(t.id, TaskStatus.STT_RUNNING)
    await repo.update_status(t.id, TaskStatus.STT_DONE)
    await db.commit()

    got = await repo.get(t.id, tenant_id=tenant)
    assert got.status == TaskStatus.STT_DONE
    assert got.audio_uri == "gs://bucket/x"


async def test_transcript_upsert_is_idempotent(db, tenant):
    repo = TaskRepository(db)
    t = Task.new(tenant_id=tenant, audio_sha256="a" * 64, audio_bytes=1, filename="x")
    await repo.create(t)
    await db.commit()

    for _ in range(3):
        await repo.upsert_transcript(
            t.id, "attempt-1",
            provider="mock", text="hi", language="en", duration_seconds=1.0, raw_uri=None,
        )
    await db.commit()

    latest = await repo.latest_transcript(t.id)
    assert latest is not None
    assert latest.text == "hi"
    assert latest.attempt_id == "attempt-1"


async def test_outbox_enqueue_visible_to_sweeper(db, tenant):
    task_repo = TaskRepository(db)
    outbox = OutboxRepository(db)
    t = Task.new(tenant_id=tenant, audio_sha256="a" * 64, audio_bytes=1, filename="x")
    await task_repo.create(t)
    await outbox.enqueue(
        task_id=t.id,
        topic="stt.requested",
        payload={"task_id": str(t.id)},
        attributes={"tenant_id": tenant, "traceparent": "deadbeef"},
    )
    await db.commit()

    # The sweeper SELECTs by published_at IS NULL — make sure the row qualifies.
    from sqlalchemy import select

    from app.infra.models import OutboxRow
    rows = (await db.execute(select(OutboxRow).where(OutboxRow.published_at.is_(None)))).scalars().all()
    assert any(r.task_id == t.id and r.topic == "stt.requested" for r in rows)
