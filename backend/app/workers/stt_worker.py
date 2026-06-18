"""STT worker — Cloud Run service consuming Pub/Sub push for `stt.requested`.

Idempotency: every attempt produces a deterministic attempt_id from (task_id,
delivery_attempt); the transcripts table has UNIQUE on (task_id, attempt_id) and
we UPSERT, so retries are safe.
"""
from __future__ import annotations

import contextlib
from uuid import UUID

from fastapi import FastAPI, Request
from opentelemetry import trace

from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.core.metrics import (
    provider_latency_seconds,
    record_provider_error,
    task_duration_seconds,
    time_block,
)
from app.core.observability import extract_trace_context, init_telemetry, tracer
from app.domain.task import TaskStatus
from app.infra.db import session_scope
from app.infra.gcs import put_transcript_json
from app.infra.repository import OutboxRepository, TaskRepository
from app.providers.registry import get_stt_provider
from app.workers._pubsub_push import parse_push

setup_logging()
init_telemetry("ai-stt-stt-worker")
log = get_logger(__name__)

app = FastAPI(title="STT Worker")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/_pubsub/stt")
async def handle(req: Request) -> dict[str, str]:
    msg = await parse_push(req)
    ctx = extract_trace_context(msg.attributes)
    with tracer().start_as_current_span("stt.process", context=ctx, kind=trace.SpanKind.CONSUMER), \
         time_block(task_duration_seconds, {"stage": "stt"}):
        task_id = UUID(msg.data["task_id"])
        attempt_id = f"d{msg.delivery_attempt}-m{msg.message_id}"

        try:
            async with session_scope() as s:
                repo = TaskRepository(s)
                outbox = OutboxRepository(s)
                task = await repo.get_no_tenant(task_id)
                if task.status == TaskStatus.DONE or task.status == TaskStatus.FAILED:
                    log.info("stt.skip.terminal", task_id=str(task_id), status=task.status)
                    return {"status": "skipped"}

                if task.status not in (TaskStatus.QUEUED, TaskStatus.STT_RUNNING):
                    log.warning("stt.skip.wrong_state", task_id=str(task_id), status=task.status)
                    return {"status": "skipped"}

                await repo.update_status(task_id, TaskStatus.STT_RUNNING)

            # Provider call outside the DB transaction to avoid long-held connections.
            stt = get_stt_provider()
            audio_uri = msg.data["audio_uri"]
            with time_block(provider_latency_seconds, {"provider": stt.name, "kind": "stt"}):
                try:
                    result = await stt.transcribe(audio_uri, language=None)
                except Exception:
                    record_provider_error(stt.name, "stt")
                    raise
            raw_uri = put_transcript_json(str(task_id), {
                "text": result.text, "language": result.language, "duration": result.duration_seconds,
                "provider": result.provider,
            })

            async with session_scope() as s:
                repo = TaskRepository(s)
                outbox = OutboxRepository(s)
                await repo.upsert_transcript(
                    task_id,
                    attempt_id,
                    provider=result.provider,
                    text=result.text,
                    language=result.language,
                    duration_seconds=result.duration_seconds,
                    raw_uri=raw_uri,
                )
                await repo.update_status(task_id, TaskStatus.STT_DONE)
                # publish to LLM stage via outbox (sweeper handles delivery)
                await outbox.enqueue(
                    task_id=task_id,
                    topic=settings.pubsub_topic_llm,
                    payload={"task_id": str(task_id), "tenant_id": msg.data.get("tenant_id")},
                    attributes=dict(msg.attributes),
                )

            log.info("stt.done", task_id=str(task_id), provider=result.provider)
            return {"status": "ok"}

        except Exception as e:
            log.exception("stt.fail", task_id=str(task_id), error=str(e))
            async with session_scope() as s:
                repo = TaskRepository(s)
                with contextlib.suppress(Exception):
                    await repo.update_status(task_id, TaskStatus.FAILED, error=str(e))
            # Return 500 so Pub/Sub redelivers up to dead_letter_max_attempts.
            raise
