from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ReviewStatus = Literal["pending", "approved", "rejected"]


class PublicHighRiskItem(BaseModel):
    id: int
    title: str
    summary: str
    category: str
    final_score: float
    risk_level: str
    keywords: list[str]
    published_at: datetime


class PublicHighRiskListData(BaseModel):
    total: int = Field(..., ge=0)
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1)
    items: list[PublicHighRiskItem]


class PublicHighRiskRankingData(BaseModel):
    items: list[PublicHighRiskItem]


class HighRiskKeywordItem(BaseModel):
    keyword: str
    count: int = Field(..., ge=0)


class HighRiskCategoryItem(BaseModel):
    category: str
    count: int = Field(..., ge=0)


class AdminHighRiskItem(BaseModel):
    id: int
    user_id: int | None = None
    input_title: str
    category: str | None = None
    final_score: float
    risk_level: str
    is_high_risk: bool
    review_status: ReviewStatus
    is_public: bool
    admin_remark: str | None = None
    created_at: datetime
    updated_at: datetime
    reviewed_at: datetime | None = None
    reviewed_by: int | None = None


class AdminHighRiskListData(BaseModel):
    total: int = Field(..., ge=0)
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1)
    items: list[AdminHighRiskItem]


class AdminHighRiskEvidenceItem(BaseModel):
    id: int
    knowledge_id: int | None = None
    title: str
    summary: str | None = None
    source_name: str | None = None
    similarity_score: float
    rank_order: int


class AdminHighRiskDetail(AdminHighRiskItem):
    input_content: str
    keywords: list[str]
    evidence_score: float
    llm_score: float
    rule_score: float
    judgement_result: str
    reason: str | None = None
    risk_points: list[str]
    suggestion: str | None = None
    evidence_matches: list[AdminHighRiskEvidenceItem]


class HighRiskReviewUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_status: ReviewStatus
    admin_remark: str | None = Field(default=None, max_length=2000)

    @field_validator("admin_remark")
    @classmethod
    def normalize_remark(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class HighRiskPublicUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_public: bool


class HighRiskRemarkUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    admin_remark: str | None = Field(default=None, max_length=2000)

    @field_validator("admin_remark")
    @classmethod
    def normalize_remark(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class PublicHighRiskListApiResponse(BaseModel):
    code: int
    message: str
    data: PublicHighRiskListData


class PublicHighRiskRankingApiResponse(BaseModel):
    code: int
    message: str
    data: PublicHighRiskRankingData


class HighRiskKeywordsApiResponse(BaseModel):
    code: int
    message: str
    data: list[HighRiskKeywordItem]


class HighRiskCategoriesApiResponse(BaseModel):
    code: int
    message: str
    data: list[HighRiskCategoryItem]


class AdminHighRiskListApiResponse(BaseModel):
    code: int
    message: str
    data: AdminHighRiskListData


class AdminHighRiskDetailApiResponse(BaseModel):
    code: int
    message: str
    data: AdminHighRiskDetail
