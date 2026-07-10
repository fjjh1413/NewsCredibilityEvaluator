from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.utils.text_cleaner import clean_text


RAG_INDEX_VERSION_V1 = "v1"
RAG_INDEX_VERSION_V2 = "v2"
RAG_INDEX_VERSION_HYBRID = "hybrid"
SUPPORTED_RAG_INDEX_VERSIONS = {
    RAG_INDEX_VERSION_V1,
    RAG_INDEX_VERSION_V2,
    RAG_INDEX_VERSION_HYBRID,
}


@dataclass(frozen=True)
class RagChunk:
    knowledge_id: int
    chunk_id: str
    chunk_index: int
    chunk_type: str
    chunk_text: str
    parent_title: str
    summary: str = ""
    category: str = ""
    truth_label: str = ""
    source_name: str = ""
    source_url: str = ""
    publish_time: str = ""
    risk_level: str = ""
    keywords: str = ""
    index_version: str = RAG_INDEX_VERSION_V2

    def to_metadata(self) -> dict[str, Any]:
        return {
            "knowledge_id": self.knowledge_id,
            "chunk_id": self.chunk_id,
            "chunk_index": self.chunk_index,
            "chunk_type": self.chunk_type,
            "title": clean_text(self.parent_title, max_length=255),
            "summary": clean_text(self.summary, max_length=1000),
            "category": clean_text(self.category, max_length=50),
            "truth_label": clean_text(self.truth_label, max_length=30),
            "source_name": clean_text(self.source_name, max_length=100),
            "source_url": clean_text(self.source_url, max_length=500),
            "publish_time": clean_text(self.publish_time, max_length=50),
            "risk_level": clean_text(self.risk_level, max_length=30),
            "keywords": clean_text(self.keywords, max_length=500),
            "index_version": self.index_version,
            "vector_sync_status": "synced",
        }


@dataclass
class RagParentCandidate:
    knowledge_id: int
    metadata: dict[str, Any]
    chunks: list[dict[str, Any]] = field(default_factory=list)
    dense_score: float = 0.0
    lexical_score: float = 0.0
    exact_score: float = 0.0
    final_score: float = 0.0

    def to_result(self) -> dict[str, Any]:
        return {
            "vector_id": f"knowledge:{self.knowledge_id}:v2",
            "document": "\n\n".join(chunk.get("document", "") for chunk in self.chunks),
            "metadata": self.metadata,
            "similarity_score": self.final_score,
            "chunks": self.chunks,
            "index_version": RAG_INDEX_VERSION_V2,
            "score_components": {
                "dense_score": round(self.dense_score, 6),
                "lexical_score": round(self.lexical_score, 6),
                "exact_score": round(self.exact_score, 6),
                "final_score": round(self.final_score, 6),
            },
        }
