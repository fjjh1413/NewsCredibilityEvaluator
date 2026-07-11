from datetime import datetime

from fastapi import APIRouter, Depends, Path, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_admin
from app.db.session import get_db
from app.models.user import User
from app.schemas.high_risk import (
    AdminHighRiskDetailApiResponse,
    AdminHighRiskListApiResponse,
    HighRiskPublicUpdate,
    HighRiskRemarkUpdate,
    HighRiskReviewUpdate,
)
from app.services.high_risk_service import (
    HighRiskConflictError,
    HighRiskNotFoundError,
    get_admin_high_risk_detail,
    list_admin_high_risk,
    update_high_risk_public_status,
    update_high_risk_remark,
    update_high_risk_review,
)
from app.services.system_log_service import get_request_ip, record_system_log
from app.utils.response import error_response, success_response


router = APIRouter(prefix="/admin/high-risk", tags=["admin-high-risk"])


@router.get("", response_model=AdminHighRiskListApiResponse)
def read_admin_high_risk(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    risk_level: str | None = Query(default=None),
    category: str | None = Query(default=None),
    review_status: str | None = Query(default=None),
    is_public: bool | None = Query(default=None),
    keyword: str | None = Query(default=None),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict:
    items, total = list_admin_high_risk(
        db,
        page=page,
        page_size=page_size,
        risk_level=risk_level,
        category=category,
        review_status=review_status,
        is_public=is_public,
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


@router.get("/{record_id}", response_model=AdminHighRiskDetailApiResponse)
def read_admin_high_risk_detail(
    record_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict | JSONResponse:
    try:
        data = get_admin_high_risk_detail(db, record_id)
    except HighRiskNotFoundError as exc:
        return _not_found(exc)
    return success_response(data=data)


@router.put("/{record_id}/review", response_model=AdminHighRiskDetailApiResponse)
def review_admin_high_risk(
    payload: HighRiskReviewUpdate,
    request: Request,
    record_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict | JSONResponse:
    try:
        data = update_high_risk_review(
            db,
            record_id,
            payload.review_status,
            int(current_admin.id),
            payload.admin_remark,
        )
    except HighRiskNotFoundError as exc:
        return _not_found(exc)
    record_system_log(
        db,
        user_id=current_admin.id,
        module="high_risk",
        action="review",
        description=(
            f"管理员审核高风险记录 record_id={record_id} "
            f"review_status={payload.review_status}"
        ),
        ip_address=get_request_ip(request),
        target_type="detection",
        target_id=record_id,
        result_status="success",
        metadata_json={"review_status": payload.review_status},
    )
    return success_response(data=data)


@router.put("/{record_id}/public", response_model=AdminHighRiskDetailApiResponse)
def update_admin_high_risk_public(
    payload: HighRiskPublicUpdate,
    request: Request,
    record_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict | JSONResponse:
    try:
        data = update_high_risk_public_status(db, record_id, payload.is_public)
    except HighRiskNotFoundError as exc:
        return _not_found(exc)
    except HighRiskConflictError as exc:
        return _conflict(exc)
    record_system_log(
        db,
        user_id=current_admin.id,
        module="high_risk",
        action="update_public",
        description=(
            f"管理员更新高风险公开状态 record_id={record_id} "
            f"is_public={payload.is_public}"
        ),
        ip_address=get_request_ip(request),
        target_type="detection",
        target_id=record_id,
        result_status="success",
        metadata_json={"is_public": payload.is_public},
    )
    return success_response(data=data)


@router.put("/{record_id}/remark", response_model=AdminHighRiskDetailApiResponse)
def update_admin_high_risk_remark(
    payload: HighRiskRemarkUpdate,
    request: Request,
    record_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict | JSONResponse:
    try:
        data = update_high_risk_remark(db, record_id, payload.admin_remark)
    except HighRiskNotFoundError as exc:
        return _not_found(exc)
    record_system_log(
        db,
        user_id=current_admin.id,
        module="high_risk",
        action="update_remark",
        description=f"管理员更新高风险备注 record_id={record_id}",
        ip_address=get_request_ip(request),
        target_type="detection",
        target_id=record_id,
        result_status="success",
    )
    return success_response(data=data)


def _not_found(exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=error_response(str(exc), code=404),
    )


def _conflict(exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content=error_response(str(exc), code=409),
    )
