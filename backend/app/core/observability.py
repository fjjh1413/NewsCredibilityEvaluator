import logging
import time
import uuid

from fastapi import FastAPI, Request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.responses import Response

from app.core.logging import request_id_context
from app.core.tracing import (
    finish_http_server_span,
    record_span_exception,
    start_http_server_span,
)


REQUEST_ID_HEADER = "X-Request-ID"
logger = logging.getLogger(__name__)

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests.",
    ("method", "route", "status_class"),
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ("method", "route", "status_class"),
    buckets=(0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
DB_QUERY_DURATION_SECONDS = Histogram(
    "db_query_duration_seconds",
    "Database query duration in seconds.",
    ("db_system", "operation", "status"),
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)
DETECTION_TASKS_TOTAL = Counter(
    "detection_tasks_total",
    "Detection task lifecycle events.",
    ("status",),
)
DETECTION_TASK_DURATION_SECONDS = Histogram(
    "detection_task_duration_seconds",
    "Detection task execution duration in seconds.",
    ("status",),
    buckets=(1, 2.5, 5, 10, 30, 60, 120, 300, 600),
)
CACHE_EVENTS_TOTAL = Counter(
    "cache_events_total",
    "Cache events by namespace and outcome.",
    ("namespace", "outcome"),
)

_INSTRUMENTED_ENGINE_IDS: set[int] = set()


def add_observability_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def observability_middleware(request: Request, call_next):
        request_id = _request_id_from_header(request)
        token = request_id_context.set(request_id)
        started_at = time.perf_counter()
        status_code = 500
        route = "unmatched"
        elapsed = 0.0
        try:
            with start_http_server_span(request, request_id) as span:
                try:
                    response = await call_next(request)
                    status_code = response.status_code
                    return response
                except Exception as exc:
                    record_span_exception(span, exc)
                    raise
                finally:
                    route = _route_template(request)
                    elapsed = time.perf_counter() - started_at
                    finish_http_server_span(
                        span,
                        method=request.method,
                        route=route,
                        status_code=status_code,
                        duration_ms=round(elapsed * 1000, 2),
                    )
        finally:
            status_class = f"{status_code // 100}xx"
            HTTP_REQUESTS_TOTAL.labels(
                method=request.method,
                route=route,
                status_class=status_class,
            ).inc()
            HTTP_REQUEST_DURATION_SECONDS.labels(
                method=request.method,
                route=route,
                status_class=status_class,
            ).observe(elapsed)

            if "response" in locals():
                response.headers[REQUEST_ID_HEADER] = request_id
            logger.info(
                "http_request_completed",
                extra={
                    "event": "http_request_completed",
                    "method": request.method,
                    "route": route,
                    "status_code": status_code,
                    "status_class": status_class,
                    "duration_ms": round(elapsed * 1000, 2),
                },
            )
            request_id_context.reset(token)


def instrument_sqlalchemy_engine(engine) -> None:
    engine_id = id(engine)
    if engine_id in _INSTRUMENTED_ENGINE_IDS:
        return

    from sqlalchemy import event

    event.listen(engine, "before_cursor_execute", _before_cursor_execute)
    event.listen(engine, "after_cursor_execute", _after_cursor_execute)
    event.listen(engine, "handle_error", _handle_cursor_error)
    _INSTRUMENTED_ENGINE_IDS.add(engine_id)


def metrics_response() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def record_detection_task_event(status: str) -> None:
    DETECTION_TASKS_TOTAL.labels(status=status).inc()


def observe_detection_task_duration(status: str, duration_seconds: float) -> None:
    DETECTION_TASK_DURATION_SECONDS.labels(status=status).observe(duration_seconds)


def record_cache_event(namespace: str, outcome: str) -> None:
    CACHE_EVENTS_TOTAL.labels(namespace=namespace, outcome=outcome).inc()


def _request_id_from_header(request: Request) -> str:
    header_value = request.headers.get(REQUEST_ID_HEADER, "").strip()
    if header_value and len(header_value) <= 128:
        return header_value
    return str(uuid.uuid4())


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    if route is None:
        return "unmatched"

    path_segments = request.url.path.split("/")
    path_params = request.path_params
    for param_name, param_value in path_params.items():
        param_segment = str(param_value)
        path_segments = [
            f"{{{param_name}}}" if segment == param_segment else segment
            for segment in path_segments
        ]
    return "/".join(path_segments)


def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    context._observability_started_at = time.perf_counter()
    context._observability_operation = _sql_operation(statement)


def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    _observe_db_query(conn, context, status="ok")


def _handle_cursor_error(exception_context):
    _observe_db_query(
        exception_context.connection,
        exception_context.execution_context,
        status="error",
    )


def _observe_db_query(conn, context, *, status: str) -> None:
    started_at = getattr(context, "_observability_started_at", None)
    if started_at is None:
        return

    operation = getattr(context, "_observability_operation", "UNKNOWN")
    elapsed = time.perf_counter() - started_at
    DB_QUERY_DURATION_SECONDS.labels(
        db_system=conn.engine.dialect.name,
        operation=operation,
        status=status,
    ).observe(elapsed)


def _sql_operation(statement: str) -> str:
    stripped = statement.lstrip()
    if not stripped:
        return "UNKNOWN"
    operation = stripped.split(None, 1)[0].upper()
    return operation if operation.isalpha() else "UNKNOWN"
