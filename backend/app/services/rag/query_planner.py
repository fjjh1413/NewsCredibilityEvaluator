from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.utils.text_cleaner import clean_text


def _base_rag_query(title: str | None, content: str | None, max_length: int) -> str:
    title_text = clean_text(title, max_length=None)
    content_text = clean_text(content, max_length=None)
    parts: list[str] = []
    if title_text:
        parts.append(f"title: {title_text}")
    if content_text:
        parts.append(f"content: {content_text}")
    return clean_text("\n".join(parts), max_length=max_length)


def _claim_text(claim: Any) -> tuple[str, str]:
    if isinstance(claim, Mapping):
        claim_id = clean_text(claim.get("claim_id") or claim.get("id"), max_length=50)
        text = clean_text(
            claim.get("text") or claim.get("claim") or claim.get("content"),
            max_length=600,
        )
        return claim_id, text
    return "", clean_text(claim, max_length=600)


def build_claim_aware_queries(
    *,
    title: str | None,
    content: str | None,
    claims: Sequence[Any] | None = None,
    max_queries: int = 4,
    max_length: int = 8000,
) -> list[str]:
    """Build a bounded query plan: whole article first, then deduped claims."""
    safe_max_queries = max(1, int(max_queries or 1))
    queries: list[str] = []

    base_query = _base_rag_query(title, content, max_length=max_length)
    if base_query:
        queries.append(base_query)

    seen_claim_texts: set[str] = set()
    for claim in claims or []:
        if len(queries) >= safe_max_queries:
            break
        claim_id, text = _claim_text(claim)
        if not text:
            continue
        dedupe_key = text.casefold()
        if dedupe_key in seen_claim_texts:
            continue
        seen_claim_texts.add(dedupe_key)
        prefix = f"claim {claim_id}: " if claim_id else "claim: "
        query = clean_text(f"{prefix}{text}", max_length=min(max_length, 800))
        if query and query not in queries:
            queries.append(query)

    return queries[:safe_max_queries]
