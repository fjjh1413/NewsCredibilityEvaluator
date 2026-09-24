from __future__ import annotations

import copy
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from app.utils.text_cleaner import clean_text


ModelReranker = Callable[[str, list[dict[str, Any]]], list[dict[str, Any]]]


def _safe_float(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(number, 1.0))


def _safe_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, number)


def _metadata(result: Mapping[str, Any]) -> Mapping[str, Any]:
    metadata = result.get("metadata")
    return metadata if isinstance(metadata, Mapping) else {}


def _knowledge_id(result: Mapping[str, Any]) -> str:
    value = _metadata(result).get("knowledge_id")
    if value is None:
        value = result.get("knowledge_id")
    return clean_text(value, max_length=100)


def _source_name(result: Mapping[str, Any]) -> str:
    return clean_text(
        _metadata(result).get("source_name") or result.get("source_name"),
        max_length=200,
    ).casefold()


def _score_component(result: Mapping[str, Any], *keys: str) -> float:
    score_components = result.get("score_components")
    if not isinstance(score_components, Mapping):
        return 0.0
    for key in keys:
        value = _safe_float(score_components.get(key))
        if value > 0:
            return value
    return 0.0


def _supporting_span_count(result: Mapping[str, Any]) -> int:
    count = 0
    spans = result.get("supporting_spans")
    if isinstance(spans, list):
        count += len(spans)
    chunks = result.get("chunks")
    if isinstance(chunks, list):
        for chunk in chunks:
            if isinstance(chunk, Mapping) and isinstance(chunk.get("supporting_spans"), list):
                count += len(chunk["supporting_spans"])
    return count


def _rule_rerank_score(result: Mapping[str, Any]) -> float:
    similarity = _safe_float(result.get("raw_cosine_score", result.get("similarity_score")))
    fusion_score = (
        _safe_float(result["fusion_score"])
        if "fusion_score" in result
        else _score_component(result, "multi_query_rrf_score", "rrf_score", "final_score")
    )
    query_match_count = min(_safe_int(result.get("query_match_count")), 4)
    supporting_span_count = min(_supporting_span_count(result), 4)
    exact_score = _score_component(result, "exact_score")

    score = (
        similarity * 0.40
        + fusion_score * 0.30
        + (query_match_count / 4.0) * 0.15
        + (supporting_span_count / 4.0) * 0.10
        + exact_score * 0.05
    )
    return round(max(0.0, min(score, 1.0)), 6)


def _model_scores_by_id(
    query_text: str,
    candidates: list[dict[str, Any]],
    model_reranker: ModelReranker | None,
) -> dict[str, dict[str, Any]]:
    if model_reranker is None:
        return {}
    raw_scores = model_reranker(query_text, copy.deepcopy(candidates))
    scores: dict[str, dict[str, Any]] = {}
    for item in raw_scores:
        if not isinstance(item, Mapping):
            continue
        knowledge_id = clean_text(item.get("knowledge_id"), max_length=100)
        if not knowledge_id:
            candidate_id = clean_text(item.get("candidate_id"), max_length=100)
            knowledge_id = candidate_id.removeprefix("kb:") if candidate_id.startswith("kb:") else candidate_id
        if not knowledge_id:
            continue
        scores[knowledge_id] = {
            "score": _safe_float(item.get("score")),
            "reason": clean_text(item.get("reason"), max_length=500),
        }
    return scores


def rerank_parent_results(
    results: Sequence[Mapping[str, Any]],
    *,
    query_text: str,
    top_k: int,
    model_enabled: bool = False,
    model_reranker: ModelReranker | None = None,
    source_repeat_penalty: float = 0.08,
) -> list[dict[str, Any]]:
    """Apply deterministic rule reranking, then optional model reranking."""
    if top_k <= 0:
        return []

    candidates: list[dict[str, Any]] = []
    for original_rank, result in enumerate(results, start=1):
        candidate = copy.deepcopy(dict(result))
        rule_score = _rule_rerank_score(candidate)
        candidate["rerank_original_rank"] = original_rank
        candidate["rule_rerank_score"] = rule_score
        candidate["rerank_score"] = rule_score
        candidate["rerank_stage"] = "rule"
        candidates.append(candidate)

    if model_enabled:
        model_scores = _model_scores_by_id(query_text, candidates, model_reranker)
        for candidate in candidates:
            model_info = model_scores.get(_knowledge_id(candidate))
            if not model_info:
                continue
            model_score = model_info["score"]
            candidate["model_rerank_score"] = model_score
            if model_info.get("reason"):
                candidate["model_rerank_reason"] = model_info["reason"]
            candidate["rerank_score"] = round(
                candidate["rule_rerank_score"] * 0.35 + model_score * 0.65,
                6,
            )
            candidate["rerank_stage"] = "model"

    remaining = sorted(
        candidates,
        key=lambda item: (
            _safe_float(item.get("rerank_score")),
            _safe_float(item.get("similarity_score")),
        ),
        reverse=True,
    )
    selected: list[dict[str, Any]] = []
    seen_sources: dict[str, int] = {}
    while remaining and len(selected) < top_k:
        best_index = 0
        best_adjusted_score = -1.0
        for index, candidate in enumerate(remaining):
            source = _source_name(candidate)
            repeat_count = seen_sources.get(source, 0) if source else 0
            adjusted_score = _safe_float(candidate.get("rerank_score")) - repeat_count * source_repeat_penalty
            if adjusted_score > best_adjusted_score:
                best_index = index
                best_adjusted_score = adjusted_score
        candidate = remaining.pop(best_index)
        candidate["diversity_adjusted_rerank_score"] = round(
            max(0.0, best_adjusted_score),
            6,
        )
        source = _source_name(candidate)
        if source:
            seen_sources[source] = seen_sources.get(source, 0) + 1
        selected.append(candidate)

    for rank, candidate in enumerate(selected, start=1):
        candidate["rerank_order"] = rank
    return selected
