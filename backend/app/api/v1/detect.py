from fastapi import APIRouter, Depends, Path, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_optional_current_user
from app.crud.detection_crud import get_detection_detail, get_detection_history
from app.db.session import get_db
from app.models.user import User
from app.schemas.detection import (
    DetectNewsApiResponse,
    DetectNewsRequest,
    DetectionDetailApiResponse,
    DetectionDetailOut,
    DetectionHistoryApiResponse,
    DetectionHistoryData,
    DetectionHistoryItem,
)
from app.services.detection_service import (
    DetectionServiceError,
    KnowledgeRetrievalFailedError,
    LLMAnalysisFailedError,
    detect_news_credibility,
)
from app.utils.response import error_response, success_response


router = APIRouter(prefix="/detect", tags=["detect"])


@router.post("/news", response_model=DetectNewsApiResponse)
def detect_news(
    payload: DetectNewsRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
) -> dict:
    try:
        result = detect_news_credibility(
            db=db,
            payload=payload,
            current_user=current_user,
        )
    except LLMAnalysisFailedError as exc:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=error_response(
                message=f"DeepSeek 分析失败：{exc}",
                code=503,
            ),
        )
    except KnowledgeRetrievalFailedError as exc:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=error_response(message=str(exc), code=503),
        )
    except DetectionServiceError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=error_response(message=str(exc), code=400),
        )

    return success_response(message="检测完成", data=result)


@router.get("/history", response_model=DetectionHistoryApiResponse)
def read_detection_history(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    risk_level: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    items, total = get_detection_history(
        db,
        current_user=current_user,
        page=page,
        page_size=page_size,
        risk_level=risk_level,
    )
    data = DetectionHistoryData(
        total=total,
        page=page,
        page_size=page_size,
        items=[DetectionHistoryItem.model_validate(item) for item in items],
    ).model_dump(mode="json")
    return success_response(data=data)


@router.get("/{id}", response_model=DetectionDetailApiResponse)
def read_detection_detail(
    id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    record = get_detection_detail(db, detection_id=id, current_user=current_user)
    if record is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=error_response("Detection record not found", code=404),
        )

    data = DetectionDetailOut.model_validate(record).model_dump(mode="json")
    return success_response(data=data)
