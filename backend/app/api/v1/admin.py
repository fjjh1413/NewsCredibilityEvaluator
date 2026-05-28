from fastapi import APIRouter, Depends

from app.core.deps import get_current_admin
from app.models.user import User
from app.utils.response import success_response


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/ping")
def admin_ping(current_admin: User = Depends(get_current_admin)) -> dict:
    return success_response(
        message="admin pong",
        data={
            "username": current_admin.username,
            "role": current_admin.role,
            "status": "ok",
        },
    )
