from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from app.models.detection_record import DetectionRecord
from app.models.knowledge_item import KnowledgeItem
from app.models.report import Report
from app.models.user import User


def get_overview_counts(db: Session, today: date) -> dict[str, int]:
    day_start = datetime.combine(today, time.min)
    next_day_start = day_start + timedelta(days=1)
    return {
        "total_detections": db.query(func.count(DetectionRecord.id)).scalar() or 0,
        "today_detections": (
            db.query(func.count(DetectionRecord.id))
            .filter(
                DetectionRecord.created_at >= day_start,
                DetectionRecord.created_at < next_day_start,
            )
            .scalar()
            or 0
        ),
        "total_users": db.query(func.count(User.id)).scalar() or 0,
        "total_knowledge": db.query(func.count(KnowledgeItem.id)).scalar() or 0,
        "total_high_risk": (
            db.query(func.count(DetectionRecord.id))
            .filter(DetectionRecord.is_high_risk.is_(True))
            .scalar()
            or 0
        ),
        "total_reports": db.query(func.count(Report.id)).scalar() or 0,
    }


def get_detection_trend_rows(
    db: Session,
    start_date: date,
    end_date: date,
) -> list[tuple[Any, int]]:
    day = func.date(DetectionRecord.created_at)
    return (
        db.query(day.label("day"), func.count(DetectionRecord.id).label("count"))
        .filter(*_date_range_filters(DetectionRecord.created_at, start_date, end_date))
        .group_by(day)
        .order_by(day.asc())
        .all()
    )


def get_detection_distribution_rows(
    db: Session,
    field: Any,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[tuple[Any, int]]:
    query = db.query(field.label("name"), func.count(DetectionRecord.id).label("count"))
    if start_date and end_date:
        query = query.filter(
            *_date_range_filters(DetectionRecord.created_at, start_date, end_date)
        )
    return query.group_by(field).order_by(func.count(DetectionRecord.id).desc()).all()


def get_detection_keyword_values(
    db: Session,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[str]:
    query = db.query(DetectionRecord.keywords).filter(
        DetectionRecord.keywords.is_not(None)
    )
    if start_date and end_date:
        query = query.filter(
            *_date_range_filters(DetectionRecord.created_at, start_date, end_date)
        )
    return [value for (value,) in query.all() if value]


def get_user_activity_rows(
    db: Session,
    start_date: date,
    end_date: date,
) -> list[tuple[Any, int]]:
    day = func.date(DetectionRecord.created_at)
    return (
        db.query(
            day.label("day"),
            func.count(distinct(DetectionRecord.user_id)).label("active_users"),
        )
        .filter(
            DetectionRecord.user_id.is_not(None),
            *_date_range_filters(DetectionRecord.created_at, start_date, end_date),
        )
        .group_by(day)
        .order_by(day.asc())
        .all()
    )


def get_knowledge_distribution_rows(
    db: Session,
    field: Any,
) -> list[tuple[Any, int]]:
    return (
        db.query(field.label("name"), func.count(KnowledgeItem.id).label("count"))
        .group_by(field)
        .order_by(func.count(KnowledgeItem.id).desc())
        .all()
    )


def get_knowledge_total(db: Session) -> int:
    return db.query(func.count(KnowledgeItem.id)).scalar() or 0


def _date_range_filters(
    field: Any,
    start_date: date,
    end_date: date,
) -> tuple[Any, Any]:
    start = datetime.combine(start_date, time.min)
    end_exclusive = datetime.combine(end_date + timedelta(days=1), time.min)
    return field >= start, field < end_exclusive
