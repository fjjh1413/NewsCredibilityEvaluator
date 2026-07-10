from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import Any

from sqlalchemy.orm import Session

from app.core.observability import (
    observe_detection_task_duration,
    record_detection_task_event,
)
from app.core.profiling import profile_block
from app.crud.user import get_user_by_id
from app.db.session import SessionLocal
from app.models.detection_task import DetectionTask
from app.models.user import User
from app.schemas.detection import DetectNewsRequest
from app.services.detection_service import detect_news_credibility


DETECTION_TASK_STATUS_QUEUED = "queued"
DETECTION_TASK_STATUS_RUNNING = "running"
DETECTION_TASK_STATUS_SUCCEEDED = "succeeded"
DETECTION_TASK_STATUS_FAILED = "failed"
DETECTION_TASK_TERMINAL_STATUSES = {
    DETECTION_TASK_STATUS_SUCCEEDED,
    DETECTION_TASK_STATUS_FAILED,
}


def create_detection_task(
    *,
    db: Session,
    payload: DetectNewsRequest,
    current_user: User | None,
) -> DetectionTask:
    task = DetectionTask(
        id=str(uuid.uuid4()),
        user_id=getattr(current_user, "id", None),
        status=DETECTION_TASK_STATUS_QUEUED,
        request_payload=_json_dumps(payload.model_dump(mode="json")),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    record_detection_task_event(DETECTION_TASK_STATUS_QUEUED)
    return task


def attach_celery_task_id(
    *,
    db: Session,
    task: DetectionTask,
    celery_task_id: str | None,
) -> DetectionTask:
    if not celery_task_id:
        return task
    task.celery_task_id = celery_task_id
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def get_detection_task(
    *,
    db: Session,
    task_id: str,
    current_user: User | None,
) -> DetectionTask | None:
    task = db.get(DetectionTask, task_id)
    if task is None:
        return None
    user_id = getattr(current_user, "id", None)
    role = getattr(current_user, "role", None)
    if role == "admin" or task.user_id is None or task.user_id == user_id:
        return task
    return None


def serialize_detection_task(task: DetectionTask) -> dict[str, Any]:
    return {
        "task_id": task.id,
        "celery_task_id": task.celery_task_id,
        "status": task.status,
        "detection_id": task.detection_id,
        "result": _json_loads(task.result_payload),
        "error_message": task.error_message,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "started_at": task.started_at,
        "finished_at": task.finished_at,
    }


def run_detection_task(task_id: str, celery_task_id: str | None = None) -> None:
    started_at = time.perf_counter()
    db = SessionLocal()
    task: DetectionTask | None = None
    try:
        task = db.get(DetectionTask, task_id)
        if task is None:
            raise ValueError(f"Detection task not found: {task_id}")
        if task.status == DETECTION_TASK_STATUS_SUCCEEDED:
            return

        _mark_task_running(db, task, celery_task_id=celery_task_id)
        record_detection_task_event(DETECTION_TASK_STATUS_RUNNING)
        payload = DetectNewsRequest(**_json_loads(task.request_payload))
        current_user = _load_user_snapshot(db, task.user_id)
        with profile_block({"operation": "detection_task"}):
            result = detect_news_credibility(
                db=db,
                payload=payload,
                current_user=current_user,
            )
        task.status = DETECTION_TASK_STATUS_SUCCEEDED
        task.result_payload = _json_dumps(result)
        task.error_message = None
        task.detection_id = _coerce_optional_int(result.get("detection_id"))
        task.finished_at = _utcnow()
        db.add(task)
        db.commit()
        record_detection_task_event(DETECTION_TASK_STATUS_SUCCEEDED)
        observe_detection_task_duration(
            DETECTION_TASK_STATUS_SUCCEEDED,
            time.perf_counter() - started_at,
        )
    except Exception as exc:
        db.rollback()
        if task is not None:
            _mark_task_failed(db, task, error_message=str(exc))
            record_detection_task_event(DETECTION_TASK_STATUS_FAILED)
            observe_detection_task_duration(
                DETECTION_TASK_STATUS_FAILED,
                time.perf_counter() - started_at,
            )
        raise
    finally:
        db.close()


def _mark_task_running(
    db: Session,
    task: DetectionTask,
    *,
    celery_task_id: str | None,
) -> None:
    task.status = DETECTION_TASK_STATUS_RUNNING
    task.celery_task_id = celery_task_id or task.celery_task_id
    task.error_message = None
    task.started_at = _utcnow()
    task.finished_at = None
    db.add(task)
    db.commit()
    db.refresh(task)


def _mark_task_failed(db: Session, task: DetectionTask, *, error_message: str) -> None:
    task.status = DETECTION_TASK_STATUS_FAILED
    task.error_message = error_message[:4000]
    task.finished_at = _utcnow()
    db.add(task)
    db.commit()


def _coerce_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _load_user_snapshot(db: Session, user_id: int | None) -> SimpleNamespace | None:
    if not user_id:
        return None
    user = get_user_by_id(db, user_id)
    if user is None:
        return None
    return SimpleNamespace(
        id=user.id,
        username=user.username,
        role=user.role,
        status=user.status,
    )


def _json_loads(value: str | None) -> Any:
    if not value:
        return None
    return json.loads(value)


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=_json_default, sort_keys=True)


def _json_default(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)
