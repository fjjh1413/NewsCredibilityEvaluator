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
    vector_sync_status: str | None = None,
    keyword: str | None = None,
) -> tuple[list[KnowledgeItem], int]:
    query = db.query(KnowledgeItem)

    if category:
        query = query.filter(KnowledgeItem.category == category)
    if truth_label:
        query = query.filter(KnowledgeItem.truth_label == truth_label)
    if risk_level:
        query = query.filter(KnowledgeItem.risk_level == risk_level)
    if vector_sync_status:
        query = query.filter(KnowledgeItem.vector_sync_status == vector_sync_status)
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
    auto_commit: bool = True,
) -> KnowledgeItem:
    update_data = item_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_item, field, value)

    db_item.vector_sync_status = "pending"
    db_item.vector_sync_error = None
    db.add(db_item)
    if auto_commit:
        db.commit()
        db.refresh(db_item)
    else:
        db.flush()
    return db_item


def update_knowledge_vector_state(
    db: Session,
    db_item: KnowledgeItem,
    status: str,
    vector_id: str | None = None,
    error: str | None = None,
    auto_commit: bool = True,
) -> KnowledgeItem:
    db_item.vector_sync_status = status
    db_item.vector_sync_error = error
    if vector_id is not None:
        db_item.vector_id = vector_id

    db.add(db_item)
    if auto_commit:
        db.commit()
        db.refresh(db_item)
    else:
        db.flush()
    return db_item


def get_all_knowledge_items(db: Session) -> list[KnowledgeItem]:
    return db.query(KnowledgeItem).order_by(KnowledgeItem.id.asc()).all()


def search_knowledge_items_for_retrieval(
    db: Session,
    tokens: list[str],
    limit: int,
    category: str | None = None,
    truth_label: str | None = None,
    risk_level: str | None = None,
) -> list[KnowledgeItem]:
    query = db.query(KnowledgeItem)

    if category:
        query = query.filter(KnowledgeItem.category == category)
    if truth_label:
        query = query.filter(KnowledgeItem.truth_label == truth_label)
    if risk_level:
        query = query.filter(KnowledgeItem.risk_level == risk_level)

    filters = []
    for token in tokens[:8]:
        pattern = f"%{token}%"
        filters.extend(
            [
                KnowledgeItem.title.like(pattern),
                KnowledgeItem.summary.like(pattern),
                KnowledgeItem.keywords.like(pattern),
                KnowledgeItem.content.like(pattern),
            ]
        )
    if filters:
        query = query.filter(or_(*filters))

    return (
        query.order_by(KnowledgeItem.created_at.desc(), KnowledgeItem.id.desc())
        .limit(limit)
        .all()
    )


def delete_knowledge_item(db: Session, db_item: KnowledgeItem) -> None:
    db.delete(db_item)
    db.commit()
