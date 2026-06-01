from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.models.knowledge_item import KnowledgeItem
from app.services.embedding_service import embed_text
from app.utils.text_cleaner import clean_text


KNOWLEDGE_COLLECTION_NAME = "knowledge_items"

_clients: dict[str, Any] = {}
_collections: dict[tuple[str, str], Any] = {}
MIN_TOP_K = 1
MAX_TOP_K = 50


class ChromaServiceError(Exception):
    """Raised when local Chroma operations fail."""


def _import_chromadb() -> Any:
    try:
        import chromadb
    except ImportError as exc:
        raise ChromaServiceError(
            "chromadb is not installed. Run `pip install -r requirements.txt`."
        ) from exc
    return chromadb


def get_chroma_persist_dir() -> str:
    return get_settings().chroma_persist_path


def get_chroma_client() -> Any:
    persist_dir = get_chroma_persist_dir()
    if persist_dir not in _clients:
        try:
            Path(persist_dir).mkdir(parents=True, exist_ok=True)
            chromadb = _import_chromadb()
            _clients[persist_dir] = chromadb.PersistentClient(path=persist_dir)
        except ChromaServiceError:
            raise
        except Exception as exc:
            raise ChromaServiceError("Failed to connect to Chroma") from exc
    return _clients[persist_dir]


def get_knowledge_collection() -> Any:
    persist_dir = get_chroma_persist_dir()
    cache_key = (persist_dir, KNOWLEDGE_COLLECTION_NAME)
    if cache_key not in _collections:
        try:
            client = get_chroma_client()
            _collections[cache_key] = client.get_or_create_collection(
                name=KNOWLEDGE_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
        except ChromaServiceError:
            raise
        except Exception as exc:
            raise ChromaServiceError("Failed to get Chroma collection") from exc
    return _collections[cache_key]


def reset_knowledge_collection() -> None:
    persist_dir = get_chroma_persist_dir()
    cache_key = (persist_dir, KNOWLEDGE_COLLECTION_NAME)
    try:
        client = get_chroma_client()
        try:
            client.delete_collection(name=KNOWLEDGE_COLLECTION_NAME)
        except Exception as exc:
            message = str(exc).lower()
            if "does not exist" not in message and "not found" not in message:
                raise
        _collections.pop(cache_key, None)
        get_knowledge_collection()
    except ChromaServiceError:
        raise
    except Exception as exc:
        raise ChromaServiceError("Failed to reset Chroma collection") from exc


def normalize_top_k(top_k: int) -> int:
    return max(MIN_TOP_K, min(top_k, MAX_TOP_K))


def build_knowledge_vector_id(item: KnowledgeItem) -> str:
    return f"knowledge:{item.id}"


def build_knowledge_metadata(item: KnowledgeItem) -> dict[str, str | int]:
    return {
        "knowledge_id": int(item.id),
        "title": clean_text(item.title, max_length=255),
        "category": clean_text(item.category, max_length=50),
        "truth_label": clean_text(item.truth_label, max_length=30),
        "source_name": clean_text(item.source_name, max_length=100),
        "risk_level": clean_text(item.risk_level, max_length=30),
    }


def upsert_knowledge_item_vector(
    item: KnowledgeItem,
    embedding_text: str,
) -> str:
    vector_id = build_knowledge_vector_id(item)
    try:
        collection = get_knowledge_collection()
        collection.upsert(
            ids=[vector_id],
            embeddings=[embed_text(embedding_text)],
            documents=[embedding_text],
            metadatas=[build_knowledge_metadata(item)],
        )
        return vector_id
    except ChromaServiceError:
        raise
    except Exception as exc:
        raise ChromaServiceError("Failed to upsert knowledge vector") from exc


def delete_knowledge_item_vector(item: KnowledgeItem) -> None:
    vector_id = item.vector_id or build_knowledge_vector_id(item)
    try:
        collection = get_knowledge_collection()
        collection.delete(ids=[vector_id])
    except ChromaServiceError:
        raise
    except Exception as exc:
        raise ChromaServiceError("Failed to delete knowledge vector") from exc


def _build_where_filter(
    category: str | None = None,
    truth_label: str | None = None,
    risk_level: str | None = None,
) -> dict[str, Any] | None:
    filters: list[dict[str, str]] = []
    if category:
        filters.append({"category": category})
    if truth_label:
        filters.append({"truth_label": truth_label})
    if risk_level:
        filters.append({"risk_level": risk_level})

    if not filters:
        return None
    if len(filters) == 1:
        return filters[0]
    return {"$and": filters}


def search_knowledge_vectors(
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
        collection = get_knowledge_collection()
        results = collection.query(
            query_embeddings=[embed_text(cleaned_query)],
            n_results=safe_top_k,
            where=_build_where_filter(
                category=category,
                truth_label=truth_label,
                risk_level=risk_level,
            ),
            include=["documents", "metadatas", "distances"],
        )
    except ChromaServiceError:
        raise
    except Exception as exc:
        raise ChromaServiceError("Failed to query knowledge vectors") from exc

    ids = results.get("ids", [[]])[0]
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    items: list[dict[str, Any]] = []
    for index, vector_id in enumerate(ids):
        distance = distances[index] if index < len(distances) else None
        similarity_score = None if distance is None else max(0.0, 1.0 - distance)
        items.append(
            {
                "vector_id": vector_id,
                "document": documents[index] if index < len(documents) else "",
                "metadata": metadatas[index] if index < len(metadatas) else {},
                "distance": distance,
                "similarity_score": similarity_score,
            }
        )
    return items
