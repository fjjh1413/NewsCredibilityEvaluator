"""Scheduled news crawling — periodically search Bocha AI and ingest results
into the knowledge base.

Each *crawl job* defines a search query, freshness window, category mapping,
and maximum result count.  Jobs are executed by the APScheduler-backed
``core.scheduler`` module.
"""

import logging
import re
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Any

from app.db.session import SessionLocal
from app.models.crawl_task import CrawlTask
from app.models.knowledge_item import KnowledgeItem
from app.services.knowledge_service import (
    _mark_vector_failed,
)
from app.services.knowledge_index_jobs import enqueue_knowledge_index_job
from app.services.web.bocha_client import BochaClient, BochaServiceError
from app.services.web.web_content_fetcher import WebContentFetcher, WebContentFetchError
from app.utils.text_cleaner import clean_text

logger = logging.getLogger(__name__)

DEDUP_TITLE_RATIO = 0.75      # titles above this SequenceMatcher ratio → duplicate
DEDUP_LOOKBACK_DAYS = 7       # only check recent items for title dedup
MAX_FETCH_CONCURRENCY = 3     # max parallel full-text fetches per job


class CrawlJobConfig:
    """Immutable configuration for a single scheduled crawl job."""

    def __init__(
        self,
        name: str,
        query: str,
        freshness: str,
        count: int = 10,
        category: str = "未分类",
        enabled: bool = True,
    ) -> None:
        self.name = name
        self.query = query
        self.freshness = freshness
        self.count = max(1, min(count, 50))
        self.category = category or "未分类"
        self.enabled = enabled


# ── default crawl jobs ──────────────────────────────────────────────

DEFAULT_CRAWL_JOBS: list[CrawlJobConfig] = [
    CrawlJobConfig(
        name="社会热点辟谣",
        query="最新社会热点事件 官方通报 辟谣",
        freshness="oneDay",
        count=10,
        category="社会",
    ),
    CrawlJobConfig(
        name="AI行业动态",
        query="人工智能 AI 最新进展 政策 监管",
        freshness="oneDay",
        count=10,
        category="AI",
    ),
    CrawlJobConfig(
        name="科技行业动态",
        query="科技行业 最新新闻 数据安全 隐私",
        freshness="oneDay",
        count=10,
        category="科技",
    ),
    CrawlJobConfig(
        name="财经新闻",
        query="财经新闻 经济政策 金融监管",
        freshness="oneDay",
        count=10,
        category="财经",
    ),
    CrawlJobConfig(
        name="医疗健康辟谣",
        query="医疗健康 辟谣 官方回应 不实信息",
        freshness="oneWeek",
        count=10,
        category="健康",
    ),
    CrawlJobConfig(
        name="教育政策",
        query="教育政策 改革 官方发布",
        freshness="oneWeek",
        count=10,
        category="教育",
    ),
    CrawlJobConfig(
        name="国际新闻核查",
        query="国际新闻 事实核查 虚假信息",
        freshness="oneDay",
        count=10,
        category="国际",
    ),
    CrawlJobConfig(
        name="娱乐辟谣",
        query="娱乐新闻 辟谣 明星 虚假",
        freshness="oneDay",
        count=10,
        category="娱乐",
    ),
    CrawlJobConfig(
        name="体育赛事新闻",
        query="体育赛事 新闻 官方声明",
        freshness="oneWeek",
        count=10,
        category="体育",
    ),
]


def _get_default_crawl_jobs() -> list[CrawlJobConfig]:
    """Return the built-in crawl job list.

    In the future this could be overridden via ``CRAWL_JOBS_JSON`` env var
    or loaded from the database.
    """
    return DEFAULT_CRAWL_JOBS


# ── main entry point called by the scheduler ────────────────────────

def execute_all_crawl_jobs(
    bocha_api_key: str,
    bocha_timeout: float,
    fetch_timeout: float,
    fetch_max_bytes: int,
    allow_private_hosts: bool,
    auto_sync_vector: bool,
    concurrent_fetches: int = MAX_FETCH_CONCURRENCY,
) -> list[dict[str, Any]]:
    """Run every enabled crawl job and return a summary for each."""
    jobs = _get_default_crawl_jobs()
    bocha_client = BochaClient(api_key=bocha_api_key, timeout=bocha_timeout)
    fetcher = WebContentFetcher(
        timeout=fetch_timeout,
        max_bytes=fetch_max_bytes,
        allow_private_hosts=allow_private_hosts,
    )
    results: list[dict[str, Any]] = []
    for job in jobs:
        if not job.enabled:
            continue
        try:
            summary = _execute_single_job(
                job=job,
                bocha_client=bocha_client,
                fetcher=fetcher,
                auto_sync_vector=auto_sync_vector,
                concurrent_fetches=concurrent_fetches,
            )
        except Exception as exc:
            logger.exception("Crawl job %r failed unexpectedly", job.name)
            summary = {
                "job_name": job.name,
                "status": "failed",
                "total_found": 0,
                "new_added": 0,
                "duplicates": 0,
                "fetch_failed": 0,
                "error": f"{type(exc).__name__}: {exc}",
            }
        results.append(summary)
    return results


# ── single job execution ────────────────────────────────────────────

def _execute_single_job(
    job: CrawlJobConfig,
    bocha_client: BochaClient,
    fetcher: WebContentFetcher,
    auto_sync_vector: bool,
    concurrent_fetches: int,
) -> dict[str, Any]:
    started_at = datetime.now()
    status = "success"

    # 1. Search Bocha
    try:
        response = bocha_client.search(
            query=job.query,
            freshness=job.freshness,
            count=job.count,
            summary=True,
        )
    except BochaServiceError as exc:
        logger.error("Crawl job %r Bocha search failed: %s", job.name, exc)
        return _save_log(
            job_name=job.name,
            search_query=job.query,
            freshness=job.freshness,
            started_at=started_at,
            total_found=0,
            new_added=0,
            duplicates=0,
            fetch_failed=0,
            errors=str(exc),
            status="failed",
        )

    webpages = response.get("webpages") or []
    total_found = len(webpages)
    if not webpages:
        return _save_log(
            job_name=job.name,
            search_query=job.query,
            freshness=job.freshness,
            started_at=started_at,
            total_found=0,
            new_added=0,
            duplicates=0,
            fetch_failed=0,
            status="success",
        )

    # 2. Dedup against knowledge base
    db = SessionLocal()
    try:
        deduped = _deduplicate(db, webpages)
    finally:
        db.close()

    duplicates = total_found - len(deduped)
    if not deduped:
        return _save_log(
            job_name=job.name,
            search_query=job.query,
            freshness=job.freshness,
            started_at=started_at,
            total_found=total_found,
            new_added=0,
            duplicates=duplicates,
            fetch_failed=0,
            status="success",
        )

    # 3. Fetch full content (parallel, bounded concurrency)
    enriched = _fetch_content_parallel(
        deduped,
        fetcher=fetcher,
        max_workers=concurrent_fetches,
    )
    fetch_failed = sum(1 for item in enriched if not item.get("full_content"))

    # 4. Create knowledge items + vectorize
    new_added = 0
    db = SessionLocal()
    try:
        for item in enriched:
            try:
                _create_knowledge_from_crawl(
                    db=db,
                    item=item,
                    job=job,
                    auto_sync_vector=auto_sync_vector,
                )
                new_added += 1
            except Exception as exc:
                logger.warning(
                    "Failed to create knowledge item from crawl: url=%s error=%s",
                    item.get("url"),
                    exc,
                )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Batch knowledge creation failed for job %r", job.name)
        status = "failed"
    finally:
        db.close()

    if fetch_failed > 0 and status == "success":
        status = "partial"

    return _save_log(
        job_name=job.name,
        search_query=job.query,
        freshness=job.freshness,
        started_at=started_at,
        total_found=total_found,
        new_added=new_added,
        duplicates=duplicates,
        fetch_failed=fetch_failed,
        status=status,
    )


# ── dedup ───────────────────────────────────────────────────────────

def _deduplicate(
    db: Any,
    webpages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Filter out webpages already present in the knowledge base."""
    lookback = datetime.now() - timedelta(days=DEDUP_LOOKBACK_DAYS)
    recent = (
        db.query(KnowledgeItem)
        .filter(KnowledgeItem.created_at >= lookback)
        .all()
    )
    existing_urls = {item.source_url for item in recent if item.source_url}
    existing_titles = [
        clean_text(item.title, max_length=255).lower()
        for item in recent
        if item.title
    ]

    unique: list[dict[str, Any]] = []
    for page in webpages:
        url = clean_text(page.get("url"), max_length=500)
        title = clean_text(page.get("name") or page.get("title"), max_length=255)

        # URL exact match
        if url and url in existing_urls:
            continue

        # title fuzzy match
        if _is_title_duplicate(title, existing_titles):
            continue

        unique.append(page)
        if url:
            existing_urls.add(url)
        if title:
            existing_titles.append(title.lower())

    return unique


def _is_title_duplicate(title: str, existing: list[str]) -> bool:
    if not title:
        return True
    lower = title.lower()
    for ex in existing:
        if lower == ex:
            return True
        if SequenceMatcher(None, lower, ex).ratio() > DEDUP_TITLE_RATIO:
            return True
    return False


# ── full-text fetch ─────────────────────────────────────────────────

def _fetch_content_parallel(
    webpages: list[dict[str, Any]],
    fetcher: WebContentFetcher,
    max_workers: int = MAX_FETCH_CONCURRENCY,
) -> list[dict[str, Any]]:
    """Fetch full article content for each webpage in parallel.

    When a fetch fails, the item still proceeds using the Bocha snippet as
    its content so the knowledge base keeps growing.
    """
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_map: dict[Future[str], int] = {}
        for idx, page in enumerate(webpages):
            url = clean_text(page.get("url"), max_length=500)
            if url:
                future_map[pool.submit(fetcher.fetch, url)] = idx
            # immediately fill with snippet as fallback
            results.append({**page, "full_content": ""})

        for future in as_completed(future_map):
            idx = future_map[future]
            try:
                full_text = future.result()
                if full_text:
                    results[idx]["full_content"] = full_text
            except (WebContentFetchError, Exception) as exc:
                logger.debug("Full-content fetch skipped for %s: %s", webpages[idx].get("url"), exc)

    return results


# ── knowledge item creation ─────────────────────────────────────────

def _create_knowledge_from_crawl(
    db: Any,
    item: dict[str, Any],
    job: CrawlJobConfig,
    auto_sync_vector: bool,
) -> KnowledgeItem:
    """Create a single KnowledgeItem from a crawl result and optionally vectorize."""
    title = clean_text(item.get("name") or item.get("title"), max_length=255)
    full_content = clean_text(item.get("full_content"), max_length=8000)
    snippet = clean_text(item.get("summary") or item.get("snippet"), max_length=2000)
    url = clean_text(item.get("url"), max_length=500)
    site_name = clean_text(item.get("site_name"), max_length=100)
    date_published = clean_text(item.get("date_published"), max_length=30)

    # Use full_content if available, otherwise fall back to snippet
    content = full_content or snippet or title
    summary = snippet or full_content[:500] if full_content else title
    admin_note = (
        f"[自动导入] 来源:{job.name} 抓取时间:{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    if not full_content:
        admin_note += " [全文抓取失败，使用搜索摘要]"

    db_item = KnowledgeItem(
        title=title,
        content=content,
        category=job.category,
        truth_label="待核查",
        source_name=site_name or "未知来源",
        source_url=url,
        summary=summary,
        keywords="",
        debunking_explanation="",
        risk_level="存疑信息",
        admin_note=admin_note,
        vector_sync_status="pending",
        vector_sync_error=None,
    )
    db.add(db_item)
    db.flush()

    if auto_sync_vector:
        try:
            enqueue_knowledge_index_job(
                db,
                db_item,
                source=f"crawl:{job.name}",
                auto_commit=False,
            )
        except Exception as exc:
            logger.warning(
                "Crawl knowledge index job enqueue failed for id=%s: %s",
                db_item.id,
                exc,
            )
            _mark_vector_failed(db, db_item, exc, auto_commit=False)

    return db_item


# ── logging ─────────────────────────────────────────────────────────

def _save_log(
    job_name: str,
    search_query: str,
    freshness: str,
    started_at: datetime,
    total_found: int,
    new_added: int,
    duplicates: int,
    fetch_failed: int = 0,
    errors: str = "",
    status: str = "success",
) -> dict[str, Any]:
    """Persist a CrawlTask log row and return a summary dict."""
    try:
        db = SessionLocal()
        try:
            log_entry = CrawlTask(
                job_name=job_name,
                search_query=search_query,
                freshness=freshness,
                total_found=total_found,
                new_added=new_added,
                duplicates=duplicates,
                fetch_failed=fetch_failed,
                errors=errors[:2000] if errors else None,
                started_at=started_at,
                finished_at=datetime.now(),
                status=status,
            )
            db.add(log_entry)
            db.commit()
        finally:
            db.close()
    except Exception as exc:
        logger.warning("Failed to persist CrawlTask log: %s", exc)

    return {
        "job_name": job_name,
        "status": status,
        "total_found": total_found,
        "new_added": new_added,
        "duplicates": duplicates,
        "fetch_failed": fetch_failed,
        "error": errors[:500] if errors else "",
    }
