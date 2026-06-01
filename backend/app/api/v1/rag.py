from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.rag import (
    RagSearchApiResponse,
    RagSearchData,
    RagSearchItem,
    RagSearchRequest,
)
from app.services.knowledge_service import (
    KnowledgeVectorSyncError,
    build_rag_search_text,
    search_similar_knowledge,
)
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
            )
        )

    data = RagSearchData(
        query=query_text,
        top_k=payload.top_k,
        results=items,
        total=len(items),
    ).model_dump(mode="json")
    return success_response(data=data)
