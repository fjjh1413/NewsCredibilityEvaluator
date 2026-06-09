from sqlalchemy.orm import Session

from app.crud import user as user_crud
from app.models.user import User
from app.schemas.user import AdminUserRoleUpdate
from app.utils.text_cleaner import clean_text


class AdminUserServiceError(Exception):
    """Base exception for administrator user-management failures."""


class AdminUserNotFoundError(AdminUserServiceError):
    pass


class AdminUserSelfOperationError(AdminUserServiceError):
    pass


class AdminUserLastAdminError(AdminUserServiceError):
    pass


def list_admin_users(
    db: Session,
    page: int,
    page_size: int,
    keyword: str | None = None,
    role: str | None = None,
    status: str | None = None,
) -> tuple[list[tuple[User, int]], int]:
    safe_page = max(page, 1)
    safe_page_size = max(1, min(page_size, 100))
    return user_crud.get_users_with_detection_counts(
        db,
        skip=(safe_page - 1) * safe_page_size,
        limit=safe_page_size,
        keyword=clean_text(keyword, max_length=100) or None,
        role=role,
        status=status,
    )


def get_admin_user(db: Session, user_id: int) -> tuple[User, int]:
    result = user_crud.get_user_with_detection_count(db, user_id)
    if result is None:
        raise AdminUserNotFoundError("用户不存在")
    return result


def enable_admin_user(db: Session, user_id: int) -> User:
    return _set_admin_user_status(db, user_id, status="active", current_admin=None)


def disable_admin_user(db: Session, user_id: int, current_admin: User) -> User:
    return _set_admin_user_status(
        db,
        user_id,
        status="disabled",
        current_admin=current_admin,
    )


def update_admin_user_role(
    db: Session,
    user_id: int,
    payload: AdminUserRoleUpdate,
    current_admin: User,
) -> User:
    try:
        user = user_crud.get_user_by_id_for_update(db, user_id)
        if user is None:
            raise AdminUserNotFoundError("用户不存在")
        if user.role == payload.role:
            return user
        if int(user.id) == int(current_admin.id) and payload.role != "admin":
            raise AdminUserSelfOperationError("不能降级当前登录的管理员账号")

        if user.role == "admin" and payload.role != "admin":
            _ensure_admin_remains_available(db, user)

        user.role = payload.role
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    except AdminUserServiceError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


def _set_admin_user_status(
    db: Session,
    user_id: int,
    status: str,
    current_admin: User | None,
) -> User:
    try:
        user = user_crud.get_user_by_id_for_update(db, user_id)
        if user is None:
            raise AdminUserNotFoundError("用户不存在")
        if user.status == status:
            return user

        if status == "disabled":
            if current_admin is not None and int(user.id) == int(current_admin.id):
                raise AdminUserSelfOperationError("不能禁用当前登录的管理员账号")
            if user.role == "admin":
                _ensure_admin_remains_available(db, user)

        user.status = status
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    except AdminUserServiceError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


def _ensure_admin_remains_available(db: Session, target: User) -> None:
    admins = user_crud.lock_admin_users(db)
    active_admins = [user for user in admins if user.status == "active"]

    if len(admins) <= 1:
        raise AdminUserLastAdminError("不能移除系统中的最后一个管理员")
    if target.status == "active" and len(active_admins) <= 1:
        raise AdminUserLastAdminError("不能禁用或降级系统中最后一个可用管理员")
