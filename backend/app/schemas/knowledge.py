from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


VectorSyncStatus = Literal["pending", "synced", "failed", "delete_failed"]


class KnowledgeInputBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)
    category: str | None = Field(default=None, max_length=50)
    truth_label: str = Field(..., min_length=1, max_length=30)
    source_name: str | None = Field(default=None, max_length=100)
    source_url: str | None = Field(default=None, max_length=500)
    publish_time: datetime | None = None
    summary: str | None = None
    keywords: str | None = Field(default=None, max_length=500)
    debunking_explanation: str | None = None
    risk_level: str | None = Field(default=None, max_length=30)
    admin_note: str | None = None

    @field_validator("title", "content")
    @classmethod
    def required_text_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("field cannot be blank")
        return cleaned


class KnowledgeCreate(KnowledgeInputBase):
    pass


class KnowledgeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=255)
    content: str | None = Field(default=None, min_length=1)
    category: str | None = Field(default=None, max_length=50)
    truth_label: str | None = Field(default=None, min_length=1, max_length=30)
    source_name: str | None = Field(default=None, max_length=100)
    source_url: str | None = Field(default=None, max_length=500)
    publish_time: datetime | None = None
    summary: str | None = None
    keywords: str | None = Field(default=None, max_length=500)
    debunking_explanation: str | None = None
    risk_level: str | None = Field(default=None, max_length=30)
    admin_note: str | None = None

    @field_validator("title", "content")
    @classmethod
    def optional_text_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("field cannot be blank")
        return cleaned


class KnowledgeOut(KnowledgeInputBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vector_id: str | None = None
    vector_sync_status: VectorSyncStatus
    vector_sync_error: str | None = None
    created_at: datetime
    updated_at: datetime


class KnowledgeListData(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[KnowledgeOut]


class KnowledgeItemApiResponse(BaseModel):
    code: int
    message: str
    data: KnowledgeOut


class KnowledgeListApiResponse(BaseModel):
    code: int
    message: str
    data: KnowledgeListData


class KnowledgeDeleteData(BaseModel):
    id: int


class KnowledgeDeleteApiResponse(BaseModel):
    code: int
    message: str
    data: KnowledgeDeleteData


class KnowledgeRebuildIndexData(BaseModel):
    total: int
    success: int
    failed: int
    failed_ids: list[int]


class KnowledgeRebuildIndexApiResponse(BaseModel):
    code: int
    message: str
    data: KnowledgeRebuildIndexData
