from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.detection_record import DetectionRecord
from app.models.user import User
from app.schemas.user import UserAdminCreate, UserCreate


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_id_for_update(db: Session, user_id: int) -> User | None:
    return (
        db.query(User)
        .filter(User.id == user_id)
        .with_for_update()
        .first()
    )


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


def get_users_with_detection_counts(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    keyword: str | None = None,
    role: str | None = None,
    status: str | None = None,
) -> tuple[list[tuple[User, int]], int]:
    detection_counts = (
        db.query(
            DetectionRecord.user_id.label("user_id"),
            func.count(DetectionRecord.id).label("detection_count"),
        )
        .group_by(DetectionRecord.user_id)
        .subquery()
    )
    query = (
        db.query(
            User,
            func.coalesce(detection_counts.c.detection_count, 0).label(
                "detection_count"
            ),
        )
        .outerjoin(detection_counts, detection_counts.c.user_id == User.id)
    )

    if keyword:
        pattern = f"%{keyword}%"
        query = query.filter(
            or_(
                User.username.like(pattern),
                User.email.like(pattern),
            )
        )
    if role:
        query = query.filter(User.role == role)
    if status:
        query = query.filter(User.status == status)

    total = query.count()
    rows = (
        query.order_by(User.created_at.desc(), User.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [(user, int(detection_count or 0)) for user, detection_count in rows], total


def get_user_with_detection_count(
    db: Session,
    user_id: int,
) -> tuple[User, int] | None:
    detection_count = (
        db.query(func.count(DetectionRecord.id))
        .filter(DetectionRecord.user_id == user_id)
        .scalar()
    )
    user = get_user_by_id(db, user_id)
    if user is None:
        return None
    return user, int(detection_count or 0)


def lock_admin_users(db: Session) -> list[User]:
    return (
        db.query(User)
        .filter(User.role == "admin")
        .with_for_update()
        .all()
    )
