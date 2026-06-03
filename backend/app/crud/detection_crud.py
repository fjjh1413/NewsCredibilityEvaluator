import json
from datetime import datetime
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.detection_record import DetectionRecord
from app.models.evidence_match import EvidenceMatch
from app.schemas.detection import DetectionCreate


DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def save_detection_record(
    db: Session,
    detection_in: DetectionCreate,
) -> DetectionRecord:
    data = detection_in.model_dump(exclude={"evidence_matches"})
    data["risk_points"] = _dump_risk_points(detection_in.risk_points)

    db_record = DetectionRecord(**data)
    for evidence_in in detection_in.evidence_matches:
        db_record.evidence_matches.append(
            EvidenceMatch(**evidence_in.model_dump())
        )

    db.add(db_record)
    db.commit()
    db.refresh(db_record)
    return db_record


def get_detection_history(
    db: Session,
    current_user: Any,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    risk_level: str | None = None,
    keyword: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    user_id: int | None = None,
) -> tuple[list[DetectionRecord], int]:
    safe_page = max(page, 1)
    safe_page_size = max(1, min(page_size, MAX_PAGE_SIZE))

    query = db.query(DetectionRecord)
    query = _apply_user_scope(query, current_user=current_user, user_id=user_id)
    if risk_level:
        query = query.filter(DetectionRecord.risk_level == risk_level)
    if keyword:
        keyword_pattern = f"%{keyword}%"
        query = query.filter(
            or_(
                DetectionRecord.input_title.like(keyword_pattern),
                DetectionRecord.input_content.like(keyword_pattern),
                DetectionRecord.keywords.like(keyword_pattern),
                DetectionRecord.reason.like(keyword_pattern),
            )
        )
    if date_from:
        query = query.filter(DetectionRecord.created_at >= date_from)
    if date_to:
        query = query.filter(DetectionRecord.created_at <= date_to)

    total = query.count()
    items = (
        query.order_by(DetectionRecord.created_at.desc(), DetectionRecord.id.desc())
        .offset((safe_page - 1) * safe_page_size)
        .limit(safe_page_size)
        .all()
    )
    return items, total


def get_detection_detail(
    db: Session,
    detection_id: int,
    current_user: Any,
) -> DetectionRecord | None:
    query = db.query(DetectionRecord).filter(DetectionRecord.id == detection_id)
    query = _apply_user_scope(query, current_user=current_user)
    return query.first()


def get_detection_record_by_id(
    db: Session,
    detection_id: int,
) -> DetectionRecord | None:
    return db.query(DetectionRecord).filter(DetectionRecord.id == detection_id).first()


def delete_detection_record(
    db: Session,
    detection_id: int,
) -> bool:
    record = get_detection_record_by_id(db, detection_id)
    if record is None:
        return False

    db.delete(record)
    db.commit()
    return True


def _apply_user_scope(query: Any, current_user: Any, user_id: int | None = None) -> Any:
    if _is_admin(current_user):
        if user_id is not None:
            return query.filter(DetectionRecord.user_id == user_id)
        return query

    current_user_id = getattr(current_user, "id", None)
    if current_user_id is None:
        return query.filter(DetectionRecord.id.is_(None))
    return query.filter(DetectionRecord.user_id == current_user_id)


def _is_admin(current_user: Any) -> bool:
    return getattr(current_user, "role", None) == "admin"


def _dump_risk_points(risk_points: list[str]) -> str:
    return json.dumps(risk_points or [], ensure_ascii=False)
