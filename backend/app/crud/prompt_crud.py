from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.prompt_template import PromptTemplate
from app.schemas.prompt import PromptTemplateCreate, PromptTemplateUpdate


def get_prompt_template(db: Session, template_id: int) -> PromptTemplate | None:
    return db.query(PromptTemplate).filter(PromptTemplate.id == template_id).first()


def get_prompt_templates(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    prompt_type: str | None = None,
    status: str | None = None,
    keyword: str | None = None,
) -> tuple[list[PromptTemplate], int]:
    query = db.query(PromptTemplate)

    if prompt_type:
        query = query.filter(PromptTemplate.type == prompt_type)
    if status:
        query = query.filter(PromptTemplate.status == status)
    if keyword:
        pattern = f"%{keyword}%"
        query = query.filter(
            or_(
                PromptTemplate.name.like(pattern),
                PromptTemplate.type.like(pattern),
                PromptTemplate.content.like(pattern),
            )
        )

    total = query.count()
    items = (
        query.order_by(
            PromptTemplate.is_default.desc(),
            PromptTemplate.updated_at.desc(),
            PromptTemplate.id.desc(),
        )
        .offset(skip)
        .limit(limit)
        .all()
    )
    return items, total


def get_active_default_prompt_template(
    db: Session,
    prompt_type: str,
) -> PromptTemplate | None:
    return (
        db.query(PromptTemplate)
        .filter(
            PromptTemplate.type == prompt_type,
            PromptTemplate.status == "enabled",
            PromptTemplate.is_default.is_(True),
        )
        .order_by(PromptTemplate.updated_at.desc(), PromptTemplate.id.desc())
        .first()
    )


def lock_prompt_templates_by_type(
    db: Session,
    prompt_type: str,
) -> list[PromptTemplate]:
    return (
        db.query(PromptTemplate)
        .filter(PromptTemplate.type == prompt_type)
        .with_for_update()
        .all()
    )


def create_prompt_template(
    db: Session,
    item_in: PromptTemplateCreate,
    created_by: int | None,
) -> PromptTemplate:
    db_item = PromptTemplate(
        name=item_in.name,
        type=item_in.type,
        content=item_in.content,
        is_default=item_in.is_default,
        status=item_in.status,
        created_by=created_by,
    )
    db.add(db_item)
    db.flush()
    return db_item


def update_prompt_template(
    db: Session,
    db_item: PromptTemplate,
    item_in: PromptTemplateUpdate,
) -> PromptTemplate:
    update_data = item_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_item, field, value)
    db.add(db_item)
    db.flush()
    return db_item


def delete_prompt_template(db: Session, db_item: PromptTemplate) -> None:
    db.delete(db_item)
    db.flush()
