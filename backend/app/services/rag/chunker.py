from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.services.rag.contracts import RAG_INDEX_VERSION_V2, RagChunk
from app.utils.text_cleaner import clean_text


DEFAULT_CHUNK_SIZE = 700
DEFAULT_CHUNK_OVERLAP = 100
MIN_CHUNK_SIZE = 120
MIN_CHUNK_OVERLAP = 0


def _get_field(item: object, field_name: str) -> object:
    if isinstance(item, dict):
        return item.get(field_name)
    return getattr(item, field_name, None)


def _format_time(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return clean_text(value, max_length=50)


def _bounded_chunk_settings(chunk_size: int, chunk_overlap: int) -> tuple[int, int]:
    safe_size = max(MIN_CHUNK_SIZE, int(chunk_size or DEFAULT_CHUNK_SIZE))
    safe_overlap = max(MIN_CHUNK_OVERLAP, int(chunk_overlap or 0))
    safe_overlap = min(safe_overlap, max(0, safe_size // 2))
    return safe_size, safe_overlap


def split_text(
    text: str | None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """Split Chinese news text into stable overlapping chunks.

    Paragraphs are kept when possible. Very long paragraphs are split with an
    overlap window so named entities near boundaries remain retrievable.
    """

    cleaned = clean_text(text, max_length=None)
    if not cleaned:
        return []

    safe_size, safe_overlap = _bounded_chunk_settings(chunk_size, chunk_overlap)
    paragraphs = [part.strip() for part in cleaned.split("\n") if part.strip()]
    units = paragraphs or [cleaned]

    chunks: list[str] = []
    current = ""

    def flush_current() -> None:
        nonlocal current
        if current:
            chunks.append(current)
            current = ""

    for unit in units:
        if len(unit) > safe_size:
            flush_current()
            start = 0
            step = max(1, safe_size - safe_overlap)
            while start < len(unit):
                part = unit[start : start + safe_size]
                if part:
                    chunks.append(part)
                if start + safe_size >= len(unit):
                    break
                start += step
            continue

        candidate = unit if not current else f"{current}\n{unit}"
        if len(candidate) <= safe_size:
            current = candidate
            continue

        flush_current()
        current = unit

    flush_current()

    if safe_overlap and len(chunks) > 1:
        overlapped: list[str] = [chunks[0]]
        for previous, chunk in zip(chunks, chunks[1:]):
            overlap = previous[-safe_overlap:]
            overlapped.append(f"{overlap}{chunk}")
        chunks = overlapped

    return [chunk for chunk in chunks if chunk.strip()]


def _append_chunk(
    chunks: list[RagChunk],
    *,
    knowledge_id: int,
    chunk_type: str,
    chunk_text: str,
    parent_title: str,
    summary: str,
    category: str,
    truth_label: str,
    source_name: str,
    source_url: str,
    publish_time: str,
    risk_level: str,
    keywords: str,
) -> None:
    cleaned_text = clean_text(chunk_text, max_length=None)
    if not cleaned_text:
        return
    chunk_index = len(chunks)
    chunks.append(
        RagChunk(
            knowledge_id=knowledge_id,
            chunk_id=f"knowledge:{knowledge_id}:chunk:{chunk_index}",
            chunk_index=chunk_index,
            chunk_type=chunk_type,
            chunk_text=cleaned_text,
            parent_title=parent_title,
            summary=summary,
            category=category,
            truth_label=truth_label,
            source_name=source_name,
            source_url=source_url,
            publish_time=publish_time,
            risk_level=risk_level,
            keywords=keywords,
            index_version=RAG_INDEX_VERSION_V2,
        )
    )


def build_knowledge_chunks(
    item: object,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[RagChunk]:
    knowledge_id = int(_get_field(item, "id") or 0)
    if knowledge_id <= 0:
        raise ValueError("knowledge item id is required for RAG chunking")

    title = clean_text(_get_field(item, "title"), max_length=255)
    summary = clean_text(_get_field(item, "summary"), max_length=1000)
    content = clean_text(_get_field(item, "content"), max_length=None)
    category = clean_text(_get_field(item, "category"), max_length=50)
    truth_label = clean_text(_get_field(item, "truth_label"), max_length=30)
    source_name = clean_text(_get_field(item, "source_name"), max_length=100)
    source_url = clean_text(_get_field(item, "source_url"), max_length=500)
    publish_time = _format_time(_get_field(item, "publish_time"))
    risk_level = clean_text(_get_field(item, "risk_level"), max_length=30)
    keywords = clean_text(_get_field(item, "keywords"), max_length=500)
    debunking = clean_text(
        _get_field(item, "debunking_explanation"),
        max_length=None,
    )

    chunks: list[RagChunk] = []
    title_summary_parts = [f"title: {title}" if title else ""]
    if summary:
        title_summary_parts.append(f"summary: {summary}")
    if keywords:
        title_summary_parts.append(f"keywords: {keywords}")
    if truth_label:
        title_summary_parts.append(f"truth_label: {truth_label}")
    if category:
        title_summary_parts.append(f"category: {category}")

    _append_chunk(
        chunks,
        knowledge_id=knowledge_id,
        chunk_type="title_summary",
        chunk_text="\n".join(part for part in title_summary_parts if part),
        parent_title=title,
        summary=summary,
        category=category,
        truth_label=truth_label,
        source_name=source_name,
        source_url=source_url,
        publish_time=publish_time,
        risk_level=risk_level,
        keywords=keywords,
    )

    context = "\n".join(
        part
        for part in (
            f"title: {title}" if title else "",
            f"source: {source_name}" if source_name else "",
            f"publish_time: {publish_time}" if publish_time else "",
        )
        if part
    )
    for content_chunk in split_text(content, chunk_size, chunk_overlap):
        chunk_text = f"{context}\ncontent: {content_chunk}" if context else content_chunk
        _append_chunk(
            chunks,
            knowledge_id=knowledge_id,
            chunk_type="content",
            chunk_text=chunk_text,
            parent_title=title,
            summary=summary,
            category=category,
            truth_label=truth_label,
            source_name=source_name,
            source_url=source_url,
            publish_time=publish_time,
            risk_level=risk_level,
            keywords=keywords,
        )

    if debunking:
        _append_chunk(
            chunks,
            knowledge_id=knowledge_id,
            chunk_type="debunking",
            chunk_text=(
                f"title: {title}\n"
                f"truth_label: {truth_label}\n"
                f"debunking_explanation: {debunking}"
            ),
            parent_title=title,
            summary=summary,
            category=category,
            truth_label=truth_label,
            source_name=source_name,
            source_url=source_url,
            publish_time=publish_time,
            risk_level=risk_level,
            keywords=keywords,
        )

    return chunks
