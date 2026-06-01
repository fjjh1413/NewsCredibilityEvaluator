from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.knowledge_item import KnowledgeItem
from app.schemas.knowledge import KnowledgeCreate, KnowledgeUpdate


def get_knowledge_item(db: Session, item_id: int) -> KnowledgeItem | None:
    return db.query(KnowledgeItem).filter(KnowledgeItem.id == item_id).first()


def get_knowledge_items(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    category: str | None = None,
    truth_label: str | None = None,
    risk_level: str | None = None,
    keyword: str | None = None,
) -> tuple[list[KnowledgeItem], int]:
    query = db.query(KnowledgeItem)

    if category:
        query = query.filter(KnowledgeItem.category == category)
    if truth_label:
        query = query.filter(KnowledgeItem.truth_label == truth_label)
    if risk_level:
        query = query.filter(KnowledgeItem.risk_level == risk_level)
    if keyword:
        keyword_pattern = f"%{keyword}%"
        query = query.filter(
            or_(
                KnowledgeItem.title.like(keyword_pattern),
                KnowledgeItem.content.like(keyword_pattern),
                KnowledgeItem.summary.like(keyword_pattern),
                KnowledgeItem.keywords.like(keyword_pattern),
            )
        )

    total = query.count()
    items = (
        query.order_by(KnowledgeItem.created_at.desc(), KnowledgeItem.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return items, total


def create_knowledge_item(
    db: Session,
    item_in: KnowledgeCreate,
) -> KnowledgeItem:
    db_item = KnowledgeItem(
        **item_in.model_dump(),
        vector_id=None,
        vector_sync_status="pending",
        vector_sync_error=None,
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


def update_knowledge_item(
    db: Session,
    db_item: KnowledgeItem,
    item_in: KnowledgeUpdate,
) -> KnowledgeItem:
    update_data = item_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_item, field, value)

    db_item.vector_sync_status = "pending"
    db_item.vector_sync_error = None
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


def update_knowledge_vector_state(
    db: Session,
    db_item: KnowledgeItem,
    status: str,
    vector_id: str | None = None,
    error: str | None = None,
) -> KnowledgeItem:
    db_item.vector_sync_status = status
    db_item.vector_sync_error = error
    if vector_id is not None:
        db_item.vector_id = vector_id

    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


def get_all_knowledge_items(db: Session) -> list[KnowledgeItem]:
    return db.query(KnowledgeItem).order_by(KnowledgeItem.id.asc()).all()


def delete_knowledge_item(db: Session, db_item: KnowledgeItem) -> None:
    db.delete(db_item)
    db.commit()
