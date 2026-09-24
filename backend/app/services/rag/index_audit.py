from __future__ import annotations

from collections import Counter
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.crud import knowledge_crud
from app.models.knowledge_item import KnowledgeItem
from app.services.rag.chunker import build_knowledge_chunks
from app.services.rag.contracts import RAG_INDEX_VERSION_V2
from app.services.rag.vector_index import (
    build_knowledge_chunk_vector_id,
    content_hash,
    knowledge_revision_hash,
    fetch_rag_v2_parent_chunks,
)
from app.utils.text_cleaner import clean_text


def expected_chunk_records_for_item(item: KnowledgeItem | object) -> list[dict[str, Any]]:
    settings = get_settings()
    chunks = build_knowledge_chunks(
        item,
        chunk_size=getattr(settings, "rag_chunk_size", 700),
        chunk_overlap=getattr(settings, "rag_chunk_overlap", 100),
    )
    return [
        {
            "chunk_id": build_knowledge_chunk_vector_id(
                int(chunk.knowledge_id),
                int(chunk.chunk_index),
            ),
            "chunk_index": int(chunk.chunk_index),
            "chunk_type": chunk.chunk_type,
            "content_hash": content_hash(chunk.chunk_text),
            "parent_revision": knowledge_revision_hash(item),
        }
        for chunk in chunks
    ]


def _actual_chunk_id(chunk: dict[str, Any]) -> str:
    metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
    return clean_text(
        metadata.get("chunk_id") or chunk.get("chunk_id") or chunk.get("id"),
        max_length=200,
    )


def _actual_content_hash(chunk: dict[str, Any]) -> str:
    metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
    stored_hash = clean_text(metadata.get("content_hash"), max_length=128)
    if stored_hash:
        return stored_hash
    return content_hash(clean_text(chunk.get("document"), max_length=None))


def _issue(
    issue_type: str,
    chunk_id: str | None = None,
    detail: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {"type": issue_type}
    if chunk_id:
        result["chunk_id"] = chunk_id
    if detail:
        result["detail"] = detail
    return result


def _audit_item(item: KnowledgeItem | object) -> dict[str, Any]:
    expected_records = expected_chunk_records_for_item(item)
    expected_by_id = {record["chunk_id"]: record for record in expected_records}
    actual_chunks = fetch_rag_v2_parent_chunks(int(getattr(item, "id")))
    actual_by_id = {
        chunk_id: chunk
        for chunk in actual_chunks
        if (chunk_id := _actual_chunk_id(chunk))
    }

    issues: list[dict[str, Any]] = []
    if clean_text(getattr(item, "vector_sync_status", None), max_length=50) != "synced":
        issues.append(
            _issue(
                "unsynced_item",
                detail=f"vector_sync_status={getattr(item, 'vector_sync_status', None)}",
            )
        )

    for chunk_id in sorted(set(expected_by_id) - set(actual_by_id)):
        issues.append(_issue("missing_chunk", chunk_id))

    for chunk_id in sorted(set(actual_by_id) - set(expected_by_id)):
        issues.append(_issue("extra_chunk", chunk_id))

    for chunk_id in sorted(set(expected_by_id) & set(actual_by_id)):
        expected = expected_by_id[chunk_id]
        actual = actual_by_id[chunk_id]
        metadata = actual.get("metadata") if isinstance(actual.get("metadata"), dict) else {}
        actual_hash = _actual_content_hash(actual)
        if actual_hash != expected["content_hash"]:
            issues.append(_issue("stale_chunk", chunk_id))
        if metadata.get("parent_revision") != expected["parent_revision"]:
            issues.append(_issue("stale_parent_revision", chunk_id))
        if metadata.get("index_version") != RAG_INDEX_VERSION_V2:
            issues.append(
                _issue(
                    "wrong_index_version",
                    chunk_id,
                    detail=f"index_version={metadata.get('index_version')}",
                )
            )

    return {
        "knowledge_id": int(getattr(item, "id")),
        "title": clean_text(getattr(item, "title", None), max_length=255),
        "expected_chunk_count": len(expected_records),
        "actual_chunk_count": len(actual_chunks),
        "issue_count": len(issues),
        "issues": issues,
    }


def audit_rag_v2_index(
    db: Session,
    *,
    sample_limit: int | None = None,
) -> dict[str, Any]:
    """Audit MySQL knowledge records against stored RAG v2 Chroma chunks."""
    settings = get_settings()
    limit = sample_limit or getattr(settings, "rag_audit_sample_limit", 200)
    limit = max(1, int(limit))

    all_items = knowledge_crud.get_all_knowledge_items(db)
    checked_items = all_items[:limit]
    item_results = [_audit_item(item) for item in checked_items]
    issue_counter: Counter[str] = Counter(
        issue["type"]
        for item in item_results
        for issue in item["issues"]
    )
    problematic_items = [item for item in item_results if item["issue_count"] > 0]
    return {
        "status": "ok" if not issue_counter else "failed",
        "index_version": RAG_INDEX_VERSION_V2,
        "total_items": len(all_items),
        "checked_items": len(checked_items),
        "sample_limit": limit,
        "items_with_issues": len(problematic_items),
        "issue_count": sum(issue_counter.values()),
        "issues_by_type": dict(issue_counter),
        "items": problematic_items,
    }
