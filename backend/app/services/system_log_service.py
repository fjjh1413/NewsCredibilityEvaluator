import logging
from typing import Any

from fastapi import Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.crud.system_log_crud import create_system_log
from app.models.system_log import SystemLog
from app.schemas.system_log import SystemLogCreate


logger = logging.getLogger(__name__)

MAX_DESCRIPTION_LENGTH = 1000


def record_system_log(
    db: Session,
    *,
    module: str,
    action: str,
    user_id: int | None = None,
    user: Any | None = None,
    description: str | None = None,
    ip_address: str | None = None,
) -> SystemLog | None:
    resolved_user_id = user_id
    if resolved_user_id is None and user is not None:
        resolved_user_id = getattr(user, "id", None)

    try:
        log_in = SystemLogCreate(
            user_id=resolved_user_id,
            module=_clean_required(module, max_length=100),
            action=_clean_required(action, max_length=100),
            description=_clean_optional(
                description,
                max_length=MAX_DESCRIPTION_LENGTH,
            ),
            ip_address=_clean_optional(ip_address, max_length=50),
        )
        return create_system_log(db, log_in)
    except Exception:
        _rollback_quietly(db)
        logger.exception(
            "Failed to record system log module=%s action=%s user_id=%s",
            module,
            action,
            resolved_user_id,
        )
        return None


def get_request_ip(request: Request | None) -> str | None:
    if request is None:
        return None

    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        client_ip = forwarded_for.split(",", 1)[0].strip()
        if client_ip:
            return client_ip

    real_ip = request.headers.get("x-real-ip", "").strip()
    if real_ip:
        return real_ip

    if request.client and request.client.host:
        return request.client.host
    return None


def _clean_required(value: str | None, max_length: int) -> str:
    cleaned = _clean_optional(value, max_length=max_length)
    return cleaned or "unknown"


def _clean_optional(value: str | None, max_length: int) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    return cleaned[:max_length]


def _rollback_quietly(db: Session) -> None:
    try:
        db.rollback()
    except (AttributeError, SQLAlchemyError):
        logger.exception("Failed to rollback after system log write error")
