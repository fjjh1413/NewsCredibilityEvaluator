from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.crud.user import get_user_by_username
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.schemas.user import UserAdminCreate
from app.services.auth_service import UserAlreadyExistsError, create_admin_user


def _build_superuser_payload() -> UserAdminCreate:
    settings = get_settings()
    if not settings.first_superuser_username:
        raise RuntimeError("FIRST_SUPERUSER_USERNAME is not configured")
    if not settings.first_superuser_password:
        raise RuntimeError("FIRST_SUPERUSER_PASSWORD is not configured")

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
    with SessionLocal() as db:
        created, message = init_db(db)
        status = "created" if created else "skipped"
        print(f"[{status}] {message}")


if __name__ == "__main__":
    main()
