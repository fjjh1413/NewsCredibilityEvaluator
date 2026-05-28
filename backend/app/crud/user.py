from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.user import UserAdminCreate, UserCreate


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.query(User).filter(User.username == username).first()


def get_user_by_email(db: Session, email: str | None) -> User | None:
    if not email:
        return None
    return db.query(User).filter(User.email == email).first()


def create_user(
    db: Session,
    user_in: UserCreate | UserAdminCreate,
    password_hash: str,
    role: str = "user",
    status: str = "active",
) -> User:
    db_user = User(
        username=user_in.username,
        password_hash=password_hash,
        email=user_in.email,
        role=role,
        status=status,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user
