from __future__ import annotations

import copy
import re
from collections.abc import Mapping, Sequence
from typing import Any

from app.utils.text_cleaner import clean_text


TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]{2,}|[\u4e00-\u9fff]{2,8}")
QUERY_LABEL_STOPWORDS = {
    "title",
    "content",
    "claim",
}


def _query_terms(query_texts: Sequence[str]) -> list[str]:
    terms: list[str] = []
    for query_text in query_texts:
        cleaned = clean_text(query_text, max_length=2000).lower()
        for token in TOKEN_PATTERN.findall(cleaned):
            if token in QUERY_LABEL_STOPWORDS or token in terms:
                continue
            terms.append(token)
    return terms[:24]


def extract_supporting_spans(
    text: str,
    *,
    query_texts: Sequence[str],
    max_spans: int = 2,
    window_chars: int = 180,
) -> list[dict[str, Any]]:
    cleaned_text = clean_text(text, max_length=None)
    if not cleaned_text or max_spans <= 0:
        return []

    lowered_text = cleaned_text.lower()
    spans: list[dict[str, Any]] = []
    seen_windows: set[tuple[int, int]] = set()
    half_window = max(40, window_chars // 2)

    for term in _query_terms(query_texts):
        start = lowered_text.find(term.lower())
        if start < 0:
            continue
        end = start + len(term)
        window_start = max(0, start - half_window)
        window_end = min(len(cleaned_text), end + half_window)
        window = (window_start, window_end)
        if window in seen_windows:
            continue
        seen_windows.add(window)
        excerpt = cleaned_text[window_start:window_end].strip()
        excerpt_lower = excerpt.lower()
        matched_terms = [
            candidate
            for candidate in _query_terms(query_texts)
            if candidate.lower() in excerpt_lower
        ][:8]
        spans.append(
            {
                "text": excerpt,
                "matched_terms": matched_terms,
                "start": window_start,
                "end": window_end,
            }
        )
        if len(spans) >= max_spans:
            break

    return spans


def add_supporting_spans_to_results(
    results: Sequence[Mapping[str, Any]],
    *,
    query_texts: Sequence[str],
    max_spans_per_result: int = 2,
) -> list[dict[str, Any]]:
    """Copy retrieval results and add lightweight query-matched spans."""
    compressed: list[dict[str, Any]] = []
    for result in results:
        result_copy = copy.deepcopy(dict(result))
        collected_spans: list[dict[str, Any]] = []
        chunks = result_copy.get("chunks") or []
        if isinstance(chunks, list):
            for chunk in chunks:
                if not isinstance(chunk, dict):
                    continue
                spans = extract_supporting_spans(
                    chunk.get("document") or "",
                    query_texts=query_texts,
                    max_spans=max_spans_per_result,
                )
                chunk["supporting_spans"] = spans
                collected_spans.extend(spans)

        if not collected_spans:
            collected_spans = extract_supporting_spans(
                result_copy.get("document") or "",
                query_texts=query_texts,
                max_spans=max_spans_per_result,
            )
        result_copy["supporting_spans"] = collected_spans[:max_spans_per_result]
        compressed.append(result_copy)
    return compressed
