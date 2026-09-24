from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.rag import (
    RagAuditApiResponse,
    RagAuditData,
    RagSearchApiResponse,
    RagSearchData,
    RagSearchItem,
    RagSearchRequest,
)
from app.services.chroma_service import ChromaServiceError
from app.services.knowledge_service import (
    KnowledgeVectorSyncError,
    build_rag_search_text,
    search_similar_knowledge,
)
from app.services.rag.index_audit import audit_rag_v2_index
from app.utils.response import error_response, success_response


router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/search", response_model=RagSearchApiResponse)
def search_knowledge(
    payload: RagSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    query_text = build_rag_search_text(
        title=payload.title,
        content=payload.content,
        query=payload.query,
    )
    try:
        results = search_similar_knowledge(
            db,
            query_text=query_text,
            top_k=payload.top_k,
            category=payload.category,
            truth_label=payload.truth_label,
            risk_level=payload.risk_level,
        )
    except KnowledgeVectorSyncError:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=error_response("Knowledge vector search failed", code=503),
        )

    items: list[RagSearchItem] = []
    for result in results:
        metadata = result.get("metadata") or {}
        items.append(
            RagSearchItem(
                id=metadata["knowledge_id"],
                title=metadata["title"],
                summary=metadata["summary"],
                category=metadata["category"],
                truth_label=metadata["truth_label"],
                source_name=metadata["source_name"],
                vector_sync_status=metadata["vector_sync_status"],
                similarity_score=result.get("similarity_score"),
                raw_cosine_score=result.get("raw_cosine_score"),
                fusion_score=result.get("fusion_score"),
                parent_revision=metadata.get("parent_revision"),
                index_version=(
                    result.get("index_version")
                    or metadata.get("index_version")
                    or "v1"
                ),
                chunks=result.get("chunks") or [],
                score_components=result.get("score_components") or {},
                rerank_original_rank=result.get("rerank_original_rank"),
                rule_rerank_score=result.get("rule_rerank_score"),
                model_rerank_score=result.get("model_rerank_score"),
                model_rerank_reason=result.get("model_rerank_reason"),
                rerank_score=result.get("rerank_score"),
                rerank_stage=result.get("rerank_stage"),
                diversity_adjusted_rerank_score=result.get("diversity_adjusted_rerank_score"),
                rerank_order=result.get("rerank_order"),
            )
        )

    data = RagSearchData(
        query=query_text,
        top_k=payload.top_k,
        results=items,
        total=len(items),
    ).model_dump(mode="json")
    return success_response(data=data)


@router.get("/audit", response_model=RagAuditApiResponse)
def audit_knowledge_index(
    sample_limit: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        summary = audit_rag_v2_index(db, sample_limit=sample_limit)
    except ChromaServiceError:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=error_response("RAG index audit failed", code=503),
        )

    data = RagAuditData.model_validate(summary).model_dump(mode="json")
    return success_response(data=data)
