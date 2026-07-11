from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from app.core.deps import get_current_admin
from app.models.user import User
from app.schemas.ai_engineering import AiEngineeringSummaryApiResponse
from app.services.ai_engineering_service import (
    AiEngineeringSummaryNotFoundError,
    get_ai_engineering_summary,
)
from app.utils.response import error_response, success_response


router = APIRouter(prefix="/admin/ai-engineering", tags=["admin-ai-engineering"])


@router.get("/summary", response_model=AiEngineeringSummaryApiResponse)
def read_ai_engineering_summary(
    current_admin: User = Depends(get_current_admin),
) -> dict | JSONResponse:
    try:
        data = get_ai_engineering_summary()
    except AiEngineeringSummaryNotFoundError as exc:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=error_response(str(exc), code=status.HTTP_404_NOT_FOUND),
        )
    return success_response(data=data)
