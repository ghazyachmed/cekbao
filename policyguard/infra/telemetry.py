"""OpenTelemetry wiring. Spans carry ids and states only, never instruction text or account numbers."""
from __future__ import annotations

import os

from opentelemetry import propagate, trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

_configured = False


def configure(service_name: str) -> None:
    """Console export when PG_OTEL_CONSOLE=1; otherwise spans are created but not exported (no collector here)."""
    global _configured
    if _configured:
        return
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    if os.environ.get("PG_OTEL_CONSOLE") == "1":
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)
    _configured = True


def tracer():
    return trace.get_tracer("policyguard")


def current_traceparent() -> str | None:
    carrier: dict[str, str] = {}
    propagate.inject(carrier)
    return carrier.get("traceparent")


def context_from_traceparent(traceparent: str | None):
    return propagate.extract({"traceparent": traceparent} if traceparent else {})
