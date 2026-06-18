from __future__ import annotations

import time

import pytest
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader

from app.core import metrics as app_metrics
from app.core.metrics import (
    record_provider_error,
    record_transition,
    time_block,
)


@pytest.fixture(autouse=True)
def _in_memory_reader(monkeypatch: pytest.MonkeyPatch):
    reader = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    metrics.set_meter_provider(provider)

    # Re-bind the module-level handles to instruments created by THIS provider —
    # otherwise they keep pointing at the global default and our reader sees nothing.
    meter = provider.get_meter("ai-stt")
    monkeypatch.setattr(app_metrics, "_meter", meter)
    monkeypatch.setattr(app_metrics, "task_duration_seconds", meter.create_histogram("task.duration", unit="s"))
    monkeypatch.setattr(app_metrics, "provider_latency_seconds", meter.create_histogram("provider.latency", unit="s"))
    monkeypatch.setattr(app_metrics, "state_transitions_total", meter.create_counter("task.state_transitions"))
    monkeypatch.setattr(app_metrics, "outbox_lag_seconds", meter.create_histogram("outbox.lag", unit="s"))
    monkeypatch.setattr(app_metrics, "provider_errors_total", meter.create_counter("provider.errors"))

    yield reader


def _metric_by_name(reader: InMemoryMetricReader, name: str):
    data = reader.get_metrics_data()
    for rm in data.resource_metrics:
        for sm in rm.scope_metrics:
            for m in sm.metrics:
                if m.name == name:
                    return m
    return None


def test_time_block_records_histogram(_in_memory_reader: InMemoryMetricReader):
    with time_block(app_metrics.provider_latency_seconds, {"provider": "mock", "kind": "stt"}):
        time.sleep(0.01)

    m = _metric_by_name(_in_memory_reader, "provider.latency")
    assert m is not None
    points = list(m.data.data_points)
    assert len(points) == 1
    assert points[0].count == 1
    assert points[0].sum > 0
    assert points[0].attributes["provider"] == "mock"


def test_record_transition(_in_memory_reader: InMemoryMetricReader):
    record_transition("QUEUED", "STT_RUNNING")
    record_transition("STT_RUNNING", "STT_DONE")

    m = _metric_by_name(_in_memory_reader, "task.state_transitions")
    assert m is not None
    points = list(m.data.data_points)
    assert sum(p.value for p in points) == 2


def test_record_provider_error(_in_memory_reader: InMemoryMetricReader):
    record_provider_error("openai-whisper", "stt")

    m = _metric_by_name(_in_memory_reader, "provider.errors")
    assert m is not None
    point = next(iter(m.data.data_points))
    assert point.value == 1
    assert point.attributes["provider"] == "openai-whisper"
