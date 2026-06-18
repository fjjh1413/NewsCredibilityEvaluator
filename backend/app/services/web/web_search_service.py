"""Web search service for real-time evidence retrieval during detection.

Wraps the Bocha Web Search API to supplement local knowledge-base (Chroma) RAG
results when the knowledge base lacks sufficient coverage for a news topic.
"""

import logging
from typing import Any
from urllib.parse import urlparse, urlunparse

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
    """Build a candidate pool from RAG and web evidence sources.

    This function **only** normalises, performs strong‑identity dedup within
    each source, and applies per‑source limits.  It does **not** decide final
    ordering, relevance, or which evidence to use — those decisions are
    delegated to the LLM evidence‑arbitration step.

    Each candidate receives a ``candidate_id`` that is unique within this
    single call (per‑call unique, not cross‑call stable):

    * RAG: ``"kb:{knowledge_id}"`` when *knowledge_id* is a positive int,
      otherwise ``"kb:rag:{rag_idx}"`` (1‑based).
    * Web: ``"web:{web_idx}"`` (1‑based).

    Key invariants
    --------------
    * Input objects are never mutated — every output row is a fresh dict.
    * No ``rank_order`` is set on candidates; final ranking comes from LLM.
    * ``raw_rank_order`` records the original retrieval position for audit.
    * ``raw_similarity_score`` records the original retrieval score for audit.
    * Source type is used **only** to identify provenance and enforce
      configured per‑source candidate limits.  It is never used as a quality
      signal or final‑ranking factor.
    * Only **strong‑identity** duplicates are removed (same knowledge_id, same
      URL).  Candidates with merely similar titles are all preserved for LLM
      judgment.  No cross‑source dedup is performed.
    * The list order is not a quality or relevance signal — a source‑neutral
      input order is built later, before the LLM call.
    """
    # ── validate limits ──────────────────────────────────────────────
    if not isinstance(rag_limit, int) or isinstance(rag_limit, bool) or rag_limit < 0:
        raise ValueError("rag_limit must be a non‑negative integer")
    if not isinstance(web_limit, int) or isinstance(web_limit, bool) or web_limit < 0:
        raise ValueError("web_limit must be a non‑negative integer")

    # ══════════════════════════════════════════════════════════════════
    # Step 1 — normalise RAG items (no input mutation)
    # ══════════════════════════════════════════════════════════════════
    rag_normalized: list[dict[str, Any]] = []

    for rag_idx, item in enumerate(rag_evidence, start=1):
        knowledge_id = item.get("knowledge_id")
        raw_rank = item.get("rank_order")

        rag_normalized.append({
            "knowledge_id": knowledge_id,
            "title": clean_text(item.get("title"), max_length=255),
            "summary": clean_text(item.get("summary"), max_length=2000),
            "category": clean_text(item.get("category"), max_length=50),
            "truth_label": clean_text(item.get("truth_label"), max_length=30),
            "source_name": clean_text(item.get("source_name"), max_length=100),
            "source_url": item.get("source_url"),
            "risk_level": clean_text(item.get("risk_level"), max_length=30),
            "publish_time": item.get("publish_time"),
            "similarity_score": item.get("similarity_score"),
            "raw_similarity_score": item.get("similarity_score"),
            "raw_rank_order": (
                int(raw_rank)
                if _is_positive_int(raw_rank)
                else rag_idx
            ),
            "_orig_rag_idx": rag_idx,
        })

    # ══════════════════════════════════════════════════════════════════
    # Step 2 — strong‑identity dedup within RAG
    # ══════════════════════════════════════════════════════════════════
    rag_unique: list[dict[str, Any]] = []
    rag_seen_kids: set[int] = set()
    rag_seen_urls: set[str] = set()
    rag_seen_identities: set[tuple[str, str, str]] = set()

    for item in rag_normalized:
        kid = item["knowledge_id"]

        # 2a — dedup by valid knowledge_id
        if _is_positive_int(kid):
            if kid in rag_seen_kids:
                continue
            rag_seen_kids.add(kid)
            rag_unique.append(item)
            continue

        # 2b — dedup by non‑empty source_url
        url_key = _normalize_url(item.get("source_url"))
        if url_key:
            if url_key in rag_seen_urls:
                continue
            rag_seen_urls.add(url_key)
            rag_unique.append(item)
            continue

        # 2c — dedup by (title, source_name, publish_time) only when
        #      all three are non‑empty
        pub_str = _normalize_publish_time(item.get("publish_time"))
        title_lower = item["title"].lower()
        source_lower = item["source_name"].lower()
        if title_lower and source_lower and pub_str:
            identity = (title_lower, source_lower, pub_str)
            if identity in rag_seen_identities:
                continue
            rag_seen_identities.add(identity)
            rag_unique.append(item)
            continue

        # 2d — insufficient identity for dedup → keep
        rag_unique.append(item)

    # ── apply rag_limit ──
    rag_selected = rag_unique[:rag_limit]

    # ══════════════════════════════════════════════════════════════════
    # Step 3 — normalise Web items (no input mutation)
    # ══════════════════════════════════════════════════════════════════
    web_normalized: list[dict[str, Any]] = []

    for web_idx, web_item in enumerate(web_evidence, start=1):
        web_normalized.append({
            "knowledge_id": None,
            "title": clean_text(web_item.title, max_length=255),
            "summary": clean_text(web_item.summary, max_length=2000),
            "source_name": clean_text(web_item.site_name, max_length=100),
            "source_url": web_item.url or "",
            "publish_time": web_item.date_published,
            "similarity_score": web_item.similarity_score,
            "raw_similarity_score": web_item.similarity_score,
            "raw_rank_order": web_idx,
            "_orig_web_idx": web_idx,
        })

    # ══════════════════════════════════════════════════════════════════
    # Step 4 — strong‑identity dedup within Web
    # ══════════════════════════════════════════════════════════════════
    web_unique: list[dict[str, Any]] = []
    web_seen_urls: set[str] = set()
    web_seen_identities: set[tuple[str, str, str]] = set()

    for item in web_normalized:
        # 4a — dedup by non‑empty source_url
        url_key = _normalize_url(item.get("source_url"))
        if url_key:
            if url_key in web_seen_urls:
                continue
            web_seen_urls.add(url_key)
            web_unique.append(item)
            continue

        # 4b — dedup by (title, source_name, publish_time) only when
        #      all three are non‑empty
        pub_str = _normalize_publish_time(item.get("publish_time"))
        title_lower = item["title"].lower()
        source_lower = item["source_name"].lower()
        if title_lower and source_lower and pub_str:
            identity = (title_lower, source_lower, pub_str)
            if identity in web_seen_identities:
                continue
            web_seen_identities.add(identity)
            web_unique.append(item)
            continue

        # 4c — insufficient identity for dedup → keep
        web_unique.append(item)

    # ── apply web_limit ──
    web_selected = web_unique[:web_limit]

    # ══════════════════════════════════════════════════════════════════
    # Step 5 — assemble candidates with per‑call unique candidate_id
    # ══════════════════════════════════════════════════════════════════
    candidate_ids: set[str] = set()

    def _make_id(base_id: str) -> str:
        cid = base_id
        if cid in candidate_ids:
            suffix = 2
            while f"{base_id}:{suffix}" in candidate_ids:
                suffix += 1
            cid = f"{base_id}:{suffix}"
        candidate_ids.add(cid)
        return cid

    candidates: list[dict[str, Any]] = []

    for item in rag_selected:
        kid = item["knowledge_id"]
        base_id = f"kb:{kid}" if _is_positive_int(kid) else f"kb:rag:{item['_orig_rag_idx']}"

        candidates.append({
            "candidate_id": _make_id(base_id),
            "knowledge_id": int(kid) if _is_positive_int(kid) else None,
            "title": item["title"],
            "summary": item["summary"],
            "category": item["category"],
            "truth_label": item["truth_label"],
            "source_name": item["source_name"],
            "source_url": item["source_url"],
            "risk_level": item["risk_level"],
            "publish_time": item.get("publish_time"),
            "source_type": "knowledge_base",
            "source_label": "📚 知识库",
            "similarity_score": item["similarity_score"],
            "raw_similarity_score": item["raw_similarity_score"],
            "raw_rank_order": item["raw_rank_order"],
        })

    for item in web_selected:
        candidates.append({
            "candidate_id": _make_id(f"web:{item['_orig_web_idx']}"),
            "knowledge_id": None,
            "title": item["title"],
            "summary": item["summary"],
            "source_name": item["source_name"],
            "source_url": item["source_url"],
            "publish_time": item.get("publish_time"),
            "source_type": "web_search",
            "source_label": "🌐 网络检索",
            "similarity_score": item["similarity_score"],
            "raw_similarity_score": item["raw_similarity_score"],
            "raw_rank_order": item["raw_rank_order"],
        })

    return candidates


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _is_positive_int(value: Any) -> bool:
    """Return ``True`` when *value* is a non‑bool positive ``int``."""
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and value > 0
    )


def _normalize_url(value: Any) -> str:
    """Return a dedup‑safe URL key, or ``""`` when not usable as strong identity.

    * Only absolute URLs (scheme + netloc present) produce a non‑empty key.
    * Scheme and host are lowercased.
    * Fragment is removed.
    * Trailing ``/`` is stripped from the path only when path is not ``"/"``.
    * Path and query are preserved as‑is (not lowercased).
    * This function produces a **comparison key only** — the original
      ``source_url`` is never overwritten.
    """
    if not isinstance(value, str):
        return ""
    raw = value.strip()
    if not raw:
        return ""
    try:
        parsed = urlparse(raw)
    except (TypeError, ValueError):
        return ""
    if not parsed.scheme or not parsed.netloc:
        return ""
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return urlunparse((scheme, netloc, path, parsed.params, parsed.query, ""))


def _normalize_publish_time(value: Any) -> str:
    """Return *value* as a stable lowercased string for dedup comparison.

    Returns ``""`` when *value* is ``None`` or empty.  The original
    ``publish_time`` on the candidate is never overwritten.
    """
    if value is None:
        return ""
    text = str(value).strip()
    return text.lower()
