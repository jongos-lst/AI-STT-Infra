from __future__ import annotations

from app.domain.task import Task, TaskStatus


def test_new_task_starts_pending_upload() -> None:
    t = Task.new(tenant_id="t1", audio_sha256="a" * 64, audio_bytes=1024, filename="x.mp3")
    assert t.status == TaskStatus.PENDING_UPLOAD
    assert t.metadata["filename"] == "x.mp3"
    assert t.tenant_id == "t1"


def test_move_updates_status_and_timestamp() -> None:
    t = Task.new(tenant_id="t1", audio_sha256="a" * 64, audio_bytes=1024, filename="x.mp3")
    before = t.updated_at
    t.move_to(TaskStatus.QUEUED)
    assert t.status == TaskStatus.QUEUED
    assert t.updated_at >= before


def test_move_records_error_on_failure() -> None:
    t = Task.new(tenant_id="t1", audio_sha256="a" * 64, audio_bytes=1024, filename="x.mp3")
    t.move_to(TaskStatus.QUEUED)
    t.move_to(TaskStatus.FAILED, error="boom")
    assert t.error == "boom"
