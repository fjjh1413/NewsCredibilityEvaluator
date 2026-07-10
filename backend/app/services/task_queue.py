from __future__ import annotations

from app.core.config import get_settings


class TaskQueueUnavailable(RuntimeError):
    pass


def enqueue_detection_task(task_id: str) -> str | None:
    settings = get_settings()
    if settings.async_task_always_eager:
        from app.services.detection_task_service import run_detection_task

        run_detection_task(task_id)
        return None

    try:
        from app.worker import celery_app
    except Exception as exc:
        raise TaskQueueUnavailable(
            "Task queue is unavailable. Install Celery and start the worker."
        ) from exc

    result = celery_app.send_task(
        "app.tasks.detection.run_detection_task",
        args=[task_id],
    )
    return result.id

