from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.crud import knowledge_crud
from app.models.knowledge_item import KnowledgeItem
from app.services.rag.contracts import RAG_INDEX_VERSION_V2, RagParentCandidate
from app.services.rag.vector_index import search_knowledge_chunk_vectors
from app.utils.text_cleaner import clean_text


DEFAULT_PARENT_TOP_K = 15
DEFAULT_CHUNKS_PER_PARENT = 2


def _safe_float(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(number, 1.0))


def _metadata_from_item(item: KnowledgeItem) -> dict[str, Any]:
    return {
        "knowledge_id": int(item.id),
        "title": clean_text(item.title, max_length=255),
        "summary": clean_text(item.summary, max_length=1000),
        "category": clean_text(item.category, max_length=50),
        "truth_label": clean_text(item.truth_label, max_length=30),
        "source_name": clean_text(item.source_name, max_length=100),
        "source_url": clean_text(item.source_url, max_length=500),
        "publish_time": clean_text(getattr(item, "publish_time", None), max_length=50),
        "risk_level": clean_text(item.risk_level, max_length=30),
        "vector_sync_status": clean_text(item.vector_sync_status, max_length=20),
        "index_version": RAG_INDEX_VERSION_V2,
    }


def _metadata_from_chunk_result(result: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(result.get("metadata") or {})
    metadata.setdefault("index_version", RAG_INDEX_VERSION_V2)
    metadata.setdefault("vector_sync_status", "synced")
    return metadata


def _tokenize_query(query_text: str) -> list[str]:
    cleaned = clean_text(query_text, max_length=500)
    if not cleaned:
        return []
    tokens = [
        token.strip().lower()
        for token in re.split(r"[\s,，。！？；;:：、|/\\()\[\]{}<>\"']+", cleaned)
        if len(token.strip()) >= 2
    ]
    if cleaned and cleaned.lower() not in tokens:
        tokens.insert(0, cleaned.lower()[:80])
    return tokens[:8]


def _score_item_lexically(item: KnowledgeItem, tokens: list[str]) -> tuple[float, float]:
    if not tokens:
        return 0.0, 0.0

    fields = {
        "title": clean_text(item.title, max_length=None).lower(),
        "summary": clean_text(item.summary, max_length=None).lower(),
        "keywords": clean_text(item.keywords, max_length=None).lower(),
        "content": clean_text(item.content, max_length=None).lower(),
    }
    weighted_hits = 0.0
    max_weight = 0.0
    exact_score = 0.0
    for token in tokens:
        token_weight = 0.0
        if token and token in fields["title"]:
            token_weight = max(token_weight, 1.0)
            exact_score = max(exact_score, 0.5)
        if token and token in fields["keywords"]:
            token_weight = max(token_weight, 0.8)
        if token and token in fields["summary"]:
            token_weight = max(token_weight, 0.6)
        if token and token in fields["content"]:
            token_weight = max(token_weight, 0.35)
        weighted_hits += token_weight
        max_weight += 1.0

    return (
        round(weighted_hits / max_weight, 6) if max_weight else 0.0,
        round(exact_score, 6),
    )


def _search_lexical_candidates(
    db: Session,
    query_text: str,
    limit: int,
    category: str | None = None,
    truth_label: str | None = None,
    risk_level: str | None = None,
) -> list[dict[str, Any]]:
    tokens = _tokenize_query(query_text)
    if not tokens:
        return []

    items = knowledge_crud.search_knowledge_items_for_retrieval(
        db,
        tokens=tokens,
        limit=limit,
        category=category,
        truth_label=truth_label,
        risk_level=risk_level,
    )

    candidates: list[dict[str, Any]] = []
    for item in items:
        lexical_score, exact_score = _score_item_lexically(item, tokens)
        if lexical_score <= 0 and exact_score <= 0:
            continue
        candidates.append(
            {
                "metadata": _metadata_from_item(item),
                "lexical_score": lexical_score,
                "exact_score": exact_score,
            }
        )

    candidates.sort(
        key=lambda item: (
            item["exact_score"],
            item["lexical_score"],
            item["metadata"].get("knowledge_id", 0),
        ),
        reverse=True,
    )
    return candidates[:limit]


def _candidate_for_metadata(
    candidates: dict[int, RagParentCandidate],
    metadata: dict[str, Any],
) -> RagParentCandidate | None:
    knowledge_id = metadata.get("knowledge_id")
    if knowledge_id is None:
        return None
    kid = int(knowledge_id)
    if kid not in candidates:
        candidates[kid] = RagParentCandidate(knowledge_id=kid, metadata=metadata)
    else:
        candidates[kid].metadata = {**metadata, **candidates[kid].metadata}
    return candidates[kid]


def _add_dense_results(
    candidates: dict[int, RagParentCandidate],
    dense_results: list[dict[str, Any]],
) -> None:
    for result in dense_results:
        metadata = _metadata_from_chunk_result(result)
        candidate = _candidate_for_metadata(candidates, metadata)
        if candidate is None:
            continue
        score = _safe_float(result.get("similarity_score"))
        candidate.dense_score = max(candidate.dense_score, score)
        candidate.chunks.append(
            {
                "chunk_id": result.get("chunk_id") or metadata.get("chunk_id"),
                "chunk_index": metadata.get("chunk_index"),
                "chunk_type": metadata.get("chunk_type"),
                "document": result.get("document") or "",
                "similarity_score": score,
            }
        )


def _add_lexical_results(
    candidates: dict[int, RagParentCandidate],
    lexical_results: list[dict[str, Any]],
) -> None:
    for result in lexical_results:
        metadata = dict(result.get("metadata") or {})
        candidate = _candidate_for_metadata(candidates, metadata)
        if candidate is None:
            continue
        candidate.lexical_score = max(
            candidate.lexical_score,
            _safe_float(result.get("lexical_score")),
        )
        candidate.exact_score = max(
            candidate.exact_score,
            _safe_float(result.get("exact_score")),
        )


def _finalize_candidates(
    candidates: dict[int, RagParentCandidate],
    chunks_per_parent: int,
) -> list[RagParentCandidate]:
    finalized: list[RagParentCandidate] = []
    for candidate in candidates.values():
        candidate.chunks.sort(
            key=lambda chunk: (
                _safe_float(chunk.get("similarity_score")),
                -int(chunk.get("chunk_index") or 0),
            ),
            reverse=True,
        )
        candidate.chunks = candidate.chunks[: max(1, chunks_per_parent)]
        candidate.final_score = round(
            min(
                1.0,
                candidate.dense_score * 0.70
                + candidate.lexical_score * 0.25
                + candidate.exact_score * 0.05,
            ),
            6,
        )
        if candidate.final_score > 0:
            finalized.append(candidate)
    return finalized


def _apply_mmr(
    candidates: list[RagParentCandidate],
    limit: int,
    enabled: bool,
) -> list[RagParentCandidate]:
    if not enabled:
        return sorted(candidates, key=lambda item: item.final_score, reverse=True)[:limit]

    remaining = sorted(candidates, key=lambda item: item.final_score, reverse=True)
    selected: list[RagParentCandidate] = []
    while remaining and len(selected) < limit:
        best_index = 0
        best_score = -1.0
        for index, candidate in enumerate(remaining):
            source_name = candidate.metadata.get("source_name") or ""
            source_penalty = sum(
                0.05
                for selected_candidate in selected
                if source_name
                and selected_candidate.metadata.get("source_name") == source_name
            )
            mmr_score = candidate.final_score - source_penalty
            if mmr_score > best_score:
                best_index = index
                best_score = mmr_score
        selected.append(remaining.pop(best_index))
    return selected


def search_similar_knowledge_v2(
    db: Session,
    query_text: str,
    top_k: int = 10,
    category: str | None = None,
    truth_label: str | None = None,
    risk_level: str | None = None,
) -> list[dict[str, Any]]:
    cleaned_query = clean_text(query_text, max_length=8000)
    if not cleaned_query:
        return []

    settings = get_settings()
    dense_results = search_knowledge_chunk_vectors(
        cleaned_query,
        top_n=settings.rag_dense_top_n,
        category=category,
        truth_label=truth_label,
        risk_level=risk_level,
    )
    lexical_results = (
        _search_lexical_candidates(
            db,
            cleaned_query,
            limit=settings.rag_parent_top_k,
            category=category,
            truth_label=truth_label,
            risk_level=risk_level,
        )
        if settings.rag_lexical_enabled
        else []
    )

    candidates: dict[int, RagParentCandidate] = {}
    _add_dense_results(candidates, dense_results)
    _add_lexical_results(candidates, lexical_results)
    finalized = _finalize_candidates(candidates, settings.rag_chunks_per_parent)
    selected = _apply_mmr(finalized, min(top_k, settings.rag_parent_top_k), settings.rag_mmr_enabled)
    return [candidate.to_result() for candidate in selected]
