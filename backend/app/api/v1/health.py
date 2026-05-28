from fastapi import APIRouter

from app.core.config import get_settings
from app.utils.response import success_response


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

