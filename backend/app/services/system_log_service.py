import logging
import math
from typing import Any

from fastapi import Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.client_ip import get_client_ip
from app.core.logging import request_id_context
from app.crud.system_log_crud import create_system_log
from app.models.system_log import SystemLog
from app.schemas.system_log import SystemLogCreate


logger = logging.getLogger(__name__)

MAX_DESCRIPTION_LENGTH = 1000
MAX_METADATA_DEPTH = 4
MAX_METADATA_ITEMS = 20
MAX_METADATA_STRING_LENGTH = 500
SENSITIVE_METADATA_KEYS = (
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
    "api_key",
    "access_token",
    "refresh_token",
)


def record_system_log(
    db: Session,
    *,
    module: str,
    action: str,
    user_id: int | None = None,
    user: Any | None = None,
    description: str | None = None,
    ip_address: str | None = None,
    request_id: str | None = None,
    target_type: str | None = None,
    target_id: str | int | None = None,
    result_status: str | None = "success",
    metadata_json: dict[str, Any] | None = None,
) -> SystemLog | None:
    resolved_user_id = user_id
    if resolved_user_id is None and user is not None:
        resolved_user_id = getattr(user, "id", None)
    resolved_request_id = _clean_optional(request_id, max_length=128) or _current_request_id()

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
            request_id=resolved_request_id,
            target_type=_clean_optional(target_type, max_length=100),
            target_id=_clean_optional(target_id, max_length=100),
            result_status=_clean_optional(result_status, max_length=20),
            metadata_json=_clean_metadata(metadata_json),
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

    return get_client_ip(request)


def _current_request_id() -> str | None:
    current = request_id_context.get()
    if not current or current == "-":
        return None
    return _clean_optional(current, max_length=128)


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


def _clean_metadata(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    cleaned = _clean_metadata_value(value, depth=0)
    if isinstance(cleaned, dict):
        return cleaned
    return {"value": cleaned}


def _clean_metadata_value(value: Any, *, depth: int) -> Any:
    if depth >= MAX_METADATA_DEPTH:
        return _stringify_metadata_value(value)

    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for raw_key, raw_value in list(value.items())[:MAX_METADATA_ITEMS]:
            key = _clean_optional(raw_key, max_length=100) or "unknown"
            if _is_sensitive_metadata_key(key):
                cleaned[key] = "[redacted]"
                continue
            cleaned[key] = _clean_metadata_value(raw_value, depth=depth + 1)
        return cleaned

    if isinstance(value, (list, tuple, set)):
        return [
            _clean_metadata_value(item, depth=depth + 1)
            for item in list(value)[:MAX_METADATA_ITEMS]
        ]

    if isinstance(value, str):
        return _clean_optional(value, max_length=MAX_METADATA_STRING_LENGTH)

    if isinstance(value, bool) or value is None or isinstance(value, int):
        return value

    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)

    return _stringify_metadata_value(value)


def _stringify_metadata_value(value: Any) -> str | None:
    return _clean_optional(value, max_length=MAX_METADATA_STRING_LENGTH)


def _is_sensitive_metadata_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(sensitive_key in normalized for sensitive_key in SENSITIVE_METADATA_KEYS)


def _rollback_quietly(db: Session) -> None:
    try:
        db.rollback()
    except (AttributeError, SQLAlchemyError):
        logger.exception("Failed to rollback after system log write error")
