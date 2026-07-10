import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.observability import add_observability_middleware
from app.core.profiling import configure_profiling
from app.core.redis_client import redis_manager
from app.core.scheduler import init_scheduler, shutdown_scheduler
from app.core.tracing import configure_tracing
from app.utils.response import error_response

logger = logging.getLogger(__name__)

BASE_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}
PRODUCTION_SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; frame-ancestors 'none'; base-uri 'self'",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: start scheduler on boot, stop on shutdown."""
    logger.info("Starting application lifespan...")
    settings = get_settings()
    init_scheduler()
    try:
        await redis_manager.startup(settings)
        yield
    finally:
        logger.info("Shutting down application lifespan...")
        await redis_manager.shutdown()
        shutdown_scheduler()


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    settings.validate_required_settings()
    configure_tracing(settings)
    configure_profiling(settings, role="backend")
    cors_origins = settings.cors_origins
    cors_allow_credentials = "*" not in cors_origins

    app = FastAPI(
        title=settings.project_name,
        version=settings.project_version,
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
        openapi_url=None if settings.is_production else "/openapi.json",
        lifespan=lifespan,
    )

    _add_security_headers_middleware(app, include_production_headers=settings.is_production)
    add_observability_middleware(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(SQLAlchemyError, database_exception_handler)
    app.include_router(api_router, prefix=settings.api_prefix)
    return app


def _add_security_headers_middleware(
    app: FastAPI,
    *,
    include_production_headers: bool,
) -> None:
    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next):
        response = await call_next(request)
        headers = dict(BASE_SECURITY_HEADERS)
        if include_production_headers:
            headers.update(PRODUCTION_SECURITY_HEADERS)
        for header_name, header_value in headers.items():
            if header_name not in response.headers:
                response.headers[header_name] = header_value
        return response


async def http_exception_handler(
    request: Request,
    exc: HTTPException,
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(
            _format_error_detail(exc.detail),
            code=exc.status_code,
        ),
        headers=exc.headers,
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response(
            _format_validation_errors(exc.errors()),
            code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        ),
    )


async def database_exception_handler(
    request: Request,
    exc: SQLAlchemyError,
) -> JSONResponse:
    settings = get_settings()
    if not settings.env_file_exists:
        message = (
            "backend/.env 不存在，请先复制 backend/.env.example 为 backend/.env，"
            "并填写 MySQL、SECRET_KEY、REPORT_DIR 等本地配置。"
        )
    else:
        message = (
            "数据库连接或操作失败，请检查 backend/.env 中的 DATABASE_URL 或 MySQL 拆分配置、"
            "确认 MySQL 服务已启动、数据库已创建，并按需执行迁移脚本。"
        )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response(
            message,
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        ),
    )


def _format_error_detail(detail: Any) -> str:
    if isinstance(detail, str):
        return detail
    if isinstance(detail, dict):
        return str(detail.get("message") or detail.get("detail") or detail)
    if isinstance(detail, list):
        return _format_validation_errors(detail)
    return str(detail)


def _format_validation_errors(errors: list[dict[str, Any]]) -> str:
    messages: list[str] = []
    for error in errors:
        location = ".".join(str(part) for part in error.get("loc", []) if part != "body")
        message = str(error.get("msg") or "请求参数错误")
        messages.append(f"{location}: {message}" if location else message)
    return "；".join(messages) or "请求参数错误"


app = create_app()
