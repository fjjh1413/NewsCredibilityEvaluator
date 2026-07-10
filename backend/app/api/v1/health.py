from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.observability import metrics_response
from app.core.redis_client import redis_manager
from app.utils.response import error_response, success_response


router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict:
    settings = get_settings()
    return success_response(
        message="service is running",
        data={
            "service": settings.project_name,
            "status": "ok",
            "version": settings.project_version,
        },
    )


@router.get("/metrics", include_in_schema=False)
def metrics():
    return metrics_response()


@router.get("/ready", response_model=None)
async def readiness_check() -> dict | JSONResponse:
    settings = get_settings()
    redis_status = await redis_manager.health(settings)
    checks = {"redis": redis_status.as_dict()}
    redis_ready = redis_status.status in {"ok", "disabled"} or not settings.redis_required
    data = {
        "service": settings.project_name,
        "status": "ok" if redis_ready else "degraded",
        "version": settings.project_version,
        "checks": checks,
    }

    if not redis_ready:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=error_response(
                message="service is not ready",
                code=status.HTTP_503_SERVICE_UNAVAILABLE,
                data=data,
            ),
        )

    return success_response(message="service is ready", data=data)
