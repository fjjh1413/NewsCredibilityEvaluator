from datetime import date

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_admin
from app.db.session import get_db
from app.models.user import User
from app.schemas.statistics import (
    DetectionTrendApiResponse,
    KnowledgeOverviewApiResponse,
    StatisticsDistributionApiResponse,
    StatisticsKeywordsApiResponse,
    StatisticsOverviewApiResponse,
    UserActivityApiResponse,
)
from app.services.statistics_service import (
    StatisticsRangeError,
    get_category_distribution,
    get_detection_trend,
    get_keyword_statistics,
    get_knowledge_overview,
    get_risk_distribution,
    get_statistics_overview,
    get_user_activity,
)
from app.utils.response import error_response, success_response


router = APIRouter(prefix="/admin/statistics", tags=["admin-statistics"])


@router.get("/overview", response_model=StatisticsOverviewApiResponse)
def read_statistics_overview(
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict:
    return success_response(data=get_statistics_overview(db))


@router.get("/trend", response_model=DetectionTrendApiResponse)
def read_detection_trend(
    days: int = Query(default=7, ge=1, le=366),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict | JSONResponse:
    try:
        data = get_detection_trend(db, days, start_date, end_date)
    except StatisticsRangeError as exc:
        return _unprocessable(exc)
    return success_response(data=data)


@router.get(
    "/risk-distribution",
    response_model=StatisticsDistributionApiResponse,
)
def read_risk_distribution(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict | JSONResponse:
    try:
        data = get_risk_distribution(db, start_date, end_date)
    except StatisticsRangeError as exc:
        return _unprocessable(exc)
    return success_response(data=data)


@router.get(
    "/category-distribution",
    response_model=StatisticsDistributionApiResponse,
)
def read_category_distribution(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict | JSONResponse:
    try:
        data = get_category_distribution(db, start_date, end_date)
    except StatisticsRangeError as exc:
        return _unprocessable(exc)
    return success_response(data=data)


@router.get("/keywords", response_model=StatisticsKeywordsApiResponse)
def read_keyword_statistics(
    limit: int = Query(default=20, ge=1, le=100),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict | JSONResponse:
    try:
        data = get_keyword_statistics(db, limit, start_date, end_date)
    except StatisticsRangeError as exc:
        return _unprocessable(exc)
    return success_response(data=data)


@router.get("/user-activity", response_model=UserActivityApiResponse)
def read_user_activity(
    days: int = Query(default=30, ge=1, le=366),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict | JSONResponse:
    try:
        data = get_user_activity(db, days, start_date, end_date)
    except StatisticsRangeError as exc:
        return _unprocessable(exc)
    return success_response(data=data)


@router.get("/knowledge-overview", response_model=KnowledgeOverviewApiResponse)
def read_knowledge_overview(
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict:
    return success_response(data=get_knowledge_overview(db))


@router.get(
    "/knowledge-vector-status",
    response_model=StatisticsDistributionApiResponse,
    include_in_schema=False,
)
def read_knowledge_vector_status(
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict:
    data = get_knowledge_overview(db)["vector_status_distribution"]
    return success_response(data=data)


def _unprocessable(exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response(str(exc), code=422),
    )
