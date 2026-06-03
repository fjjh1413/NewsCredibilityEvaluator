from datetime import datetime

from fastapi import APIRouter, Depends, Path, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_admin
from app.crud.detection_crud import (
    delete_detection_record,
    get_detection_detail,
    get_detection_history,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.detection import (
    DetectionDeleteApiResponse,
    DetectionDetailApiResponse,
    DetectionDetailOut,
    DetectionHistoryApiResponse,
    DetectionHistoryData,
    DetectionHistoryItem,
)
from app.utils.response import error_response, success_response


router = APIRouter(prefix="/admin/detections", tags=["admin-detections"])


@router.get("", response_model=DetectionHistoryApiResponse)
def read_admin_detections(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    risk_level: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    user_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict:
    items, total = get_detection_history(
        db,
        current_user=current_admin,
        page=page,
        page_size=page_size,
        risk_level=risk_level,
        keyword=keyword,
        date_from=date_from,
        date_to=date_to,
        user_id=user_id,
    )
    data = DetectionHistoryData(
        total=total,
        page=page,
        page_size=page_size,
        items=[DetectionHistoryItem.model_validate(item) for item in items],
    ).model_dump(mode="json")
    return success_response(data=data)


@router.get("/{id}", response_model=DetectionDetailApiResponse)
def read_admin_detection_detail(
    id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict:
    record = get_detection_detail(db, detection_id=id, current_user=current_admin)
    if record is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=error_response("Detection record not found", code=404),
        )

    data = DetectionDetailOut.model_validate(record).model_dump(mode="json")
    return success_response(data=data)


@router.delete("/{id}", response_model=DetectionDeleteApiResponse)
def delete_admin_detection(
    id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict:
    deleted = delete_detection_record(db, id)
    if not deleted:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=error_response("Detection record not found", code=404),
        )

    return success_response(message="deleted", data={"id": id})
