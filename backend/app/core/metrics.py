"""Typed OTel metric handles. One place to add a new metric.

The handles are no-ops until ``init_metrics()`` runs (in ``observability.py``).
That keeps unit tests fast and lets the worker entrypoints opt in.
"""
from __future__ import annotations

import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any

from opentelemetry import metrics

_METER_NAME = "ai-stt"

_meter = metrics.get_meter(_METER_NAME)

task_duration_seconds = _meter.create_histogram(
    name="task.duration",
    description="Time spent in each task stage",
    unit="s",
)

provider_latency_seconds = _meter.create_histogram(
    name="provider.latency",
    description="AI provider call latency",
    unit="s",
)

state_transitions_total = _meter.create_counter(
    name="task.state_transitions",
    description="Task state transitions, labelled by from/to",
)

outbox_lag_seconds = _meter.create_histogram(
    name="outbox.lag",
    description="Wall time from outbox row insert to Pub/Sub publish",
    unit="s",
)

provider_errors_total = _meter.create_counter(
    name="provider.errors",
    description="Provider call failures",
)


@contextmanager
def time_block(
    histogram: metrics.Histogram, attributes: Mapping[str, Any] | None = None
) -> Iterator[None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        histogram.record(time.perf_counter() - start, attributes=dict(attributes or {}))


def record_transition(from_state: str, to_state: str) -> None:
    state_transitions_total.add(1, attributes={"from": from_state, "to": to_state})


def record_provider_error(provider: str, kind: str) -> None:
    provider_errors_total.add(1, attributes={"provider": provider, "kind": kind})
