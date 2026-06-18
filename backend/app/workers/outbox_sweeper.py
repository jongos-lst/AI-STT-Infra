"""Outbox sweeper — runs as a Cloud Run Job on a 1-min schedule (or a long-lived
container in dev). Reads unpublished outbox rows, publishes to Pub/Sub, marks
published.
"""
from __future__ import annotations

import asyncio
import datetime as _dt

from sqlalchemy import select, update

from app.core.logging import get_logger, setup_logging
from app.core.observability import init_telemetry
from app.infra.db import session_scope
from app.infra.models import OutboxRow
from app.infra.pubsub import publish

setup_logging()
init_telemetry("ai-stt-outbox-sweeper")
log = get_logger(__name__)


async def sweep_once(batch_size: int = 200) -> int:
    sent = 0
    async with session_scope() as s:
        rows = (
            await s.execute(
                select(OutboxRow)
                .where(OutboxRow.published_at.is_(None))
                .order_by(OutboxRow.created_at)
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            )
        ).scalars().all()

        for r in rows:
            try:
                msg_id = publish(r.topic, r.payload, attributes=r.attributes)
                log.info("outbox.published", outbox_id=r.id, topic=r.topic, message_id=msg_id)
                await s.execute(
                    update(OutboxRow).where(OutboxRow.id == r.id).values(published_at=_dt.datetime.now(tz=_dt.timezone.utc))
                )
                sent += 1
            except Exception as e:  # noqa: BLE001
                log.exception("outbox.publish.fail", outbox_id=r.id, topic=r.topic, error=str(e))
                # leave published_at NULL so next sweep retries
    return sent


async def run_forever(interval_seconds: float = 1.0) -> None:
    log.info("outbox.sweeper.start", interval=interval_seconds)
    while True:
        try:
            n = await sweep_once()
            if n == 0:
                await asyncio.sleep(interval_seconds)
        except Exception as e:  # noqa: BLE001
            log.exception("outbox.sweeper.error", error=str(e))
            await asyncio.sleep(interval_seconds)


if __name__ == "__main__":
    asyncio.run(run_forever())
