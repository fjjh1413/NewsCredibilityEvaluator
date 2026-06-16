"""APScheduler lifecycle management for the FastAPI application.

Registers scheduled news-crawl jobs on startup and shuts down gracefully.
If APScheduler is not installed or crawling is disabled, the module logs
a warning and becomes a no-op — the app still starts normally.
"""

import logging
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_scheduler: Any = None
"""Module-level reference to the active BackgroundScheduler, or None."""


def init_scheduler() -> None:
    """Register all enabled crawl jobs and start the background scheduler.

    Called from the FastAPI ``lifespan`` startup handler.
    """
    global _scheduler

    settings = get_settings()
    if not settings.crawl_enabled:
        logger.info("Scheduled crawling is disabled (CRAWL_ENABLED=false)")
        return

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.warning(
            "APScheduler is not installed; scheduled crawling disabled. "
            "Install with: pip install APScheduler"
        )
        return

    if not settings.bocha_api_key:
        logger.warning(
            "BOCHA_API_KEY is not configured; scheduled crawling disabled."
        )
        return

    # Group jobs by frequency to assign appropriate cron triggers.
    # We use the schedule from settings only; individual per-job frequencies
    # are derived from the default job list's freshness / expected cadence.
    cron_expression = settings.crawl_schedule

    scheduler = BackgroundScheduler(daemon=True)

    # Single unified job that runs all individual crawl jobs sequentially.
    # This is simpler than registering N separate APScheduler jobs and
    # avoids storming Bocha / target sites when all fire simultaneously.
    scheduler.add_job(
        func=_run_all_crawl_jobs,
        trigger=CronTrigger.from_crontab(cron_expression),
        id="crawl_all",
        name="定时抓取: 全部类别",
        replace_existing=True,
        misfire_grace_time=900,  # 15 min — tolerate brief downtime
    )

    scheduler.start()
    _scheduler = scheduler
    logger.info(
        "Crawl scheduler started (schedule=%s, jobs=%d default categories).",
        cron_expression,
        9,  # the 9 built-in categories
    )


def shutdown_scheduler() -> None:
    """Shut down the background scheduler gracefully.

    Called from the FastAPI ``lifespan`` shutdown handler.
    """
    global _scheduler

    if _scheduler is None:
        return

    try:
        _scheduler.shutdown(wait=False)
    except Exception as exc:
        logger.warning("Error shutting down crawl scheduler: %s", exc)
    finally:
        _scheduler = None
        logger.info("Crawl scheduler shut down.")


# ── internal ────────────────────────────────────────────────────────

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
        success_count = sum(1 for r in results if r.get("status") == "success")
        total_count = len(results)
        total_new = sum(r.get("new_added", 0) for r in results)
        logger.info(
            "Scheduled crawl completed: %d/%d jobs succeeded, %d new items added.",
            success_count,
            total_count,
            total_new,
        )
    except Exception:
        logger.exception("Scheduled crawl execution failed with an unexpected error.")
