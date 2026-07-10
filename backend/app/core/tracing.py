"""OpenTelemetry tracing helpers.

Tracing is opt-in via OTEL_TRACING_ENABLED so local tests and development do not
depend on an OpenTelemetry collector.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any


logger = logging.getLogger(__name__)

_TRACING_CONFIGURED = False
_TRACING_ENABLED = False


def configure_tracing(settings: Any) -> None:
    """Configure OpenTelemetry tracing when explicitly enabled."""
    global _TRACING_CONFIGURED, _TRACING_ENABLED

    if _TRACING_CONFIGURED:
        return
    _TRACING_CONFIGURED = True

    if not settings.otel_tracing_enabled:
        logger.info("otel_tracing_disabled")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.propagate import set_global_textmap
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
        from opentelemetry.trace.propagation.tracecontext import (
            TraceContextTextMapPropagator,
        )
    except ImportError as exc:
        raise RuntimeError(
            "OTEL_TRACING_ENABLED=true requires OpenTelemetry dependencies. "
            "Run `pip install -r backend/requirements.txt`."
        ) from exc

    resource = Resource.create(
        {
            "service.name": settings.otel_service_name,
            "service.version": settings.project_version,
            "deployment.environment": settings.environment,
        }
    )
    provider = TracerProvider(
        resource=resource,
        sampler=ParentBased(TraceIdRatioBased(settings.otel_trace_sample_ratio)),
    )
    exporter = OTLPSpanExporter(
        endpoint=settings.otel_exporter_otlp_traces_endpoint,
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    set_global_textmap(TraceContextTextMapPropagator())

    _TRACING_ENABLED = True
    logger.info(
        "otel_tracing_configured",
        extra={
            "event": "otel_tracing_configured",
            "service_name": settings.otel_service_name,
            "otlp_endpoint": settings.otel_exporter_otlp_traces_endpoint,
            "sample_ratio": settings.otel_trace_sample_ratio,
        },
    )


def is_tracing_enabled() -> bool:
    return _TRACING_ENABLED


@contextmanager
def trace_span(
    name: str,
    attributes: dict[str, str | int | float | bool | None] | None = None,
) -> Iterator[Any | None]:
    if not _TRACING_ENABLED:
        yield None
        return

    from opentelemetry import trace

    with trace.get_tracer("app").start_as_current_span(name) as span:
        add_span_attributes(span, attributes)
        yield span


@contextmanager
def start_http_server_span(request: Any, request_id: str) -> Iterator[Any | None]:
    if not _TRACING_ENABLED:
        yield None
        return

    from opentelemetry import propagate, trace
    from opentelemetry.trace import SpanKind

    parent_context = propagate.extract(dict(request.headers))
    span_name = f"{request.method} {request.url.path}"
    attributes = {
        "http.request.method": request.method,
        "url.path": request.url.path,
        "url.scheme": request.url.scheme,
        "server.address": request.url.hostname or "",
        "request.id": request_id,
    }

    with trace.get_tracer("app.http").start_as_current_span(
        span_name,
        context=parent_context,
        kind=SpanKind.SERVER,
        attributes=attributes,
    ) as span:
        yield span


def finish_http_server_span(
    span: Any | None,
    *,
    method: str,
    route: str,
    status_code: int,
    duration_ms: float,
) -> None:
    if span is None:
        return

    span.update_name(f"{method} {route}")
    add_span_attributes(
        span,
        {
            "http.route": route,
            "http.response.status_code": status_code,
            "http.server.duration_ms": duration_ms,
        },
    )
    if status_code >= 500:
        _set_span_error(span)


def record_span_exception(span: Any | None, exc: BaseException) -> None:
    if span is None:
        return

    span.record_exception(exc)
    _set_span_error(span)


def add_span_attributes(
    span: Any | None,
    attributes: dict[str, str | int | float | bool | None] | None,
) -> None:
    if span is None or not attributes:
        return

    for key, value in attributes.items():
        if value is not None:
            span.set_attribute(key, value)


def _set_span_error(span: Any) -> None:
    from opentelemetry.trace import Status, StatusCode

    span.set_status(Status(StatusCode.ERROR))
