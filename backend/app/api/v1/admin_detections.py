import json
from datetime import datetime

from fastapi import APIRouter, Depends, Path, Query, Request, status
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
from app.services.system_log_service import get_request_ip, record_system_log
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
    raw_analysis_payload = getattr(record, "analysis_payload", None)
    if isinstance(raw_analysis_payload, str) and raw_analysis_payload.strip():
        try:
            analysis_payload = json.loads(raw_analysis_payload)
        except json.JSONDecodeError:
            analysis_payload = {}
    elif isinstance(raw_analysis_payload, dict):
        analysis_payload = raw_analysis_payload
    else:
        analysis_payload = {}

    for field_name in (
        "publish_time",
        "source_name",
        "source_url",
        "candidate_evidence_list",
        "excluded_evidence",
        "similar_news",
        "evidence_quality",
        "arbitration_status",
        "knowledge_has_relevant_match",
        "web_has_relevant_match",
    ):
        if field_name in analysis_payload:
            data[field_name] = analysis_payload[field_name]
    return success_response(data=data)


@router.delete("/{id}", response_model=DetectionDeleteApiResponse)
def delete_admin_detection(
    request: Request,
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

    record_system_log(
        db,
        user_id=current_admin.id,
        module="admin",
        action="delete_detection",
        description=f"管理员删除检测记录 detection_id={id}",
        ip_address=get_request_ip(request),
    )
    return success_response(message="deleted", data={"id": id})
