from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_admin
from app.crud.system_log_crud import list_system_logs
from app.db.session import get_db
from app.models.user import User
from app.schemas.system_log import (
    SystemLogListApiResponse,
    SystemLogListData,
    SystemLogOut,
)
from app.utils.response import success_response


router = APIRouter(prefix="/admin/logs", tags=["admin-logs"])


@router.get("", response_model=SystemLogListApiResponse)
def read_admin_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    module: str | None = Query(default=None),
    action: str | None = Query(default=None),
    user_id: int | None = Query(default=None, ge=1),
    keyword: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict:
    rows, total = list_system_logs(
        db,
        page=page,
        page_size=page_size,
        module=module,
        action=action,
        user_id=user_id,
        keyword=keyword,
        date_from=date_from,
        date_to=date_to,
    )
    data = SystemLogListData(
        total=total,
        page=page,
        page_size=page_size,
        items=[
            SystemLogOut(
                id=log.id,
                user_id=log.user_id,
                username=username,
                module=log.module,
                action=log.action,
                description=log.description,
                ip_address=log.ip_address,
                created_at=log.created_at,
            )
            for log, username in rows
        ],
    ).model_dump(mode="json")
    return success_response(data=data)
