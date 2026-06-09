import logging

from sqlalchemy.orm import Session

from app.crud import prompt_crud
from app.models.prompt_template import PromptTemplate
from app.schemas.prompt import PromptTemplateCreate, PromptTemplateUpdate
from app.services.prompt_template_validator import (
    NEWS_CREDIBILITY_PROMPT_TYPE,
    PromptTemplateValidationError,
    validate_prompt_template_content,
)
from app.utils.text_cleaner import clean_text


logger = logging.getLogger(__name__)

NO_ENABLED_DEFAULT_PROMPT_FALLBACK_LOG = (
    "No enabled default prompt template found, fallback to built-in prompt."
)
INVALID_DEFAULT_PROMPT_FALLBACK_LOG = (
    "Default prompt template validation failed, fallback to built-in prompt."
)

class PromptTemplateServiceError(Exception):
    """Base exception for Prompt template management failures."""


class PromptTemplateNotFoundError(PromptTemplateServiceError):
    pass


class PromptTemplateDisabledError(PromptTemplateServiceError):
    pass


class PromptTemplateDefaultDeleteError(PromptTemplateServiceError):
    pass


def list_prompt_templates(
    db: Session,
    page: int,
    page_size: int,
    prompt_type: str | None = None,
    status: str | None = None,
    keyword: str | None = None,
) -> tuple[list[PromptTemplate], int]:
    skip = (page - 1) * page_size
    return prompt_crud.get_prompt_templates(
        db,
        skip=skip,
        limit=page_size,
        prompt_type=prompt_type,
        status=status,
        keyword=keyword,
    )


def get_prompt_template(db: Session, template_id: int) -> PromptTemplate:
    template = prompt_crud.get_prompt_template(db, template_id)
    if template is None:
        raise PromptTemplateNotFoundError("Prompt template not found")
    return template


def create_prompt_template(
    db: Session,
    item_in: PromptTemplateCreate,
    created_by: int | None,
) -> PromptTemplate:
    validate_prompt_template_content(item_in.type, item_in.content)
    if item_in.is_default and item_in.status != "enabled":
        raise PromptTemplateDisabledError("Disabled Prompt template cannot be set as default")

    try:
        if item_in.is_default:
            _clear_type_defaults(db, item_in.type)
        template = prompt_crud.create_prompt_template(db, item_in, created_by)
        db.commit()
        db.refresh(template)
        return template
    except Exception:
        db.rollback()
        raise


def update_prompt_template(
    db: Session,
    template_id: int,
    item_in: PromptTemplateUpdate,
) -> PromptTemplate:
    template = get_prompt_template(db, template_id)
    update_data = item_in.model_dump(exclude_unset=True)
    next_type = update_data.get("type", template.type)
    next_content = update_data.get("content", template.content)
    next_status = update_data.get("status", template.status)
    next_is_default = update_data.get("is_default", template.is_default)

    if next_status == "disabled":
        if update_data.get("is_default") is True:
            raise PromptTemplateDisabledError("Disabled Prompt template cannot be set as default")
        update_data["is_default"] = False
        next_is_default = False

    should_validate_content = (
        next_type == NEWS_CREDIBILITY_PROMPT_TYPE
        and (
            "content" in update_data
            or "type" in update_data
            or next_status == "enabled"
            or next_is_default
        )
    )
    if should_validate_content:
        validate_prompt_template_content(next_type, next_content)

    try:
        if next_is_default:
            _clear_type_defaults(db, next_type, keep_id=template.id)
            update_data["is_default"] = True

        updated = prompt_crud.update_prompt_template(
            db,
            template,
            PromptTemplateUpdate(**update_data),
        )
        db.commit()
        db.refresh(updated)
        return updated
    except Exception:
        db.rollback()
        raise


def enable_prompt_template(db: Session, template_id: int) -> PromptTemplate:
    return update_prompt_template(
        db,
        template_id,
        PromptTemplateUpdate(status="enabled"),
    )


def disable_prompt_template(db: Session, template_id: int) -> PromptTemplate:
    return update_prompt_template(
        db,
        template_id,
        PromptTemplateUpdate(status="disabled", is_default=False),
    )


def set_default_prompt_template(db: Session, template_id: int) -> PromptTemplate:
    template = get_prompt_template(db, template_id)
    if template.status != "enabled":
        raise PromptTemplateDisabledError("Disabled Prompt template cannot be set as default")
    validate_prompt_template_content(template.type, template.content)

    try:
        _clear_type_defaults(db, template.type, keep_id=template.id)
        updated = prompt_crud.update_prompt_template(
            db,
            template,
            PromptTemplateUpdate(is_default=True),
        )
        db.commit()
        db.refresh(updated)
        return updated
    except Exception:
        db.rollback()
        raise


def delete_prompt_template(db: Session, template_id: int) -> None:
    template = get_prompt_template(db, template_id)
    if template.is_default:
        raise PromptTemplateDefaultDeleteError(
            "Default Prompt template cannot be deleted; set another default or disable it first"
        )

    try:
        prompt_crud.delete_prompt_template(db, template)
        db.commit()
    except Exception:
        db.rollback()
        raise


def get_default_prompt_content(
    db: Session,
    prompt_type: str = NEWS_CREDIBILITY_PROMPT_TYPE,
) -> str:
    """Return an enabled default template, or an empty string for the code fallback."""

    try:
        template = prompt_crud.get_active_default_prompt_template(db, prompt_type)
    except Exception:
        logger.exception(
            "Failed to read default Prompt template for type=%s, fallback to built-in prompt.",
            prompt_type,
        )
        return ""

    if template is None:
        logger.warning("%s type=%s", NO_ENABLED_DEFAULT_PROMPT_FALLBACK_LOG, prompt_type)
        return ""

    content = getattr(template, "content", None)
    if not isinstance(content, str):
        logger.error(
            "Default prompt template content is not text, fallback to built-in prompt. id=%s type=%s",
            getattr(template, "id", None),
            prompt_type,
        )
        return ""
    cleaned_content = clean_text(content, max_length=None)
    try:
        return validate_prompt_template_content(prompt_type, cleaned_content)
    except PromptTemplateValidationError as exc:
        logger.error(
            "%s id=%s type=%s: %s",
            INVALID_DEFAULT_PROMPT_FALLBACK_LOG,
            getattr(template, "id", None),
            prompt_type,
            exc,
        )
        return ""


def _clear_type_defaults(
    db: Session,
    prompt_type: str,
    keep_id: int | None = None,
) -> None:
    templates = prompt_crud.lock_prompt_templates_by_type(db, prompt_type)
    for template in templates:
        if keep_id is not None and int(template.id) == int(keep_id):
            continue
        if template.is_default:
            template.is_default = False
            db.add(template)
    db.flush()
