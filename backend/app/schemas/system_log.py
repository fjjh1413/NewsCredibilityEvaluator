from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SystemLogCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: int | None = None
    module: str = Field(..., min_length=1, max_length=100)
    action: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    ip_address: str | None = Field(default=None, max_length=50)

    @field_validator("module", "action")
    @classmethod
    def required_text_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("field cannot be blank")
        return cleaned

    @field_validator("description", "ip_address")
    @classmethod
    def optional_text_must_be_clean(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class SystemLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None = None
    username: str | None = None
    module: str
    action: str
    description: str | None = None
    ip_address: str | None = None
    created_at: datetime


class SystemLogListData(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[SystemLogOut]


class SystemLogListApiResponse(BaseModel):
    code: int
    message: str
    data: SystemLogListData
