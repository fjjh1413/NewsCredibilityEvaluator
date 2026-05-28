from sqlalchemy.orm import Session

from app.crud import user as user_crud
from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.schemas.user import UserAdminCreate, UserCreate


class AuthServiceError(Exception):
    """Base exception for authentication service errors."""


class UserAlreadyExistsError(AuthServiceError):
    pass


class InvalidCredentialsError(AuthServiceError):
    pass


class DisabledUserError(AuthServiceError):
    pass


def _ensure_user_not_exists(db: Session, username: str, email: str | None) -> None:
    if user_crud.get_user_by_username(db, username):
        raise UserAlreadyExistsError("用户名已存在")

    if email and user_crud.get_user_by_email(db, email):
        raise UserAlreadyExistsError("邮箱已存在")


def register_user(db: Session, user_in: UserCreate) -> User:
    _ensure_user_not_exists(db, user_in.username, user_in.email)

    password_hash = get_password_hash(user_in.password)
    return user_crud.create_user(
        db,
        user_in=user_in,
        password_hash=password_hash,
        role="user",
        status="active",
    )


def create_admin_user(db: Session, user_in: UserAdminCreate) -> User:
    if user_crud.get_user_by_username(db, user_in.username):
        raise UserAlreadyExistsError("用户名已存在")

    if user_in.email and user_crud.get_user_by_email(db, user_in.email):
        raise UserAlreadyExistsError("邮箱已存在")

    password_hash = get_password_hash(user_in.password)
    return user_crud.create_user(
        db,
        user_in=user_in,
        password_hash=password_hash,
        role=user_in.role,
        status=user_in.status,
    )


def authenticate_user(db: Session, username: str, password: str) -> User:
    user = user_crud.get_user_by_username(db, username)
    if not user or not verify_password(password, user.password_hash):
        raise InvalidCredentialsError("用户名或密码错误")

    if user.status != "active":
        raise DisabledUserError("用户账号已被禁用")

    return user
