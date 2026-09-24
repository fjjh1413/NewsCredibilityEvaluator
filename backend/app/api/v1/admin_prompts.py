from fastapi import APIRouter, Depends, Path, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_admin
from app.db.session import get_db
from app.models.user import User
from app.schemas.prompt import (
    PromptTemplateCreate,
    PromptTemplateDeleteApiResponse,
    PromptTemplateItemApiResponse,
    PromptTemplateListApiResponse,
    PromptTemplateListData,
    PromptTemplateOut,
    PromptTemplateUpdate,
)
from app.services.prompt_service import (
    PromptTemplateDefaultDeleteError,
    PromptTemplateDisabledError,
    PromptTemplateNotFoundError,
    create_prompt_template,
    delete_prompt_template,
    disable_prompt_template,
    enable_prompt_template,
    get_prompt_template,
    list_prompt_templates,
    set_default_prompt_template,
    update_prompt_template,
)
from app.services.prompt_template_validator import PromptTemplateValidationError
from app.services.system_log_service import get_request_ip, record_system_log
from app.utils.response import error_response, success_response


router = APIRouter(prefix="/admin/prompts", tags=["admin-prompts"])


@router.get("", response_model=PromptTemplateListApiResponse)
def read_prompt_templates(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    prompt_type: str | None = Query(default=None, alias="type"),
    status_value: str | None = Query(default=None, alias="status"),
    keyword: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict:
    items, total = list_prompt_templates(
        db,
        page=page,
        page_size=page_size,
        prompt_type=prompt_type,
        status=status_value,
        keyword=keyword,
    )
    data = PromptTemplateListData(
        total=total,
        page=page,
        page_size=page_size,
        items=[PromptTemplateOut.model_validate(item) for item in items],
    ).model_dump(mode="json")
    return success_response(data=data)


@router.get("/{id}", response_model=PromptTemplateItemApiResponse)
def read_prompt_template(
    id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict | JSONResponse:
    try:
        template = get_prompt_template(db, id)
    except PromptTemplateNotFoundError as exc:
        return _not_found(exc)
    return _item_response(template)


@router.post("", response_model=PromptTemplateItemApiResponse, status_code=201)
def create_prompt(
    payload: PromptTemplateCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict | JSONResponse:
    try:
        template = create_prompt_template(db, payload, created_by=current_admin.id)
    except PromptTemplateValidationError as exc:
        return _unprocessable(exc)
    except PromptTemplateDisabledError as exc:
        return _conflict(exc)
    record_system_log(
        db,
        user_id=current_admin.id,
        module="prompt",
        action="create",
        description=f"管理员新增 Prompt template_id={template.id} type={template.type}",
        ip_address=get_request_ip(request),
        target_type="prompt_template",
        target_id=template.id,
        result_status="success",
        metadata_json={"type": template.type},
    )
    return _item_response(template, message="created", code=201)


@router.put("/{id}", response_model=PromptTemplateItemApiResponse)
def update_prompt(
    payload: PromptTemplateUpdate,
    request: Request,
    id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict | JSONResponse:
    try:
        template = update_prompt_template(db, id, payload)
    except PromptTemplateNotFoundError as exc:
        return _not_found(exc)
    except PromptTemplateValidationError as exc:
        return _unprocessable(exc)
    except PromptTemplateDisabledError as exc:
        return _conflict(exc)
    record_system_log(
        db,
        user_id=current_admin.id,
        module="prompt",
        action="update",
        description=f"管理员更新 Prompt template_id={id} type={template.type}",
        ip_address=get_request_ip(request),
        target_type="prompt_template",
        target_id=id,
        result_status="success",
        metadata_json={"type": template.type},
    )
    return _item_response(template, message="updated")


@router.delete("/{id}", response_model=PromptTemplateDeleteApiResponse)
def delete_prompt(
    request: Request,
    id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict | JSONResponse:
    try:
        delete_prompt_template(db, id)
    except PromptTemplateNotFoundError as exc:
        return _not_found(exc)
    except PromptTemplateDefaultDeleteError as exc:
        return _conflict(exc)
    record_system_log(
        db,
        user_id=current_admin.id,
        module="prompt",
        action="delete",
        description=f"管理员删除 Prompt template_id={id}",
        ip_address=get_request_ip(request),
        target_type="prompt_template",
        target_id=id,
        result_status="success",
    )
    return success_response(message="deleted", data={"id": id})


@router.post("/{id}/enable", response_model=PromptTemplateItemApiResponse)
def enable_prompt(
    request: Request,
    id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict | JSONResponse:
    try:
        template = enable_prompt_template(db, id)
    except PromptTemplateNotFoundError as exc:
        return _not_found(exc)
    except PromptTemplateValidationError as exc:
        return _unprocessable(exc)
    record_system_log(
        db,
        user_id=current_admin.id,
        module="prompt",
        action="enable",
        description=f"管理员启用 Prompt template_id={id} type={template.type}",
        ip_address=get_request_ip(request),
        target_type="prompt_template",
        target_id=id,
        result_status="success",
        metadata_json={"type": template.type},
    )
    return _item_response(template, message="enabled")


@router.post("/{id}/disable", response_model=PromptTemplateItemApiResponse)
def disable_prompt(
    request: Request,
    id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict | JSONResponse:
    try:
        template = disable_prompt_template(db, id)
    except PromptTemplateNotFoundError as exc:
        return _not_found(exc)
    record_system_log(
        db,
        user_id=current_admin.id,
        module="prompt",
        action="disable",
        description=f"管理员禁用 Prompt template_id={id} type={template.type}",
        ip_address=get_request_ip(request),
        target_type="prompt_template",
        target_id=id,
        result_status="success",
        metadata_json={"type": template.type},
    )
    return _item_response(template, message="disabled")


@router.post("/{id}/set-default", response_model=PromptTemplateItemApiResponse)
def set_default_prompt(
    request: Request,
    id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict | JSONResponse:
    try:
        template = set_default_prompt_template(db, id)
    except PromptTemplateNotFoundError as exc:
        return _not_found(exc)
    except PromptTemplateValidationError as exc:
        return _unprocessable(exc)
    except PromptTemplateDisabledError as exc:
        return _conflict(exc)
    record_system_log(
        db,
        user_id=current_admin.id,
        module="prompt",
        action="set_default",
        description=f"管理员设置默认 Prompt template_id={id} type={template.type}",
        ip_address=get_request_ip(request),
        target_type="prompt_template",
        target_id=id,
        result_status="success",
        metadata_json={"type": template.type},
    )
    return _item_response(template, message="default updated")


def _item_response(template: object, message: str = "success", code: int = 200) -> dict:
    data = PromptTemplateOut.model_validate(template).model_dump(mode="json")
    return success_response(data=data, message=message, code=code)


def _not_found(exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=error_response(str(exc), code=404),
    )


def _conflict(exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content=error_response(str(exc), code=409),
    )


def _unprocessable(exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=error_response(str(exc), code=422),
    )
