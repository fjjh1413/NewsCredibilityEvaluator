from typing import Literal

from fastapi import APIRouter, Depends, Query

from app.core.deps import get_current_admin
from app.models.user import User
from app.schemas.admin_operation_policy import AdminOperationPolicyListApiResponse
from app.services.admin_operation_policy_service import list_admin_operation_policies
from app.utils.response import success_response


router = APIRouter(
    prefix="/admin/operation-policies",
    tags=["admin-operation-policies"],
)


@router.get("", response_model=AdminOperationPolicyListApiResponse)
def read_admin_operation_policies(
    risk_level: Literal["medium", "high", "critical"] | None = Query(default=None),
    current_admin: User = Depends(get_current_admin),
) -> dict:
    items = list_admin_operation_policies(risk_level=risk_level)
    return success_response(data={"total": len(items), "items": items})
