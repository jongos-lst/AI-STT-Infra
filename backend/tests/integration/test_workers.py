"""Real DB + worker HTTP handlers, with only AI and blob storage replaced by fixtures."""
from __future__ import annotations

import asyncio
import base64
import json
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.errors import ProviderError
from app.domain.task import Task, TaskStatus
from app.infra.models import OutboxRow, SummaryRow, TaskRow, TranscriptRow
from app.infra.repository import OutboxRepository, TaskRepository
from app.providers.base import SummaryResult, TranscriptResult
from app.workers import llm_worker, stt_worker

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]


@pytest.fixture(params=["stt", "llm"])
def stage(request, monkeypatch):
    name = request.param
    monkeypatch.setattr(settings, "pubsub_emulator_host", "localhost:8085")
    monkeypatch.setattr(stt_worker, "put_transcript_json", lambda *_: "gs://transcripts/result.json")
    return SimpleNamespace(
        name=name,
        worker=stt_worker if name == "stt" else llm_worker,
        running=TaskStatus.STT_RUNNING if name == "stt" else TaskStatus.LLM_RUNNING,
        done=TaskStatus.STT_DONE if name == "stt" else TaskStatus.DONE,
        result_model=TranscriptRow if name == "stt" else SummaryRow,
    )


async def ready_task(db, stage):
    repo = TaskRepository(db)
    task = Task.new(tenant_id="worker-test", audio_sha256="a" * 64, audio_bytes=12, filename="x.wav")
    await repo.create(task)
    await repo.update_status(task.id, TaskStatus.QUEUED, audio_uri="gs://audio/x.wav")
    if stage.name == "llm":
        await repo.update_status(task.id, TaskStatus.STT_RUNNING)
        await repo.upsert_transcript(task.id, "stt-fixture", provider="mock", text="hello", language="en", duration_seconds=1, raw_uri=None)
        await repo.update_status(task.id, TaskStatus.STT_DONE)
    await db.commit()
    return task.id


def envelope(task_id, delivery_attempt=None):
    body = {"message": {"messageId": "same-message", "data": base64.b64encode(json.dumps({
        "task_id": str(task_id), "tenant_id": "worker-test", "audio_uri": "gs://audio/x.wav",
    }).encode()).decode(), "attributes": {"tenant_id": "worker-test"}}}
    if delivery_attempt is not None:
        body["deliveryAttempt"] = delivery_attempt
    return body


def provider(stage, monkeypatch, action):
    async def call(*_args, **_kwargs):
        await action()
        if stage.name == "stt":
            return TranscriptResult(text="transcribed", provider="fixture", language="en")
        return SummaryResult(text="summarized", provider="fixture", model="fixture")
    monkeypatch.setattr(stage.worker, f"get_{stage.name}_provider", lambda: SimpleNamespace(
        name="fixture", transcribe=call, summarize=call,
    ))


def client(stage):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=stage.worker.app, raise_app_exceptions=False), base_url="http://worker")


async def snapshot(db, task_id, stage):
    db.expire_all()
    row = await db.get(TaskRow, task_id)
    results = (await db.execute(select(stage.result_model).where(stage.result_model.task_id == task_id))).scalars().all()
    events = (await db.execute(select(OutboxRow).where(OutboxRow.task_id == task_id))).scalars().all()
    return row, results, events


@pytest.mark.parametrize("delivery_attempt", [None, 1])
async def test_transient_redelivery_recovers_and_duplicate_is_noop(db, stage, monkeypatch, delivery_attempt):
    task_id = await ready_task(db, stage)
    before = (await snapshot(db, task_id, stage))[0].updated_at
    failures = 1

    async def action():
        nonlocal failures
        if failures:
            failures -= 1
            raise ProviderError("temporary 503")

    provider(stage, monkeypatch, action)
    body = envelope(task_id, delivery_attempt)
    async with client(stage) as http:
        response = await http.post(f"/_pubsub/{stage.name}", json=body)
        assert response.status_code == 500
        row, results, events = await snapshot(db, task_id, stage)
        assert row.status == stage.running
        assert row.updated_at > before
        assert not results and not events
        response = await http.post(f"/_pubsub/{stage.name}", json=body)
        assert response.status_code == 200 and response.json() == {"status": "ok"}
        row, results, events = await snapshot(db, task_id, stage)
        assert row.status == stage.done and row.error is None
        assert len(results) == 1
        assert [event.topic for event in events] == ([settings.pubsub_topic_llm] if stage.name == "stt" else [])
        completed_at = row.updated_at
        response = await http.post(f"/_pubsub/{stage.name}", json=body)
        assert response.json() == {"status": "skipped"}
        row, results, events = await snapshot(db, task_id, stage)
        assert row.updated_at == completed_at and len(results) == 1


async def test_exhaustion_is_terminal_with_one_dead_letter_even_without_delivery_attempt(db, stage, monkeypatch):
    task_id = await ready_task(db, stage)

    async def fail():
        raise ProviderError("provider remains unavailable")

    provider(stage, monkeypatch, fail)
    async with client(stage) as http:
        for attempt in range(1, 6):
            response = await http.post(f"/_pubsub/{stage.name}", json=envelope(task_id))
            assert response.status_code == (500 if attempt < 5 else 200)
            row, _, _ = await snapshot(db, task_id, stage)
            assert row.status == (stage.running if attempt < 5 else TaskStatus.FAILED)
        assert response.json() == {"status": "failed"}
        failed_at = row.updated_at
        for _ in range(2):
            response = await http.post(f"/_pubsub/{stage.name}", json=envelope(task_id, 6))
            assert response.json() == {"status": "skipped"}
    row, results, events = await snapshot(db, task_id, stage)
    assert row.updated_at == failed_at and row.error == "provider remains unavailable"
    assert getattr(row, f"{stage.name}_failures") == 5
    assert not results
    assert len(events) == 1 and events[0].topic == settings.pubsub_topic_dlq
    assert events[0].payload["task_id"] == str(task_id)
    assert events[0].attributes["failed_stage"] == stage.name


@pytest.mark.parametrize("late_failure", [False, True])
async def test_concurrent_duplicate_cannot_overwrite_success(db, stage, monkeypatch, late_failure):
    task_id = await ready_task(db, stage)
    first_started, release_first = asyncio.Event(), asyncio.Event()
    calls = 0

    async def action():
        nonlocal calls
        calls += 1
        if calls == 1:
            first_started.set()
            await asyncio.wait_for(release_first.wait(), 5)
            if late_failure:
                raise ProviderError("late failure")

    provider(stage, monkeypatch, action)
    async with client(stage) as http:
        first = asyncio.create_task(http.post(f"/_pubsub/{stage.name}", json=envelope(task_id)))
        await asyncio.wait_for(first_started.wait(), 5)
        second = await http.post(f"/_pubsub/{stage.name}", json=envelope(task_id, 2))
        assert second.json() == {"status": "ok"}
        release_first.set()
        assert (await first).json() == {"status": "skipped"}
    row, results, events = await snapshot(db, task_id, stage)
    assert row.status == stage.done and row.error is None
    assert len(results) == 1
    assert [event.topic for event in events] == ([settings.pubsub_topic_llm] if stage.name == "stt" else [])


async def test_dead_letter_enqueue_failure_rolls_back_terminal_transition(db, stage, monkeypatch):
    task_id = await ready_task(db, stage)

    async def fail():
        raise ProviderError("persistent error")

    provider(stage, monkeypatch, fail)
    async with client(stage) as http:
        for _ in range(4):
            assert (await http.post(f"/_pubsub/{stage.name}", json=envelope(task_id))).status_code == 500
        enqueue = OutboxRepository.enqueue

        async def broken_enqueue(*_args, **_kwargs):
            raise RuntimeError("outbox unavailable")

        monkeypatch.setattr(OutboxRepository, "enqueue", broken_enqueue)
        assert (await http.post(f"/_pubsub/{stage.name}", json=envelope(task_id))).status_code == 500
        row, _, events = await snapshot(db, task_id, stage)
        assert row.status == stage.running and getattr(row, f"{stage.name}_failures") == 4
        assert not events
        monkeypatch.setattr(OutboxRepository, "enqueue", enqueue)
        assert (await http.post(f"/_pubsub/{stage.name}", json=envelope(task_id))).json() == {"status": "failed"}
    row, _, events = await snapshot(db, task_id, stage)
    assert row.status == TaskStatus.FAILED and len(events) == 1


@pytest.mark.parametrize("late_success", [False, True])
async def test_exhaustion_wins_over_late_concurrent_delivery(db, stage, monkeypatch, late_success):
    task_id = await ready_task(db, stage)
    delayed_started, release_delayed = asyncio.Event(), asyncio.Event()
    calls = 0

    async def action():
        nonlocal calls
        calls += 1
        if calls == 5:
            delayed_started.set()
            await asyncio.wait_for(release_delayed.wait(), 5)
            if late_success:
                return
        raise ProviderError("persistent error")

    provider(stage, monkeypatch, action)
    async with client(stage) as http:
        for _ in range(4):
            assert (await http.post(f"/_pubsub/{stage.name}", json=envelope(task_id))).status_code == 500
        delayed = asyncio.create_task(http.post(f"/_pubsub/{stage.name}", json=envelope(task_id)))
        await asyncio.wait_for(delayed_started.wait(), 5)
        last = await http.post(f"/_pubsub/{stage.name}", json=envelope(task_id))
        assert last.json() == {"status": "failed"}
        release_delayed.set()
        assert (await delayed).json() == {"status": "skipped"}
    row, results, events = await snapshot(db, task_id, stage)
    assert row.status == TaskStatus.FAILED and getattr(row, f"{stage.name}_failures") == 5
    assert not results and len(events) == 1 and events[0].topic == settings.pubsub_topic_dlq
