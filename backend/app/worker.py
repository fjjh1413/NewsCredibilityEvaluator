from __future__ import annotations

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.profiling import configure_profiling


try:
    from celery import Celery
except ImportError as exc:  # pragma: no cover - exercised in deployed worker env
    raise RuntimeError(
        "Celery is required for async detection. Install backend requirements first."
    ) from exc


settings = get_settings()
configure_logging()
settings.validate_required_settings()
configure_profiling(settings, role="worker")

celery_app = Celery(
    "news_credibility_evaluator",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.detection"],
)

celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    task_time_limit=600,
    task_soft_time_limit=540,
    broker_connection_retry_on_startup=True,
    timezone="Asia/Shanghai",
)
