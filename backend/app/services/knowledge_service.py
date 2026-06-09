import logging
from typing import Any

from sqlalchemy.orm import Session

from app.crud import knowledge_crud
from app.models.knowledge_item import KnowledgeItem
from app.schemas.knowledge import KnowledgeCreate, KnowledgeUpdate
from app.services.chroma_service import (
    ChromaServiceError,
    delete_knowledge_item_vector,
    normalize_top_k,
    reset_knowledge_collection,
    search_knowledge_vectors,
    upsert_knowledge_item_vector,
)
from app.utils.text_cleaner import clean_text


logger = logging.getLogger(__name__)


class KnowledgeServiceError(Exception):
    """Base exception for knowledge service errors."""


class KnowledgeNotFoundError(KnowledgeServiceError):
    pass


class KnowledgeVectorSyncError(KnowledgeServiceError):
    pass


def _format_sync_error(exc: Exception) -> str:
    return clean_text(f"{type(exc).__name__}: {exc}", max_length=1000)


def _get_knowledge_field(item: object, field_name: str) -> object:
    if isinstance(item, dict):
        return item.get(field_name)
    return getattr(item, field_name, None)


def build_knowledge_embedding_text(
    item: object,
    max_length: int | None = 8000,
) -> str:
    field_labels = (
        ("title", "title"),
        ("content", "content"),
        ("category", "category"),
        ("summary", "summary"),
        ("keywords", "keywords"),
        ("truth_label", "truth_label"),
        ("debunking_explanation", "debunking_explanation"),
    )

    lines: list[str] = []
    for field_name, label in field_labels:
        value = clean_text(_get_knowledge_field(item, field_name), max_length=None)
        if value:
            lines.append(f"{label}: {value}")

    return clean_text("\n".join(lines), max_length=max_length)


def _mark_vector_pending(
    db: Session,
    item: KnowledgeItem,
    auto_commit: bool = True,
) -> KnowledgeItem:
    return knowledge_crud.update_knowledge_vector_state(
        db,
        item,
        status="pending",
        error=None,
        auto_commit=auto_commit,
    )


def _mark_vector_failed(
    db: Session,
    item: KnowledgeItem,
    exc: Exception,
    auto_commit: bool = True,
) -> KnowledgeItem:
    error_message = _format_sync_error(exc)
    logger.exception("Knowledge vector sync failed for item id=%s", item.id)
    return knowledge_crud.update_knowledge_vector_state(
        db,
        item,
        status="failed",
        error=error_message,
        auto_commit=auto_commit,
    )


def _mark_vector_delete_failed(
    db: Session,
    item: KnowledgeItem,
    delete_exc: Exception,
    vector_id: str | None = None,
    restore_exc: Exception | None = None,
    auto_commit: bool = True,
) -> KnowledgeItem:
    error_parts = [f"MySQL delete failed: {_format_sync_error(delete_exc)}"]
    if restore_exc is None:
        error_parts.append("Chroma vector was restored; delete must be retried")
    else:
        error_parts.append(
            f"Chroma vector restore failed: {_format_sync_error(restore_exc)}"
        )
    error_message = clean_text("; ".join(error_parts), max_length=1000)
    logger.warning(
        "Knowledge delete failed for item id=%s; marking vector_sync_status=delete_failed",
        item.id,
    )
    return knowledge_crud.update_knowledge_vector_state(
        db,
        item,
        status="delete_failed",
        vector_id=vector_id,
        error=error_message,
        auto_commit=auto_commit,
    )


def _try_mark_vector_delete_failed(
    db: Session,
    item: KnowledgeItem,
    delete_exc: Exception,
    vector_id: str | None = None,
    restore_exc: Exception | None = None,
) -> bool:
    try:
        _mark_vector_delete_failed(
            db,
            item,
            delete_exc,
            vector_id=vector_id,
            restore_exc=restore_exc,
        )
        return True
    except Exception:
        db.rollback()
        logger.exception(
            "Failed to mark knowledge item id=%s vector_sync_status=delete_failed",
            item.id,
        )
        return False


def _mark_vector_synced(
    db: Session,
    item: KnowledgeItem,
    vector_id: str,
    auto_commit: bool = True,
) -> KnowledgeItem:
    return knowledge_crud.update_knowledge_vector_state(
        db,
        item,
        status="synced",
        vector_id=vector_id,
        error=None,
        auto_commit=auto_commit,
    )


def build_rag_search_text(
    title: str | None = None,
    content: str | None = None,
    query: str | None = None,
    max_length: int | None = 8000,
) -> str:
    title_text = clean_text(title, max_length=None)
    content_text = clean_text(content, max_length=None)
    if title_text or content_text:
        parts: list[str] = []
        if title_text:
            parts.append(f"title: {title_text}")
        if content_text:
            parts.append(f"content: {content_text}")
        return clean_text("\n".join(parts), max_length=max_length)

    return clean_text(query, max_length=max_length)


def _sync_knowledge_vector(
    db: Session,
    item: KnowledgeItem,
    auto_commit: bool = True,
    raise_on_failure: bool = False,
) -> KnowledgeItem:
    embedding_text = build_knowledge_embedding_text(item)
    try:
        vector_id = upsert_knowledge_item_vector(item, embedding_text)
    except ChromaServiceError as exc:
        failed_item = _mark_vector_failed(db, item, exc, auto_commit=auto_commit)
        if raise_on_failure:
            raise KnowledgeVectorSyncError(
                "Knowledge update failed because Chroma vector sync failed"
            ) from exc
        return failed_item

    return _mark_vector_synced(db, item, vector_id, auto_commit=auto_commit)


def list_knowledge_items(
    db: Session,
    page: int,
    page_size: int,
    category: str | None = None,
    truth_label: str | None = None,
    risk_level: str | None = None,
    keyword: str | None = None,
) -> tuple[list[KnowledgeItem], int]:
    skip = (page - 1) * page_size
    return knowledge_crud.get_knowledge_items(
        db,
        skip=skip,
        limit=page_size,
        category=category,
        truth_label=truth_label,
        risk_level=risk_level,
        keyword=keyword,
    )


def get_knowledge_item(db: Session, item_id: int) -> KnowledgeItem:
    item = knowledge_crud.get_knowledge_item(db, item_id)
    if item is None:
        raise KnowledgeNotFoundError("Knowledge item not found")
    return item


def create_knowledge_item(
    db: Session,
    item_in: KnowledgeCreate,
) -> KnowledgeItem:
    item = knowledge_crud.create_knowledge_item(db, item_in)
    return _sync_knowledge_vector(db, item)


def update_knowledge_item(
    db: Session,
    item_id: int,
    item_in: KnowledgeUpdate,
) -> KnowledgeItem:
    item = get_knowledge_item(db, item_id)
    updated_item = knowledge_crud.update_knowledge_item(
        db,
        item,
        item_in,
        auto_commit=False,
    )
    try:
        synced_item = _sync_knowledge_vector(
            db,
            updated_item,
            auto_commit=False,
            raise_on_failure=True,
        )
    except KnowledgeVectorSyncError:
        db.rollback()
        logger.exception(
            "Knowledge update rolled back because vector sync failed for item id=%s",
            item_id,
        )
        raise
    except Exception:
        db.rollback()
        logger.exception("Knowledge update failed before commit for item id=%s", item_id)
        raise

    db.commit()
    db.refresh(synced_item)
    return synced_item


def delete_knowledge_item(db: Session, item_id: int) -> None:
    """Delete Chroma vector first, then MySQL record.

    This is not a distributed transaction. If MySQL delete fails after Chroma
    delete, the service tries to restore the vector and marks the MySQL record
    as delete_failed when possible. In production, soft delete or an async
    compensation job is safer for cross-store consistency.
    """
    item = get_knowledge_item(db, item_id)
    try:
        delete_knowledge_item_vector(item)
    except ChromaServiceError as exc:
        logger.exception(
            "Chroma knowledge vector delete failed for item id=%s; MySQL record kept",
            item.id,
        )
        _mark_vector_failed(db, item, exc)
        raise KnowledgeVectorSyncError(
            "Failed to delete knowledge vector; MySQL record was not deleted"
        ) from exc

    try:
        knowledge_crud.delete_knowledge_item(db, item)
    except Exception as exc:
        db.rollback()
        logger.exception("MySQL knowledge delete failed for item id=%s", item.id)
        _restore_vector_after_mysql_delete_failure(db, item, exc)


def search_similar_knowledge(
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

    safe_top_k = normalize_top_k(top_k)
    try:
        vector_results = search_knowledge_vectors(
            cleaned_query,
            top_k=safe_top_k,
            category=category,
            truth_label=truth_label,
            risk_level=risk_level,
        )
    except ChromaServiceError as exc:
        raise KnowledgeVectorSyncError("Knowledge vector search failed") from exc

    verified_results: list[dict[str, Any]] = []
    for result in vector_results:
        metadata = result.get("metadata") or {}
        knowledge_id = metadata.get("knowledge_id")
        if knowledge_id is None:
            continue

        db_item = knowledge_crud.get_knowledge_item(db, int(knowledge_id))
        if db_item is None:
            continue

        result["metadata"] = {
            "knowledge_id": int(db_item.id),
            "title": clean_text(db_item.title, max_length=255),
            "summary": clean_text(db_item.summary, max_length=1000),
            "category": clean_text(db_item.category, max_length=50),
            "truth_label": clean_text(db_item.truth_label, max_length=30),
            "source_name": clean_text(db_item.source_name, max_length=100),
            "risk_level": clean_text(db_item.risk_level, max_length=30),
            "vector_sync_status": clean_text(
                db_item.vector_sync_status,
                max_length=20,
            ),
        }
        verified_results.append(result)

    return verified_results


def _restore_vector_after_mysql_delete_failure(
    db: Session,
    item: KnowledgeItem,
    delete_exc: Exception,
) -> None:
    try:
        vector_id = upsert_knowledge_item_vector(
            item,
            build_knowledge_embedding_text(item),
        )
    except Exception as restore_exc:
        db.rollback()
        logger.exception("Knowledge vector restore failed for item id=%s", item.id)
        existing_item = knowledge_crud.get_knowledge_item(db, int(item.id))
        if existing_item is not None:
            marked = _try_mark_vector_delete_failed(
                db,
                existing_item,
                delete_exc,
                restore_exc=restore_exc,
            )
            mark_message = (
                "knowledge item marked delete_failed"
                if marked
                else "failed to mark knowledge item delete_failed"
            )
        else:
            logger.error(
                "Knowledge item id=%s was not found while marking delete_failed",
                item.id,
            )
            mark_message = "knowledge item could not be marked delete_failed"
        raise KnowledgeVectorSyncError(
            f"MySQL delete failed and vector restore failed; {mark_message}"
        ) from delete_exc

    logger.warning(
        "MySQL delete failed for item id=%s; Chroma vector was restored",
        item.id,
    )
    existing_item = knowledge_crud.get_knowledge_item(db, int(item.id))
    if existing_item is not None:
        marked = _try_mark_vector_delete_failed(db, existing_item, delete_exc, vector_id)
        mark_message = (
            "knowledge item marked delete_failed"
            if marked
            else "failed to mark knowledge item delete_failed"
        )
    else:
        logger.error(
            "Knowledge item id=%s was not found after restored vector",
            item.id,
        )
        mark_message = "knowledge item could not be marked delete_failed"
    raise KnowledgeVectorSyncError(
        f"MySQL delete failed; vector was restored; {mark_message}"
    ) from delete_exc


def vectorize_knowledge_item(db: Session, item_id: int) -> KnowledgeItem:
    item = get_knowledge_item(db, item_id)
    item = _mark_vector_pending(db, item)
    return _sync_knowledge_vector(db, item)


def rebuild_knowledge_index(db: Session) -> dict[str, Any]:
    items = knowledge_crud.get_all_knowledge_items(db)
    failed_ids: list[int] = []

    try:
        reset_knowledge_collection()
    except ChromaServiceError as exc:
        for item in items:
            _mark_vector_failed(db, item, exc)
            failed_ids.append(int(item.id))
        return {
            "total": len(items),
            "success": 0,
            "failed": len(failed_ids),
            "failed_ids": failed_ids,
        }

    success_count = 0
    for item in items:
        pending_item = _mark_vector_pending(db, item)
        synced_item = _sync_knowledge_vector(db, pending_item)
        if synced_item.vector_sync_status == "synced":
            success_count += 1
        else:
            failed_ids.append(int(synced_item.id))

    return {
        "total": len(items),
        "success": success_count,
        "failed": len(failed_ids),
        "failed_ids": failed_ids,
    }
