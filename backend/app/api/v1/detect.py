from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import get_current_user, get_optional_current_user
from app.core.rate_limit import InMemoryRateLimiter
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
    detect_news_credibility,
)
from app.services.system_log_service import get_request_ip, record_system_log
from app.utils.response import error_response, success_response


router = APIRouter(prefix="/detect", tags=["detect"])
detector_rate_limiter = InMemoryRateLimiter()


def _get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        client_ip = forwarded_for.split(",", 1)[0].strip()
        if client_ip:
            return client_ip

    real_ip = request.headers.get("x-real-ip", "").strip()
    if real_ip:
        return real_ip

    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def enforce_detect_news_rate_limit(request: Request) -> None:
    settings = get_settings()
    client_ip = _get_client_ip(request)
    is_allowed = detector_rate_limiter.allow_request(
        key=client_ip,
        limit=settings.detect_rate_limit_count,
        window_seconds=settings.detect_rate_limit_window_seconds,
    )
    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="检测请求过于频繁，请稍后再试",
        )


@router.post(
    "/news",
    response_model=DetectNewsApiResponse,
    dependencies=[Depends(enforce_detect_news_rate_limit)],
)
def detect_news(
    payload: DetectNewsRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
) -> dict:
    try:
        result = detect_news_credibility(
            db=db,
            payload=payload,
            current_user=current_user,
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

    record_system_log(
        db,
        user_id=getattr(current_user, "id", None),
        module="detection",
        action="detect_news",
        description=(
            f"完成新闻检测 detection_id={result.get('detection_id')} "
            f"risk_level={result.get('risk_level')} "
            f"final_score={result.get('final_score')}"
        ),
        ip_address=get_request_ip(request),
    )
    return success_response(message="检测完成", data=result)


@router.get("/history", response_model=DetectionHistoryApiResponse)
def read_detection_history(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    risk_level: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    items, total = get_detection_history(
        db,
        current_user=current_user,
        page=page,
        page_size=page_size,
        risk_level=risk_level,
        keyword=keyword,
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
