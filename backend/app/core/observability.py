"""OpenTelemetry setup. Trace context survives across Pub/Sub via message attributes."""
from __future__ import annotations

from collections.abc import Mapping

from opentelemetry import propagate, trace
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from app.core.config import settings

_initialized = False


def init_telemetry(service_name: str | None = None) -> None:
    """Idempotent. Safe to call from main() and from worker entrypoints."""
    global _initialized
    if _initialized:
        return
    resource = Resource.create({SERVICE_NAME: service_name or settings.otel_service_name})
    provider = TracerProvider(resource=resource)

    if settings.is_prod or settings.app_env == "staging":
        try:
            from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
            provider.add_span_processor(BatchSpanProcessor(CloudTraceSpanExporter(project_id=settings.gcp_project_id)))
        except ImportError:
            pass
    else:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
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
