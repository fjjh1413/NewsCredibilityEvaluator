from datetime import datetime

from sqlalchemy import func, or_
from sqlalchemy.orm import Query, Session

from app.models.detection_record import DetectionRecord


DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def get_public_high_risk_records(
    db: Session,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    category: str | None = None,
    risk_level: str | None = None,
    keyword: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> tuple[list[DetectionRecord], int]:
    safe_page, safe_page_size = _safe_pagination(page, page_size)
    query = _apply_filters(
        _public_query(db),
        category=category,
        risk_level=risk_level,
        keyword=keyword,
        start_date=start_date,
        end_date=end_date,
        summary_only=True,
    )
    total = query.count()
    items = (
        query.order_by(
            DetectionRecord.reviewed_at.desc(),
            DetectionRecord.created_at.desc(),
            DetectionRecord.id.desc(),
        )
        .offset((safe_page - 1) * safe_page_size)
        .limit(safe_page_size)
        .all()
    )
    return items, total


def get_public_high_risk_ranking(
    db: Session,
    limit: int = 10,
) -> list[DetectionRecord]:
    safe_limit = max(1, min(limit, 100))
    return (
        _public_query(db)
        .order_by(
            DetectionRecord.final_score.asc(),
            DetectionRecord.reviewed_at.desc(),
            DetectionRecord.created_at.desc(),
            DetectionRecord.id.desc(),
        )
        .limit(safe_limit)
        .all()
    )


def get_public_high_risk_keyword_values(db: Session) -> list[str | None]:
    rows = _public_query(db).with_entities(DetectionRecord.keywords).all()
    return [row[0] for row in rows]


def get_public_high_risk_category_rows(db: Session) -> list[tuple[str, int]]:
    category_label = func.coalesce(DetectionRecord.category, "未分类")
    return (
        _public_query(db)
        .with_entities(category_label, func.count(DetectionRecord.id))
        .group_by(category_label)
        .order_by(func.count(DetectionRecord.id).desc(), category_label.asc())
        .all()
    )


def get_admin_high_risk_records(
    db: Session,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    risk_level: str | None = None,
    category: str | None = None,
    review_status: str | None = None,
    is_public: bool | None = None,
    keyword: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> tuple[list[DetectionRecord], int]:
    safe_page, safe_page_size = _safe_pagination(page, page_size)
    query = _apply_filters(
        db.query(DetectionRecord).filter(DetectionRecord.is_high_risk.is_(True)),
        category=category,
        risk_level=risk_level,
        keyword=keyword,
        start_date=start_date,
        end_date=end_date,
    )
    if review_status:
        query = query.filter(DetectionRecord.review_status == review_status)
    if is_public is not None:
        query = query.filter(DetectionRecord.is_public.is_(is_public))

    total = query.count()
    items = (
        query.order_by(DetectionRecord.created_at.desc(), DetectionRecord.id.desc())
        .offset((safe_page - 1) * safe_page_size)
        .limit(safe_page_size)
        .all()
    )
    return items, total


def get_high_risk_record(db: Session, record_id: int) -> DetectionRecord | None:
    return (
        db.query(DetectionRecord)
        .filter(
            DetectionRecord.id == record_id,
            DetectionRecord.is_high_risk.is_(True),
        )
        .first()
    )


def save_high_risk_record(db: Session, record: DetectionRecord) -> DetectionRecord:
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def _public_query(db: Session) -> Query:
    return db.query(DetectionRecord).filter(
        DetectionRecord.is_high_risk.is_(True),
        DetectionRecord.review_status == "approved",
        DetectionRecord.is_public.is_(True),
    )


def _apply_filters(
    query: Query,
    category: str | None = None,
    risk_level: str | None = None,
    keyword: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    summary_only: bool = False,
) -> Query:
    if category:
        query = query.filter(DetectionRecord.category == category)
    if risk_level:
        query = query.filter(DetectionRecord.risk_level == risk_level)
    if keyword:
        pattern = f"%{keyword.strip()}%"
        if summary_only:
            query = query.filter(
                or_(
                    DetectionRecord.input_title.like(pattern),
                    func.substr(DetectionRecord.input_content, 1, 150).like(pattern),
                )
            )
        else:
            query = query.filter(
                or_(
                    DetectionRecord.input_title.like(pattern),
                    DetectionRecord.input_content.like(pattern),
                    DetectionRecord.keywords.like(pattern),
                    DetectionRecord.reason.like(pattern),
                )
            )
    if start_date:
        query = query.filter(DetectionRecord.created_at >= start_date)
    if end_date:
        query = query.filter(DetectionRecord.created_at <= end_date)
    return query


def _safe_pagination(page: int, page_size: int) -> tuple[int, int]:
    return max(page, 1), max(1, min(page_size, MAX_PAGE_SIZE))
