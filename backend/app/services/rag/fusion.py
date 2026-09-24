from __future__ import annotations

import copy
import math
from typing import Any, Mapping, Sequence

from app.utils.text_cleaner import clean_text


DEFAULT_RRF_RANK_CONSTANT = 60
DEFAULT_SIGNAL_WEIGHTS = {
    "dense": 0.70,
    "lexical": 0.25,
    "exact": 0.05,
}


def _safe_float(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(number, 1.0))


def _safe_rank(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        rank = int(value)
    except (TypeError, ValueError):
        return None
    return rank if rank > 0 else None


def _safe_rank_constant(value: int) -> int:
    try:
        rank_constant = int(value)
    except (TypeError, ValueError):
        return DEFAULT_RRF_RANK_CONSTANT
    return rank_constant if rank_constant > 0 else DEFAULT_RRF_RANK_CONSTANT


def normalized_rrf_score(
    ranks: Mapping[str, int | None],
    *,
    weights: Mapping[str, float] | None = None,
    rank_constant: int = DEFAULT_RRF_RANK_CONSTANT,
    exact_score: float = 0.0,
) -> float:
    """Return a bounded rank-fusion score, not a calibrated cosine similarity."""
    rank_constant = _safe_rank_constant(rank_constant)
    signal_weights = dict(DEFAULT_SIGNAL_WEIGHTS)
    if weights is not None:
        signal_weights.update(weights)

    top_rank_unit = 1.0 / (rank_constant + 1)
    score = 0.0
    for signal, weight in signal_weights.items():
        if signal == "exact":
            continue
        rank = _safe_rank(ranks.get(signal))
        if rank is None or weight <= 0:
            continue
        score += float(weight) * ((1.0 / (rank_constant + rank)) / top_rank_unit)

    score += max(0.0, float(signal_weights.get("exact", 0.0))) * _safe_float(
        exact_score
    )
    return round(max(0.0, min(score, 1.0)), 6)


def _result_parent_key(result: Mapping[str, Any]) -> str | None:
    metadata = result.get("metadata") or {}
    knowledge_id = metadata.get("knowledge_id")
    if knowledge_id is not None and not isinstance(knowledge_id, bool):
        return f"knowledge:{knowledge_id}"
    vector_id = clean_text(result.get("vector_id"), max_length=200)
    return vector_id or None


def _chunk_key(chunk: Mapping[str, Any]) -> str:
    return clean_text(chunk.get("chunk_id"), max_length=200) or clean_text(
        chunk.get("document"),
        max_length=500,
    )


def _merge_chunks(
    existing: Sequence[Mapping[str, Any]],
    incoming: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for chunk in [*existing, *incoming]:
        if not isinstance(chunk, Mapping):
            continue
        key = _chunk_key(chunk)
        if not key:
            continue
        current = merged.get(key)
        candidate = copy.deepcopy(dict(chunk))
        if current is None or _safe_float(candidate.get("similarity_score")) > _safe_float(
            current.get("similarity_score")
        ):
            merged[key] = candidate
    return sorted(
        merged.values(),
        key=lambda item: _safe_float(item.get("similarity_score")),
        reverse=True,
    )


def _merge_score_components(
    existing: Mapping[str, Any],
    incoming: Mapping[str, Any],
) -> dict[str, Any]:
    merged = copy.deepcopy(dict(existing))
    for key, value in incoming.items():
        if key.endswith("_score") and isinstance(value, (int, float)):
            merged[key] = max(_safe_float(merged.get(key)), _safe_float(value))
        else:
            merged.setdefault(key, value)
    return merged


def _query_rrf_score(
    ranks: Sequence[int],
    *,
    query_count: int,
    rank_constant: int,
) -> float:
    if not ranks or query_count <= 0:
        return 0.0
    rank_constant = _safe_rank_constant(rank_constant)
    top_rank_unit = 1.0 / (rank_constant + 1)
    score = sum((1.0 / (rank_constant + rank)) / top_rank_unit for rank in ranks)
    return round(max(0.0, min(score / query_count, 1.0)), 6)


def fuse_ranked_parent_results(
    ranked_result_sets: Sequence[Sequence[Mapping[str, Any]]],
    *,
    top_k: int,
    rank_constant: int = DEFAULT_RRF_RANK_CONSTANT,
    query_texts: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    """Fuse per-query parent-document result lists by normalized RRF."""
    if top_k <= 0:
        return []

    query_count = len(ranked_result_sets)
    candidates: dict[str, dict[str, Any]] = {}
    for query_index, ranked_results in enumerate(ranked_result_sets):
        for rank, result in enumerate(ranked_results, start=1):
            if not isinstance(result, Mapping):
                continue
            key = _result_parent_key(result)
            if key is None:
                continue

            result_copy = copy.deepcopy(dict(result))
            hit = {
                "query_index": query_index,
                "rank": rank,
                "score": _safe_float(result_copy.get("similarity_score")),
            }
            if query_texts and query_index < len(query_texts):
                hit["query"] = clean_text(query_texts[query_index], max_length=300)

            if key not in candidates:
                result_copy["query_hits"] = [hit]
                candidates[key] = result_copy
                continue

            existing = candidates[key]
            existing["query_hits"].append(hit)
            similarity_scores = [
                _safe_float(item["similarity_score"])
                for item in (existing, result_copy)
                if item.get("similarity_score") is not None
            ]
            existing["similarity_score"] = max(similarity_scores) if similarity_scores else None
            cosine_scores = [
                item.get("raw_cosine_score")
                for item in (existing, result_copy)
                if isinstance(item.get("raw_cosine_score"), (int, float))
                and math.isfinite(item["raw_cosine_score"])
            ]
            if cosine_scores:
                existing["raw_cosine_score"] = max(cosine_scores)
            existing["chunks"] = _merge_chunks(
                existing.get("chunks") or [],
                result_copy.get("chunks") or [],
            )
            existing["score_components"] = _merge_score_components(
                existing.get("score_components") or {},
                result_copy.get("score_components") or {},
            )
            existing["metadata"] = {
                **(result_copy.get("metadata") or {}),
                **(existing.get("metadata") or {}),
            }

    fused: list[dict[str, Any]] = []
    for candidate in candidates.values():
        ranks = [int(hit["rank"]) for hit in candidate.get("query_hits", [])]
        multi_query_score = _query_rrf_score(
            ranks,
            query_count=query_count,
            rank_constant=rank_constant,
        )
        candidate["query_match_count"] = len(ranks)
        candidate["multi_query_rrf_score"] = multi_query_score
        # Preserve dense similarity for absolute thresholds; fusion only ranks.
        candidate["fusion_score"] = multi_query_score
        score_components = dict(candidate.get("score_components") or {})
        score_components["multi_query_rrf_score"] = multi_query_score
        score_components["query_match_count"] = len(ranks)
        candidate["score_components"] = score_components
        if query_texts:
            candidate["retrieval_queries"] = [
                clean_text(query_texts[hit["query_index"]], max_length=300)
                for hit in candidate.get("query_hits", [])
                if hit["query_index"] < len(query_texts)
            ]
        fused.append(candidate)

    fused.sort(
        key=lambda item: (
            _safe_float(item.get("multi_query_rrf_score")),
            _safe_float(item.get("similarity_score")),
        ),
        reverse=True,
    )
    return fused[:top_k]
