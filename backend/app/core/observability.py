"""OpenTelemetry setup. Trace context survives across Pub/Sub via message attributes."""
from __future__ import annotations

from collections.abc import Mapping

from opentelemetry import metrics, propagate, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from app.core.config import settings

_initialized = False


def init_telemetry(service_name: str | None = None) -> None:
    """Idempotent. Safe to call from main() and from worker entrypoints.

    Wires up both tracing and metrics. Exporters depend on env:
      - prod/staging → Cloud Trace + Cloud Monitoring (if libs installed)
      - dev → console exporters
    """
    global _initialized
    if _initialized:
        return
    resource = Resource.create({SERVICE_NAME: service_name or settings.otel_service_name})
    in_cloud = settings.is_prod or settings.app_env == "staging"

    tp = TracerProvider(resource=resource)
    if in_cloud:
        try:
            from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
            tp.add_span_processor(
                BatchSpanProcessor(CloudTraceSpanExporter(project_id=settings.gcp_project_id))
            )
        except ImportError:
            pass
    else:
        tp.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(tp)

    metric_exporter = None
    if in_cloud:
        try:
            from opentelemetry.exporter.cloud_monitoring import CloudMonitoringMetricsExporter
            metric_exporter = CloudMonitoringMetricsExporter(project_id=settings.gcp_project_id)
        except ImportError:
            pass
    else:
        metric_exporter = ConsoleMetricExporter()

    if metric_exporter is not None:
        reader = PeriodicExportingMetricReader(metric_exporter, export_interval_millis=60_000)
        metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[reader]))

    _initialized = True


def tracer(name: str = "app") -> trace.Tracer:
    return trace.get_tracer(name)


def inject_trace_context(attributes: dict[str, str]) -> dict[str, str]:
    """Stamp current trace context into Pub/Sub message attributes."""
    propagate.inject(attributes)
    return attributes


def extract_trace_context(attributes: Mapping[str, str]) -> object:
    """Restore trace context from Pub/Sub message attributes."""
    return propagate.extract(attributes)
