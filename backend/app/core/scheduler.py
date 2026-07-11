"""APScheduler lifecycle management for background jobs."""

import logging
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_scheduler: Any = None
"""Module-level reference to the active BackgroundScheduler, or None."""


def init_scheduler() -> None:
    """Register enabled background jobs and start the scheduler."""
    global _scheduler

    settings = get_settings()
    if not settings.crawl_enabled and not settings.knowledge_index_job_enabled:
        logger.info("Scheduler is disabled")
        return

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
        from apscheduler.triggers.interval import IntervalTrigger
    except ImportError:
        logger.warning(
            "APScheduler is not installed; scheduled jobs disabled. "
            "Install with: pip install APScheduler"
        )
        return

    scheduler = BackgroundScheduler(daemon=True)
    cron_expression = settings.crawl_schedule

    if settings.crawl_enabled and settings.bocha_api_key:
        scheduler.add_job(
            func=_run_all_crawl_jobs,
            trigger=CronTrigger.from_crontab(cron_expression),
            id="crawl_all",
            name="scheduled crawl: all categories",
            replace_existing=True,
            misfire_grace_time=900,
        )
    elif settings.crawl_enabled:
        logger.warning(
            "BOCHA_API_KEY is not configured; scheduled crawling disabled, "
            "knowledge index jobs may still run."
        )

    if settings.knowledge_index_job_enabled:
        scheduler.add_job(
            func=_run_knowledge_index_jobs,
            trigger=IntervalTrigger(
                seconds=settings.knowledge_index_job_interval_seconds,
            ),
            id="knowledge_index_jobs",
            name="knowledge index job worker",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300,
        )

    if not scheduler.get_jobs():
        logger.info("No scheduled jobs registered")
        return

    scheduler.start()
    _scheduler = scheduler
    logger.info(
        "Scheduler started (crawl_schedule=%s, registered_jobs=%d).",
        cron_expression,
        len(scheduler.get_jobs()),
    )


def shutdown_scheduler() -> None:
    """Shut down the background scheduler gracefully."""
    global _scheduler

    if _scheduler is None:
        return

    try:
        _scheduler.shutdown(wait=False)
    except Exception as exc:
        logger.warning("Error shutting down scheduler: %s", exc)
    finally:
        _scheduler = None
        logger.info("Scheduler shut down.")


def _run_all_crawl_jobs() -> None:
    """Execute all enabled crawl jobs inside the scheduler thread."""
    from app.services.web.news_crawler import execute_all_crawl_jobs

    settings = get_settings()

    try:
        results = execute_all_crawl_jobs(
            bocha_api_key=settings.bocha_api_key,
            bocha_timeout=settings.web_search_timeout_seconds,
            fetch_timeout=settings.crawl_fetch_timeout_seconds,
            fetch_max_bytes=settings.crawl_fetch_max_bytes,
            allow_private_hosts=settings.crawl_allow_private_hosts,
            auto_sync_vector=settings.crawl_auto_sync_vector,
            concurrent_fetches=settings.crawl_concurrent_fetches,
        )
        success_count = sum(1 for result in results if result.get("status") == "success")
        total_count = len(results)
        total_new = sum(result.get("new_added", 0) for result in results)
        logger.info(
            "Scheduled crawl completed: %d/%d jobs succeeded, %d new items added.",
            success_count,
            total_count,
            total_new,
        )
    except Exception:
        logger.exception("Scheduled crawl execution failed with an unexpected error.")


def _run_knowledge_index_jobs() -> None:
    """Process queued knowledge index jobs inside the scheduler thread."""
    from app.services.knowledge_index_jobs import process_pending_knowledge_index_jobs

    settings = get_settings()

    try:
        summary = process_pending_knowledge_index_jobs(
            batch_size=settings.knowledge_index_job_batch_size,
        )
        if summary["processed"]:
            logger.info("Knowledge index jobs processed: %s", summary)
    except Exception:
        logger.exception("Knowledge index job worker failed with an unexpected error.")
