from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.system_log import SystemLog
from app.models.user import User
from app.schemas.system_log import SystemLogCreate


DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def create_system_log(db: Session, log_in: SystemLogCreate) -> SystemLog:
    db_log = SystemLog(**log_in.model_dump())
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log


def list_system_logs(
    db: Session,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    module: str | None = None,
    action: str | None = None,
    user_id: int | None = None,
    keyword: str | None = None,
    request_id: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    result_status: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> tuple[list[tuple[SystemLog, str | None]], int]:
    safe_page = max(page, 1)
    safe_page_size = max(1, min(page_size, MAX_PAGE_SIZE))

    query = db.query(SystemLog, User.username).outerjoin(User, SystemLog.user_id == User.id)
    if module:
        query = query.filter(SystemLog.module == module)
    if action:
        query = query.filter(SystemLog.action == action)
    if user_id is not None:
        query = query.filter(SystemLog.user_id == user_id)
    if request_id:
        query = query.filter(SystemLog.request_id == request_id)
    if target_type:
        query = query.filter(SystemLog.target_type == target_type)
    if target_id:
        query = query.filter(SystemLog.target_id == target_id)
    if result_status:
        query = query.filter(SystemLog.result_status == result_status)
    if date_from:
        query = query.filter(SystemLog.created_at >= date_from)
    if date_to:
        query = query.filter(SystemLog.created_at <= date_to)

    cleaned_keyword = keyword.strip() if keyword else ""
    if cleaned_keyword:
        keyword_pattern = f"%{cleaned_keyword}%"
        query = query.filter(
            or_(
                SystemLog.module.like(keyword_pattern),
                SystemLog.action.like(keyword_pattern),
                SystemLog.description.like(keyword_pattern),
                SystemLog.ip_address.like(keyword_pattern),
                SystemLog.request_id.like(keyword_pattern),
                SystemLog.target_type.like(keyword_pattern),
                SystemLog.target_id.like(keyword_pattern),
                SystemLog.result_status.like(keyword_pattern),
                User.username.like(keyword_pattern),
            )
        )

    total = query.count()
    rows = (
        query.order_by(SystemLog.created_at.desc(), SystemLog.id.desc())
        .offset((safe_page - 1) * safe_page_size)
        .limit(safe_page_size)
        .all()
    )
    return [(log, username) for log, username in rows], total
