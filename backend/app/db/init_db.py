from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.crud.user import get_user_by_username
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.schemas.user import UserAdminCreate
from app.services.auth_service import UserAlreadyExistsError, create_admin_user


def _build_superuser_payload() -> UserAdminCreate:
    settings = get_settings()
    if not settings.first_superuser_username:
        raise RuntimeError(
            "FIRST_SUPERUSER_USERNAME 未配置，请在 backend/.env 中设置管理员账号。"
        )
    if not settings.first_superuser_password:
        raise RuntimeError(
            "FIRST_SUPERUSER_PASSWORD 未配置，请在 backend/.env 中设置管理员密码。"
        )

    return UserAdminCreate(
        username=settings.first_superuser_username,
        password=settings.first_superuser_password,
        email=settings.first_superuser_email or None,
        role="admin",
        status="active",
    )


def init_db(db: Session) -> tuple[bool, str]:
    Base.metadata.create_all(bind=engine)

    superuser = _build_superuser_payload()
    existing_user = get_user_by_username(db, superuser.username)
    if existing_user:
        return False, f"Admin user already exists: {existing_user.username}"

    try:
        user = create_admin_user(db, superuser)
    except UserAlreadyExistsError as exc:
        raise RuntimeError(str(exc)) from exc

    return True, f"Admin user created: {user.username}"


def main() -> None:
    try:
        with SessionLocal() as db:
            created, message = init_db(db)
            status = "created" if created else "skipped"
            print(f"[{status}] {message}")
    except SQLAlchemyError as exc:
        settings = get_settings()
        if not settings.env_file_exists:
            print(
                "[error] backend/.env 不存在。请先执行 "
                "`Copy-Item .env.example .env`，再填写 MySQL 连接信息。"
            )
        else:
            print(
                "[error] 数据库初始化失败。请检查 MySQL 是否启动、"
                "backend/.env 中的 DATABASE_URL 或 DATABASE_* 是否正确，"
                "以及数据库是否已创建。"
            )
        raise SystemExit(1) from exc
    except RuntimeError as exc:
        print(f"[error] {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
