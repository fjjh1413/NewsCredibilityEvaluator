from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


PromptTemplateStatus = Literal["enabled", "disabled"]


class PromptTemplateBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=100)
    type: str = Field(..., min_length=1, max_length=50)
    content: str = Field(..., min_length=1)

    @field_validator("name", "type", "content")
    @classmethod
    def required_text_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("field cannot be blank")
        return cleaned


class PromptTemplateCreate(PromptTemplateBase):
    is_default: bool = False
    status: PromptTemplateStatus = "enabled"


class PromptTemplateUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100)
    type: str | None = Field(default=None, min_length=1, max_length=50)
    content: str | None = Field(default=None, min_length=1)
    is_default: bool | None = None
    status: PromptTemplateStatus | None = None

    @field_validator("name", "type", "content")
    @classmethod
    def optional_text_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("field cannot be blank")
        return cleaned


class PromptTemplateOut(PromptTemplateBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_default: bool
    status: PromptTemplateStatus
    created_by: int | None = None
    created_at: datetime
    updated_at: datetime


class PromptTemplateListData(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[PromptTemplateOut]


class PromptTemplateItemApiResponse(BaseModel):
    code: int
    message: str
    data: PromptTemplateOut


class PromptTemplateListApiResponse(BaseModel):
    code: int
    message: str
    data: PromptTemplateListData


class PromptTemplateDeleteData(BaseModel):
    id: int


class PromptTemplateDeleteApiResponse(BaseModel):
    code: int
    message: str
    data: PromptTemplateDeleteData
