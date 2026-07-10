from __future__ import annotations

from app.services.detection_task_service import run_detection_task
from app.worker import celery_app


@celery_app.task(name="app.tasks.detection.run_detection_task", bind=True)
def run_detection_task_job(self, task_id: str) -> None:
    run_detection_task(task_id, celery_task_id=self.request.id)

