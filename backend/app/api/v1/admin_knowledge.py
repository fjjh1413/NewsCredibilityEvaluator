from fastapi import APIRouter, Depends, Path, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_admin
from app.db.session import get_db
from app.models.user import User
from app.schemas.knowledge import (
    KnowledgeCreate,
    KnowledgeDeleteApiResponse,
    KnowledgeItemApiResponse,
    KnowledgeListApiResponse,
    KnowledgeListData,
    KnowledgeOut,
    KnowledgeRebuildIndexApiResponse,
    KnowledgeRebuildIndexData,
    KnowledgeUpdate,
    VectorSyncStatus,
)
from app.services.knowledge_service import (
    KnowledgeNotFoundError,
    KnowledgeVectorSyncError,
    create_knowledge_item,
    delete_knowledge_item,
    get_knowledge_item,
    list_knowledge_items,
    rebuild_knowledge_index,
    update_knowledge_item,
    vectorize_knowledge_item,
)
from app.services.system_log_service import get_request_ip, record_system_log
from app.utils.response import error_response, success_response


router = APIRouter(prefix="/admin/knowledge", tags=["admin-knowledge"])


@router.get("", response_model=KnowledgeListApiResponse)
def read_knowledge_items(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    category: str | None = Query(default=None),
    truth_label: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    vector_sync_status: VectorSyncStatus | None = Query(default=None),
    keyword: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict:
    items, total = list_knowledge_items(
        db,
        page=page,
        page_size=page_size,
        category=category,
        truth_label=truth_label,
        risk_level=risk_level,
        vector_sync_status=vector_sync_status,
        keyword=keyword,
    )
    data = KnowledgeListData(
        total=total,
        page=page,
        page_size=page_size,
        items=[KnowledgeOut.model_validate(item) for item in items],
    ).model_dump(mode="json")
    return success_response(data=data)


@router.post("/rebuild-index", response_model=KnowledgeRebuildIndexApiResponse)
def rebuild_knowledge_vectors(
    request: Request,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict:
    result = rebuild_knowledge_index(db)
    record_system_log(
        db,
        user_id=current_admin.id,
        module="knowledge",
        action="rebuild_index",
        description=(
            f"管理员重建知识库索引 total={result['total']} "
            f"success={result['success']} failed={result['failed']}"
        ),
        ip_address=get_request_ip(request),
    )
    data = KnowledgeRebuildIndexData(**result).model_dump()
    message = "rebuild completed"
    if result["failed"]:
        message = "rebuild completed with failures"
    return success_response(data=data, message=message)


@router.get("/{id}", response_model=KnowledgeItemApiResponse)
def read_knowledge_item(
    id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict:
    try:
        item = get_knowledge_item(db, id)
    except KnowledgeNotFoundError as exc:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=error_response(str(exc), code=404),
        )

    data = KnowledgeOut.model_validate(item).model_dump(mode="json")
    return success_response(data=data)


@router.post("/{id}/vectorize", response_model=KnowledgeItemApiResponse)
def vectorize_knowledge(
    request: Request,
    id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict:
    try:
        item = vectorize_knowledge_item(db, id)
    except KnowledgeNotFoundError as exc:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=error_response(str(exc), code=404),
        )
    record_system_log(
        db,
        user_id=current_admin.id,
        module="knowledge",
        action="vectorize",
        description=(
            f"管理员向量化知识库 item_id={id} "
            f"vector_sync_status={item.vector_sync_status}"
        ),
        ip_address=get_request_ip(request),
    )

    data = KnowledgeOut.model_validate(item).model_dump(mode="json")
    message = "vectorized"
    if item.vector_sync_status == "failed":
        message = "vector sync failed"
    return success_response(message=message, data=data)


@router.post("", response_model=KnowledgeItemApiResponse, status_code=201)
def create_knowledge(
    payload: KnowledgeCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict:
    item = create_knowledge_item(db, payload)
    record_system_log(
        db,
        user_id=current_admin.id,
        module="knowledge",
        action="create",
        description=f"管理员新增知识库 item_id={item.id}",
        ip_address=get_request_ip(request),
    )
    data = KnowledgeOut.model_validate(item).model_dump(mode="json")
    message = "created"
    if item.vector_sync_status == "failed":
        message = "created, vector sync failed"
    return success_response(message=message, code=201, data=data)


@router.put("/{id}", response_model=KnowledgeItemApiResponse)
def update_knowledge(
    payload: KnowledgeUpdate,
    request: Request,
    id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict:
    try:
        item = update_knowledge_item(db, id, payload)
    except KnowledgeNotFoundError as exc:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=error_response(str(exc), code=404),
        )
    except KnowledgeVectorSyncError as exc:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=error_response(str(exc), code=409),
        )
    record_system_log(
        db,
        user_id=current_admin.id,
        module="knowledge",
        action="update",
        description=f"管理员更新知识库 item_id={id}",
        ip_address=get_request_ip(request),
    )

    data = KnowledgeOut.model_validate(item).model_dump(mode="json")
    message = "success"
    if item.vector_sync_status == "failed":
        message = "updated, vector sync failed"
    return success_response(message=message, data=data)


@router.delete("/{id}", response_model=KnowledgeDeleteApiResponse)
def delete_knowledge(
    request: Request = None,
    id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict:
    try:
        delete_knowledge_item(db, id)
    except KnowledgeNotFoundError as exc:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=error_response(str(exc), code=404),
        )
    except KnowledgeVectorSyncError as exc:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=error_response(str(exc), code=409),
        )
    record_system_log(
        db,
        user_id=current_admin.id,
        module="knowledge",
        action="delete",
        description=f"管理员删除知识库 item_id={id}",
        ip_address=get_request_ip(request),
    )

    return success_response(message="deleted", data={"id": id})
