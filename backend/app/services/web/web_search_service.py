"""Web search service for real-time evidence retrieval during detection.

Wraps the Bocha Web Search API to supplement local knowledge-base (Chroma) RAG
results when the knowledge base lacks sufficient coverage for a news topic.
"""

import logging
from difflib import SequenceMatcher
from typing import Any

from app.services.web.bocha_client import BochaClient, BochaServiceError
from app.schemas.web_search import WebEvidenceItem, WebSearchMeta
from app.utils.text_cleaner import clean_text

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# RAG quality thresholds — control when web search is triggered
# ---------------------------------------------------------------------------
RAG_TOP1_THRESHOLD = 0.45          # top-1 similarity below this → always trigger
RAG_TOP1_MODERATE = 0.60           # top-1 below this + few meaningful results → trigger
RAG_MIN_MEANINGFUL_RESULTS = 3     # count only results with similarity >= this threshold
RAG_MIN_SIMILARITY = 0.30          # below this, a result is not considered meaningful

# ---------------------------------------------------------------------------
# evidence merge limits
# ---------------------------------------------------------------------------
DEFAULT_WEB_COUNT = 5
DEFAULT_RAG_LIMIT = 5
DEFAULT_WEB_LIMIT = 5
DEDUP_TITLE_THRESHOLD = 0.75      # SequenceMatcher ratio above this → duplicate

# ---------------------------------------------------------------------------
# web search query building
# ---------------------------------------------------------------------------

def build_search_query(title: str, keywords: list[str]) -> str:
    """Build a search-engine query from news title and extracted keywords.

    Uses the title as the primary signal with up to 3 keywords appended for
    precision.  This is intentionally rule-based (no extra LLM call).
    """
    title_text = clean_text(title, max_length=100)
    if not title_text:
        return " ".join(keywords[:5]) if keywords else ""

    key_terms = [clean_text(k, max_length=20) for k in keywords[:3]]
    key_terms = [k for k in key_terms if k]
    if key_terms:
        return f"{title_text} {' '.join(key_terms)}"
    return title_text


# ---------------------------------------------------------------------------
# RAG quality evaluation
# ---------------------------------------------------------------------------

def should_trigger_web_search(
    rag_evidence: list[dict[str, Any]],
    enable_web_search: bool,
) -> bool:
    """Decide whether to supplement RAG results with web search.

    Returns ``True`` only when *enable_web_search* is enabled **and** the
    existing RAG evidence looks insufficient.
    """
    if not enable_web_search:
        return False

    if not rag_evidence:
        logger.info("Web search triggered: no RAG evidence found")
        return True

    top1_score = _safe_float(rag_evidence[0].get("similarity_score"))
    # Count only results with meaningful similarity — ignore noise below MIN_SIMILARITY
    meaningful = [
        e for e in rag_evidence
        if _safe_float(e.get("similarity_score")) >= RAG_MIN_SIMILARITY
    ]
    meaningful_count = len(meaningful)

    if top1_score < RAG_TOP1_THRESHOLD:
        logger.info(
            "Web search triggered: top-1 similarity %.2f < %.2f",
            top1_score,
            RAG_TOP1_THRESHOLD,
        )
        return True

    if top1_score < RAG_TOP1_MODERATE and meaningful_count < RAG_MIN_MEANINGFUL_RESULTS:
        logger.info(
            "Web search triggered: top-1 similarity %.2f < %.2f and only %d meaningful RAG results (< %d)",
            top1_score,
            RAG_TOP1_MODERATE,
            meaningful_count,
            RAG_MIN_MEANINGFUL_RESULTS,
        )
        return True

    return False


# ---------------------------------------------------------------------------
# web search execution
# ---------------------------------------------------------------------------

def search_evidence(
    client: BochaClient,
    title: str,
    keywords: list[str],
    count: int = DEFAULT_WEB_COUNT,
    freshness: str = "oneMonth",
) -> list[WebEvidenceItem]:
    """Execute a Bocha web search and return normalized evidence items."""
    query = build_search_query(title, keywords)
    if not query:
        return []

    try:
        response = client.search(query=query, freshness=freshness, count=count, summary=True)
    except BochaServiceError as exc:
        logger.warning("Bocha web search failed for query %r: %s", query, exc)
        return []

    webpages = response.get("webpages") or []
    items: list[WebEvidenceItem] = []
    for page in webpages:
        if not isinstance(page, dict):
            continue
        snippet = clean_text(
            page.get("summary") or page.get("snippet"), max_length=2000
        )
        if not snippet:
            continue

        items.append(
            WebEvidenceItem(
                title=clean_text(page.get("name") or page.get("title"), max_length=255),
                url=clean_text(page.get("url"), max_length=500),
                summary=snippet,
                site_name=clean_text(page.get("site_name"), max_length=100),
                date_published=clean_text(page.get("date_published"), max_length=30),
                similarity_score=_safe_float(page.get("score")),
                source_type="web_search",
                source_label="🌐 网络检索",
                rank_order=0,
            )
        )
    return items[:count]


# ---------------------------------------------------------------------------
# evidence merging
# ---------------------------------------------------------------------------

def merge_evidence(
    rag_evidence: list[dict[str, Any]],
    web_evidence: list[WebEvidenceItem],
    rag_limit: int = DEFAULT_RAG_LIMIT,
    web_limit: int = DEFAULT_WEB_LIMIT,
) -> list[dict[str, Any]]:
    """Merge RAG and web evidence, deduplicating by title similarity.

    RAG results are placed first (higher trust from curated knowledge base).
    """
    merged: list[dict[str, Any]] = []

    # RAG evidence first
    for item in rag_evidence[:rag_limit]:
        item["source_type"] = item.get("source_type", "knowledge_base")
        item["source_label"] = item.get("source_label", "📚 知识库")
        merged.append(item)

    # web evidence appended with dedup
    rag_titles = [
        clean_text(item.get("title"), max_length=255).lower()
        for item in rag_evidence[:rag_limit]
    ]
    added = 0
    for web_item in web_evidence:
        if added >= web_limit:
            break
        if _is_duplicate_title(web_item.title, rag_titles):
            continue
        merged.append({
            "title": web_item.title,
            "summary": web_item.summary,
            "source_name": web_item.site_name,
            "source_url": web_item.url,
            "publish_time": web_item.date_published,
            "similarity_score": web_item.similarity_score,
            "source_type": web_item.source_type,
            "source_label": web_item.source_label,
            "knowledge_id": None,
        })
        rag_titles.append(clean_text(web_item.title, max_length=255).lower())
        added += 1

    # re-assign rank_order
    for idx, item in enumerate(merged, start=1):
        item["rank_order"] = idx

    return merged


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _is_duplicate_title(title: str, existing_titles: list[str]) -> bool:
    """Check whether *title* is too similar to any title already present."""
    if not title:
        return True
    lower = title.lower()
    for existing in existing_titles:
        if not existing:
            continue
        if lower == existing:
            return True
        if SequenceMatcher(None, lower, existing).ratio() > DEDUP_TITLE_THRESHOLD:
            return True
    return False
