from datetime import date

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.cache import cache_service
from app.core.config import get_settings
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
async def read_statistics_overview(
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict:
    data = await _cached_statistics(
        "overview",
        lambda: run_in_threadpool(get_statistics_overview, db),
    )
    return success_response(data=data)


@router.get("/trend", response_model=DetectionTrendApiResponse)
async def read_detection_trend(
    days: int = Query(default=7, ge=1, le=366),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict | JSONResponse:
    try:
        data = await _cached_statistics(
            "trend",
            lambda: run_in_threadpool(
                get_detection_trend,
                db,
                days,
                start_date,
                end_date,
            ),
            days,
            _date_key(start_date),
            _date_key(end_date),
        )
    except StatisticsRangeError as exc:
        return _unprocessable(exc)
    return success_response(data=data)


@router.get(
    "/risk-distribution",
    response_model=StatisticsDistributionApiResponse,
)
async def read_risk_distribution(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict | JSONResponse:
    try:
        data = await _cached_statistics(
            "risk-distribution",
            lambda: run_in_threadpool(get_risk_distribution, db, start_date, end_date),
            _date_key(start_date),
            _date_key(end_date),
        )
    except StatisticsRangeError as exc:
        return _unprocessable(exc)
    return success_response(data=data)


@router.get(
    "/category-distribution",
    response_model=StatisticsDistributionApiResponse,
)
async def read_category_distribution(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict | JSONResponse:
    try:
        data = await _cached_statistics(
            "category-distribution",
            lambda: run_in_threadpool(
                get_category_distribution,
                db,
                start_date,
                end_date,
            ),
            _date_key(start_date),
            _date_key(end_date),
        )
    except StatisticsRangeError as exc:
        return _unprocessable(exc)
    return success_response(data=data)


@router.get("/keywords", response_model=StatisticsKeywordsApiResponse)
async def read_keyword_statistics(
    limit: int = Query(default=20, ge=1, le=100),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict | JSONResponse:
    try:
        data = await _cached_statistics(
            "keywords",
            lambda: run_in_threadpool(
                get_keyword_statistics,
                db,
                limit,
                start_date,
                end_date,
            ),
            limit,
            _date_key(start_date),
            _date_key(end_date),
        )
    except StatisticsRangeError as exc:
        return _unprocessable(exc)
    return success_response(data=data)


@router.get("/user-activity", response_model=UserActivityApiResponse)
async def read_user_activity(
    days: int = Query(default=30, ge=1, le=366),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict | JSONResponse:
    try:
        data = await _cached_statistics(
            "user-activity",
            lambda: run_in_threadpool(
                get_user_activity,
                db,
                days,
                start_date,
                end_date,
            ),
            days,
            _date_key(start_date),
            _date_key(end_date),
        )
    except StatisticsRangeError as exc:
        return _unprocessable(exc)
    return success_response(data=data)


@router.get("/knowledge-overview", response_model=KnowledgeOverviewApiResponse)
async def read_knowledge_overview(
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict:
    data = await _cached_statistics(
        "knowledge-overview",
        lambda: run_in_threadpool(get_knowledge_overview, db),
    )
    return success_response(data=data)


@router.get(
    "/knowledge-vector-status",
    response_model=StatisticsDistributionApiResponse,
    include_in_schema=False,
)
async def read_knowledge_vector_status(
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict:
    overview = await _cached_statistics(
        "knowledge-overview",
        lambda: run_in_threadpool(get_knowledge_overview, db),
    )
    data = overview["vector_status_distribution"]
    return success_response(data=data)


def _unprocessable(exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=error_response(str(exc), code=422),
    )


async def _cached_statistics(
    name: str,
    producer,
    *parts: object,
):
    settings = get_settings()
    key = ":".join(
        ["admin:statistics:v1", name, *(str(part) for part in parts)]
    ).rstrip(":")
    return await cache_service.get_or_set(
        key,
        producer,
        ttl_seconds=settings.admin_statistics_cache_ttl_seconds,
        settings=settings,
    )


def _date_key(value: date | None) -> str:
    return value.isoformat() if value else "none"
