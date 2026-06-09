from fastapi import APIRouter, Depends, Path, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_admin
from app.crud.detection_crud import get_detection_history
from app.db.session import get_db
from app.models.user import User
from app.schemas.detection import (
    DetectionHistoryApiResponse,
    DetectionHistoryData,
    DetectionHistoryItem,
)
from app.schemas.user import (
    AdminUserItemApiResponse,
    AdminUserListApiResponse,
    AdminUserListData,
    AdminUserOut,
    AdminUserRoleUpdate,
    UserRole,
    UserStatus,
)
from app.services.admin_user_service import (
    AdminUserLastAdminError,
    AdminUserNotFoundError,
    AdminUserSelfOperationError,
    disable_admin_user,
    enable_admin_user,
    get_admin_user,
    list_admin_users,
    update_admin_user_role,
)
from app.utils.response import error_response, success_response


router = APIRouter(prefix="/admin/users", tags=["admin-users"])


@router.get("", response_model=AdminUserListApiResponse)
def read_admin_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = Query(default=None),
    role: UserRole | None = Query(default=None),
    status_value: UserStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict:
    items, total = list_admin_users(
        db,
        page=page,
        page_size=page_size,
        keyword=keyword,
        role=role,
        status=status_value,
    )
    data = AdminUserListData(
        total=total,
        page=page,
        page_size=page_size,
        items=[_user_out(user, detection_count) for user, detection_count in items],
    ).model_dump(mode="json")
    return success_response(data=data)


@router.get("/{user_id}/detections", response_model=DetectionHistoryApiResponse)
def read_admin_user_detections(
    user_id: int = Path(..., ge=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict | JSONResponse:
    try:
        get_admin_user(db, user_id)
    except AdminUserNotFoundError as exc:
        return _not_found(exc)

    items, total = get_detection_history(
        db,
        current_user=current_admin,
        page=page,
        page_size=page_size,
        user_id=user_id,
    )
    data = DetectionHistoryData(
        total=total,
        page=page,
        page_size=page_size,
        items=[DetectionHistoryItem.model_validate(item) for item in items],
    ).model_dump(mode="json")
    return success_response(data=data)


@router.get("/{user_id}", response_model=AdminUserItemApiResponse)
def read_admin_user(
    user_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict | JSONResponse:
    try:
        user, detection_count = get_admin_user(db, user_id)
    except AdminUserNotFoundError as exc:
        return _not_found(exc)
    return _item_response(user, detection_count)


@router.post("/{user_id}/enable", response_model=AdminUserItemApiResponse)
def enable_user(
    user_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict | JSONResponse:
    try:
        user = enable_admin_user(db, user_id)
        _, detection_count = get_admin_user(db, user_id)
    except AdminUserNotFoundError as exc:
        return _not_found(exc)
    return _item_response(user, detection_count, message="用户已启用")


@router.post("/{user_id}/disable", response_model=AdminUserItemApiResponse)
def disable_user(
    user_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict | JSONResponse:
    try:
        user = disable_admin_user(db, user_id, current_admin)
        _, detection_count = get_admin_user(db, user_id)
    except AdminUserNotFoundError as exc:
        return _not_found(exc)
    except (AdminUserSelfOperationError, AdminUserLastAdminError) as exc:
        return _conflict(exc)
    return _item_response(user, detection_count, message="用户已禁用")


@router.post("/{user_id}/role", response_model=AdminUserItemApiResponse)
def update_user_role(
    payload: AdminUserRoleUpdate,
    user_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict | JSONResponse:
    try:
        user = update_admin_user_role(db, user_id, payload, current_admin)
        _, detection_count = get_admin_user(db, user_id)
    except AdminUserNotFoundError as exc:
        return _not_found(exc)
    except (AdminUserSelfOperationError, AdminUserLastAdminError) as exc:
        return _conflict(exc)
    return _item_response(user, detection_count, message="用户角色已更新")


def _user_out(user: User, detection_count: int) -> AdminUserOut:
    return AdminUserOut(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        status=user.status,
        is_active=user.status == "active",
        created_at=user.created_at,
        updated_at=user.updated_at,
        detection_count=detection_count,
    )


def _item_response(
    user: User,
    detection_count: int,
    message: str = "success",
) -> dict:
    return success_response(
        message=message,
        data=_user_out(user, detection_count).model_dump(mode="json"),
    )


def _not_found(exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=error_response(str(exc), code=404),
    )


def _conflict(exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content=error_response(str(exc), code=409),
    )
