from typing import Literal

from pydantic import BaseModel, Field


RiskLevel = Literal["medium", "high", "critical"]


class AdminOperationPolicyItem(BaseModel):
    operation_key: str
    module: str
    action: str
    title: str
    description: str
    risk_level: RiskLevel
    target_type: str
    requires_confirmation: bool
    requires_dual_approval: bool
    audit_event: str
    audit_fields: list[str]
    current_enforcement: list[str]
    next_controls: list[str]
    rollback_hint: str


class AdminOperationPolicyListData(BaseModel):
    total: int = Field(..., ge=0)
    items: list[AdminOperationPolicyItem]


class AdminOperationPolicyListApiResponse(BaseModel):
    code: int
    message: str
    data: AdminOperationPolicyListData
