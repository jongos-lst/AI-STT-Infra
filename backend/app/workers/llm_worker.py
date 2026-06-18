"""LLM worker — consumes `llm.requested`, summarizes transcript, writes summary."""
from __future__ import annotations

from uuid import UUID

from fastapi import FastAPI, Request
from opentelemetry import trace

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
from app.infra.repository import TaskRepository
from app.providers.registry import get_llm_provider
from app.workers._pubsub_push import parse_push

setup_logging()
init_telemetry("ai-stt-llm-worker")
log = get_logger(__name__)

app = FastAPI(title="LLM Worker")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/_pubsub/llm")
async def handle(req: Request) -> dict[str, str]:
    msg = await parse_push(req)
    ctx = extract_trace_context(msg.attributes)
    with tracer().start_as_current_span("llm.process", context=ctx, kind=trace.SpanKind.CONSUMER), \
         time_block(task_duration_seconds, {"stage": "llm"}):
        task_id = UUID(msg.data["task_id"])
        attempt_id = f"d{msg.delivery_attempt}-m{msg.message_id}"

        try:
            async with session_scope() as s:
                repo = TaskRepository(s)
                task = await repo.get_no_tenant(task_id)
                if task.status in (TaskStatus.DONE, TaskStatus.FAILED):
                    return {"status": "skipped"}
                if task.status not in (TaskStatus.STT_DONE, TaskStatus.LLM_RUNNING):
                    log.warning("llm.skip.wrong_state", task_id=str(task_id), status=task.status)
                    return {"status": "skipped"}
                transcript_row = await repo.latest_transcript(task_id)
                if transcript_row is None:
                    raise RuntimeError("no transcript present for LLM stage")
                transcript_text = transcript_row.text
                await repo.update_status(task_id, TaskStatus.LLM_RUNNING)

            llm = get_llm_provider()
            with time_block(provider_latency_seconds, {"provider": llm.name, "kind": "llm"}):
                try:
                    result = await llm.summarize(transcript_text)
                except Exception:
                    record_provider_error(llm.name, "llm")
                    raise

            async with session_scope() as s:
                repo = TaskRepository(s)
                await repo.upsert_summary(
                    task_id,
                    attempt_id,
                    provider=result.provider,
                    model=result.model,
                    text=result.text,
                    prompt_tokens=result.prompt_tokens,
                    completion_tokens=result.completion_tokens,
                )
                await repo.update_status(task_id, TaskStatus.DONE)

            log.info("llm.done", task_id=str(task_id), provider=result.provider, model=result.model)
            return {"status": "ok"}

        except Exception as e:  # noqa: BLE001
            log.exception("llm.fail", task_id=str(task_id), error=str(e))
            async with session_scope() as s:
                repo = TaskRepository(s)
                try:
                    await repo.update_status(task_id, TaskStatus.FAILED, error=str(e))
                except Exception:  # noqa: BLE001
                    pass
            raise
