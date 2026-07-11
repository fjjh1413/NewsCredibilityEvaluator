from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.knowledge_index_job import KnowledgeIndexJob
from app.models.knowledge_item import KnowledgeItem
from app.utils.text_cleaner import clean_text


logger = logging.getLogger(__name__)

KNOWLEDGE_INDEX_OPERATION_UPSERT = "upsert"

KNOWLEDGE_INDEX_JOB_STATUS_QUEUED = "queued"
KNOWLEDGE_INDEX_JOB_STATUS_PROCESSING = "processing"
KNOWLEDGE_INDEX_JOB_STATUS_SUCCEEDED = "succeeded"
KNOWLEDGE_INDEX_JOB_STATUS_FAILED = "failed"
KNOWLEDGE_INDEX_JOB_STATUS_DEAD = "dead"
KNOWLEDGE_INDEX_JOB_STATUS_SKIPPED = "skipped"

_RETRYABLE_STATUSES = {
    KNOWLEDGE_INDEX_JOB_STATUS_QUEUED,
    KNOWLEDGE_INDEX_JOB_STATUS_FAILED,
}
_COALESCIBLE_STATUSES = {
    KNOWLEDGE_INDEX_JOB_STATUS_QUEUED,
    KNOWLEDGE_INDEX_JOB_STATUS_FAILED,
}


def enqueue_knowledge_index_job(
    db: Session,
    item: KnowledgeItem,
    *,
    operation: str = KNOWLEDGE_INDEX_OPERATION_UPSERT,
    source: str | None = None,
    max_attempts: int | None = None,
    auto_commit: bool = True,
) -> KnowledgeIndexJob:
    knowledge_id = int(getattr(item, "id"))
    attempts_limit = max(1, max_attempts or get_settings().knowledge_index_job_max_attempts)
    now = _utcnow()

    existing = (
        db.query(KnowledgeIndexJob)
        .filter(
            KnowledgeIndexJob.knowledge_id == knowledge_id,
            KnowledgeIndexJob.operation == operation,
            KnowledgeIndexJob.status.in_(_COALESCIBLE_STATUSES),
        )
        .order_by(KnowledgeIndexJob.id.desc())
        .first()
    )
    if existing is not None:
        existing.status = KNOWLEDGE_INDEX_JOB_STATUS_QUEUED
        existing.source = source or existing.source
        existing.attempts = 0
        existing.error_message = None
        existing.next_attempt_at = now
        existing.finished_at = None
        existing.max_attempts = attempts_limit
        db.add(existing)
        _finish_write(db, existing, auto_commit=auto_commit)
        return existing

    job = KnowledgeIndexJob(
        knowledge_id=knowledge_id,
        operation=operation,
        status=KNOWLEDGE_INDEX_JOB_STATUS_QUEUED,
        source=source,
        attempts=0,
        max_attempts=attempts_limit,
        next_attempt_at=now,
    )
    db.add(job)
    _finish_write(db, job, auto_commit=auto_commit)
    return job


def process_pending_knowledge_index_jobs(batch_size: int | None = None) -> dict[str, int]:
    db = SessionLocal()
    try:
        return process_knowledge_index_jobs(db, batch_size=batch_size)
    finally:
        db.close()


def process_knowledge_index_jobs(
    db: Session,
    *,
    batch_size: int | None = None,
) -> dict[str, int]:
    limit = max(1, batch_size or get_settings().knowledge_index_job_batch_size)
    jobs = _get_due_jobs(db, limit=limit, now=_utcnow())
    summary = {
        "processed": 0,
        "succeeded": 0,
        "failed": 0,
        "dead": 0,
        "skipped": 0,
    }
    for job in jobs:
        outcome = _process_one_job(db, job)
        summary["processed"] += 1
        summary[outcome] += 1
    return summary


def sync_knowledge_vector(
    db: Session,
    item: KnowledgeItem,
    *,
    auto_commit: bool = False,
    raise_on_failure: bool = True,
) -> KnowledgeItem:
    from app.services.knowledge_service import sync_knowledge_vector as sync_vector

    return sync_vector(
        db,
        item,
        auto_commit=auto_commit,
        raise_on_failure=raise_on_failure,
    )


def _get_due_jobs(
    db: Session,
    *,
    limit: int,
    now: datetime,
) -> list[KnowledgeIndexJob]:
    return (
        db.query(KnowledgeIndexJob)
        .filter(
            KnowledgeIndexJob.status.in_(_RETRYABLE_STATUSES),
            KnowledgeIndexJob.attempts < KnowledgeIndexJob.max_attempts,
            or_(
                KnowledgeIndexJob.next_attempt_at.is_(None),
                KnowledgeIndexJob.next_attempt_at <= now,
            ),
        )
        .order_by(KnowledgeIndexJob.created_at.asc(), KnowledgeIndexJob.id.asc())
        .limit(limit)
        .all()
    )


def _process_one_job(db: Session, job: KnowledgeIndexJob) -> str:
    _mark_processing(db, job)
    item = db.get(KnowledgeItem, int(job.knowledge_id))
    if item is None:
        _mark_skipped(db, job, "Knowledge item no longer exists")
        return "skipped"

    try:
        if job.operation != KNOWLEDGE_INDEX_OPERATION_UPSERT:
            raise ValueError(f"Unsupported knowledge index operation: {job.operation}")
        sync_knowledge_vector(
            db,
            item,
            auto_commit=False,
            raise_on_failure=True,
        )
        _mark_succeeded(db, job)
        return "succeeded"
    except Exception as exc:
        logger.warning(
            "Knowledge index job id=%s failed for item id=%s: %s",
            job.id,
            job.knowledge_id,
            exc,
        )
        status = _mark_failed_or_dead(db, job, exc)
        return "dead" if status == KNOWLEDGE_INDEX_JOB_STATUS_DEAD else "failed"


def _mark_processing(db: Session, job: KnowledgeIndexJob) -> None:
    now = _utcnow()
    job.status = KNOWLEDGE_INDEX_JOB_STATUS_PROCESSING
    job.attempts = int(job.attempts or 0) + 1
    job.locked_at = now
    job.started_at = job.started_at or now
    job.finished_at = None
    job.error_message = None
    db.add(job)
    db.commit()
    db.refresh(job)


def _mark_succeeded(db: Session, job: KnowledgeIndexJob) -> None:
    job.status = KNOWLEDGE_INDEX_JOB_STATUS_SUCCEEDED
    job.error_message = None
    job.finished_at = _utcnow()
    job.locked_at = None
    db.add(job)
    db.commit()
    db.refresh(job)


def _mark_skipped(db: Session, job: KnowledgeIndexJob, reason: str) -> None:
    job.status = KNOWLEDGE_INDEX_JOB_STATUS_SKIPPED
    job.error_message = clean_text(reason, max_length=1000)
    job.finished_at = _utcnow()
    job.locked_at = None
    db.add(job)
    db.commit()
    db.refresh(job)


def _mark_failed_or_dead(
    db: Session,
    job: KnowledgeIndexJob,
    exc: Exception,
) -> str:
    status = (
        KNOWLEDGE_INDEX_JOB_STATUS_DEAD
        if int(job.attempts or 0) >= int(job.max_attempts or 1)
        else KNOWLEDGE_INDEX_JOB_STATUS_FAILED
    )
    job.status = status
    job.error_message = _format_job_error(exc)
    job.finished_at = _utcnow() if status == KNOWLEDGE_INDEX_JOB_STATUS_DEAD else None
    job.locked_at = None
    job.next_attempt_at = _next_attempt_at(job)
    db.add(job)
    db.commit()
    db.refresh(job)
    return status


def _next_attempt_at(job: KnowledgeIndexJob) -> datetime | None:
    if job.status == KNOWLEDGE_INDEX_JOB_STATUS_DEAD:
        return None
    settings = get_settings()
    base_delay = max(1, settings.knowledge_index_job_retry_delay_seconds)
    delay_seconds = base_delay * max(1, int(job.attempts or 1))
    return _utcnow() + timedelta(seconds=delay_seconds)


def _format_job_error(exc: Exception) -> str:
    return clean_text(f"{type(exc).__name__}: {exc}", max_length=1000)


def _finish_write(
    db: Session,
    job: KnowledgeIndexJob,
    *,
    auto_commit: bool,
) -> None:
    if auto_commit:
        db.commit()
        db.refresh(job)
    else:
        db.flush()


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
