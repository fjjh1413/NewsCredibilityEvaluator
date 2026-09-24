from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from app.models.knowledge_item import KnowledgeItem
from app.services.chroma_service import (
    ChromaServiceError,
    _build_where_filter,
    _run_knowledge_collection_operation,
    normalize_top_k,
)
from app.services.embedding_service import embed_text, embed_texts
from app.services.rag.chunker import build_knowledge_chunks
from app.services.rag.contracts import RAG_INDEX_VERSION_V2
from app.utils.text_cleaner import clean_text


DEFAULT_DENSE_TOP_N = 50


def build_knowledge_chunk_vector_id(knowledge_id: int, chunk_index: int) -> str:
    return f"knowledge:{int(knowledge_id)}:chunk:{int(chunk_index)}"


def build_knowledge_parent_vector_id(item: KnowledgeItem | object) -> str:
    return f"knowledge:{int(getattr(item, 'id'))}:v2"


def content_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def knowledge_revision_hash(item: KnowledgeItem | object) -> str:
    """Fingerprint evidence-bearing fields, excluding mutable sync timestamps.

    This revision travels with every chunk so readers can reject an older
    vector generation while an asynchronous index update is still pending.
    """
    fields = (
        "title", "content", "summary", "keywords", "debunking_explanation",
        "category", "truth_label", "source_name", "source_url", "publish_time",
        "risk_level",
    )
    payload = {
        name: clean_text(getattr(item, name, None), max_length=None)
        for name in fields
    }
    return content_hash(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _combine_where_filters(*filters: dict[str, Any] | None) -> dict[str, Any] | None:
    parts = [flt for flt in filters if flt]
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    return {"$and": parts}


def _version_filter() -> dict[str, str]:
    return {"index_version": RAG_INDEX_VERSION_V2}


def _parent_filter(knowledge_id: int) -> dict[str, Any]:
    return {
        "$and": [
            {"knowledge_id": int(knowledge_id)},
            _version_filter(),
        ]
    }


def delete_knowledge_item_chunk_vectors(item: KnowledgeItem | object) -> None:
    knowledge_id = int(getattr(item, "id"))
    _run_knowledge_collection_operation(
        "Failed to delete RAG v2 knowledge chunk vectors",
        lambda collection: collection.delete(where=_parent_filter(knowledge_id)),
    )


def reset_knowledge_chunk_vectors() -> None:
    _run_knowledge_collection_operation(
        "Failed to reset RAG v2 knowledge chunk vectors",
        lambda collection: collection.delete(where=_version_filter()),
    )


def upsert_knowledge_item_chunk_vectors(
    item: KnowledgeItem,
    chunk_size: int = 700,
    chunk_overlap: int = 100,
) -> list[str]:
    chunks = build_knowledge_chunks(
        item,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    if not chunks:
        return []

    try:
        embeddings = embed_texts([chunk.chunk_text for chunk in chunks])
    except ChromaServiceError:
        raise
    except Exception as exc:
        raise ChromaServiceError("Failed to embed RAG v2 knowledge chunks") from exc

    vector_ids = [
        build_knowledge_chunk_vector_id(chunk.knowledge_id, chunk.chunk_index)
        for chunk in chunks
    ]
    documents = [chunk.chunk_text for chunk in chunks]
    metadatas = [
        {
            **chunk.to_metadata(),
            "content_hash": content_hash(chunk.chunk_text),
            "parent_revision": knowledge_revision_hash(item),
        }
        for chunk in chunks
    ]

    def _replace_parent_chunks(collection: Any) -> None:
        collection.delete(where=_parent_filter(int(getattr(item, "id"))))
        collection.upsert(
            ids=vector_ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    _run_knowledge_collection_operation(
        "Failed to upsert RAG v2 knowledge chunk vectors",
        _replace_parent_chunks,
    )
    return vector_ids


def search_knowledge_chunk_vectors(
    query_text: str,
    top_n: int = DEFAULT_DENSE_TOP_N,
    category: str | None = None,
    truth_label: str | None = None,
    risk_level: str | None = None,
) -> list[dict[str, Any]]:
    cleaned_query = clean_text(query_text, max_length=8000)
    if not cleaned_query:
        return []

    safe_top_n = normalize_top_k(top_n)
    try:
        query_embedding = embed_text(cleaned_query)
    except ChromaServiceError:
        raise
    except Exception as exc:
        raise ChromaServiceError("Failed to query RAG v2 knowledge chunks") from exc

    where_filter = _combine_where_filters(
        _version_filter(),
        _build_where_filter(
            category=category,
            truth_label=truth_label,
            risk_level=risk_level,
        ),
    )

    results = _run_knowledge_collection_operation(
        "Failed to query RAG v2 knowledge chunks",
        lambda collection: collection.query(
            query_embeddings=[query_embedding],
            n_results=safe_top_n,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        ),
    )

    ids = results.get("ids", [[]])[0]
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    items: list[dict[str, Any]] = []
    for index, vector_id in enumerate(ids):
        distance = distances[index] if index < len(distances) else None
        metadata = metadatas[index] if index < len(metadatas) else {}
        raw_cosine_score = (
            max(-1.0, min(1.0, 1.0 - distance))
            if isinstance(distance, (int, float)) and math.isfinite(distance) else None
        )
        similarity_score = None if raw_cosine_score is None else max(0.0, raw_cosine_score)
        items.append(
            {
                "vector_id": vector_id,
                "chunk_id": metadata.get("chunk_id") or vector_id,
                "document": documents[index] if index < len(documents) else "",
                "metadata": metadata,
                "distance": distance,
                "similarity_score": similarity_score,
                "raw_cosine_score": raw_cosine_score,
                "index_version": RAG_INDEX_VERSION_V2,
            }
        )
    return items


def fetch_rag_v2_parent_chunks(knowledge_id: int) -> list[dict[str, Any]]:
    """Fetch stored v2 chunks for one parent document without embedding/querying."""
    results = _run_knowledge_collection_operation(
        "Failed to fetch RAG v2 parent chunks",
        lambda collection: collection.get(
            where=_parent_filter(int(knowledge_id)),
            include=["documents", "metadatas"],
        ),
    )

    ids = results.get("ids", [])
    documents = results.get("documents", [])
    metadatas = results.get("metadatas", [])
    chunks: list[dict[str, Any]] = []
    for index, vector_id in enumerate(ids):
        metadata = metadatas[index] if index < len(metadatas) else {}
        document = documents[index] if index < len(documents) else ""
        chunks.append(
            {
                "id": vector_id,
                "chunk_id": metadata.get("chunk_id") or vector_id,
                "document": document,
                "metadata": metadata,
            }
        )
    return chunks
