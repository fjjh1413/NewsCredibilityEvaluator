from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.high_risk import (
    HighRiskCategoriesApiResponse,
    HighRiskKeywordsApiResponse,
    PublicHighRiskListApiResponse,
    PublicHighRiskRankingApiResponse,
)
from app.services.high_risk_service import (
    get_public_high_risk_categories,
    get_public_high_risk_keywords,
    list_public_high_risk,
    list_public_high_risk_ranking,
)
from app.utils.response import success_response


router = APIRouter(prefix="/high-risk", tags=["high-risk"])


@router.get("/public", response_model=PublicHighRiskListApiResponse)
def read_public_high_risk(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    category: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    items, total = list_public_high_risk(
        db,
        page=page,
        page_size=page_size,
        category=category,
        risk_level=risk_level,
        keyword=keyword,
        start_date=start_date,
        end_date=end_date,
    )
    return success_response(
        data={
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items,
        }
    )


@router.get("/ranking", response_model=PublicHighRiskRankingApiResponse)
def read_public_high_risk_ranking(
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    return success_response(data={"items": list_public_high_risk_ranking(db, limit)})


@router.get("/keywords", response_model=HighRiskKeywordsApiResponse)
def read_public_high_risk_keywords(
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    return success_response(data=get_public_high_risk_keywords(db, limit))


@router.get(
    "/category-distribution",
    response_model=HighRiskCategoriesApiResponse,
)
def read_public_high_risk_categories(
    db: Session = Depends(get_db),
) -> dict:
    return success_response(data=get_public_high_risk_categories(db))
