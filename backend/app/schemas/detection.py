import json
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EvidenceMatchBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    knowledge_id: int | None = None
    title: str = Field(..., min_length=1, max_length=255)
    summary: str | None = None
    source_name: str | None = Field(default=None, max_length=100)
    similarity_score: float = Field(..., ge=0)
    rank_order: int = Field(..., ge=1)

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("title cannot be blank")
        return cleaned


class EvidenceMatchCreate(EvidenceMatchBase):
    pass


class EvidenceMatchOut(EvidenceMatchBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    detection_id: int
    created_at: datetime
    updated_at: datetime


class DetectionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: int | None = None
    input_title: str = Field(..., min_length=1, max_length=255)
    input_content: str = Field(..., min_length=1)
    category: str | None = Field(default=None, max_length=50)
    keywords: str | None = Field(default=None, max_length=500)
    final_score: float = Field(..., ge=0, le=100)
    evidence_score: float = Field(..., ge=0, le=100)
    llm_score: float = Field(..., ge=0, le=100)
    rule_score: float = Field(..., ge=0, le=100)
    risk_level: str = Field(..., min_length=1, max_length=30)
    judgement_result: str = Field(..., min_length=1, max_length=100)
    reason: str | None = None
    risk_points: list[str] = Field(default_factory=list)
    suggestion: str | None = None
    is_high_risk: bool = False
    report_url: str | None = Field(default=None, max_length=500)
    analysis_payload: dict[str, Any] = Field(default_factory=dict)
    evidence_matches: list[EvidenceMatchCreate] = Field(default_factory=list)

    @field_validator("input_title", "input_content", "risk_level", "judgement_result")
    @classmethod
    def required_text_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("field cannot be blank")
        return cleaned

    @field_validator("risk_points", mode="before")
    @classmethod
    def risk_points_accept_json_string(cls, value: Any) -> list[str]:
        return parse_risk_points(value)


class DetectionRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None = None
    input_title: str
    input_content: str
    category: str | None = None
    keywords: str | None = None
    final_score: float
    evidence_score: float
    llm_score: float
    rule_score: float
    risk_level: str
    judgement_result: str
    reason: str | None = None
    risk_points: list[str] = Field(default_factory=list)
    suggestion: str | None = None
    is_high_risk: bool
    report_url: str | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator(
        "final_score",
        "evidence_score",
        "llm_score",
        "rule_score",
        mode="before",
    )
    @classmethod
    def decimal_score_to_float(cls, value: Any) -> float:
        if isinstance(value, Decimal):
            return float(value)
        return value

    @field_validator("risk_points", mode="before")
    @classmethod
    def risk_points_from_storage(cls, value: Any) -> list[str]:
        return parse_risk_points(value)


class DetectionHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None = None
    input_title: str
    final_score: float
    risk_level: str
    is_high_risk: bool
    report_url: str | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator("final_score", mode="before")
    @classmethod
    def decimal_score_to_float(cls, value: Any) -> float:
        if isinstance(value, Decimal):
            return float(value)
        return value


class DetectionDetailOut(DetectionRecordOut):
    evidence_matches: list[EvidenceMatchOut] = Field(default_factory=list)
    candidate_evidence_list: list["DetectEvidenceItem"] = Field(default_factory=list)
    excluded_evidence: list["DetectEvidenceItem"] = Field(default_factory=list)
    similar_news: list["SimilarNewsItem"] = Field(default_factory=list)
    evidence_quality: "EvidenceQualityOut | None" = None
    arbitration_status: str = "unavailable"
    quality_status: str | None = None
    arbitration_error: str | None = None
    arbitration_attempts: int = Field(default=0, ge=0, le=2)
    analysis_contract_version: str | None = None
    knowledge_has_relevant_match: bool = False
    web_has_relevant_match: bool = False
    publish_time: str | None = None
    source_name: str | None = None
    source_url: str | None = None


class DetectionHistoryData(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[DetectionHistoryItem]


class DetectionHistoryApiResponse(BaseModel):
    code: int
    message: str
    data: DetectionHistoryData


class DetectionDetailApiResponse(BaseModel):
    code: int
    message: str
    data: DetectionDetailOut


class DetectionDeleteData(BaseModel):
    id: int


class DetectionDeleteApiResponse(BaseModel):
    code: int
    message: str
    data: DetectionDeleteData


class DetectNewsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)
    category: str | None = Field(default=None, max_length=50)
    source_name: str | None = Field(default=None, max_length=100)
    source_url: str | None = Field(default=None, max_length=2048)
    publish_time: str | None = Field(default=None, max_length=100)
    enable_web_search: bool = Field(default=True, description="是否启用联网检索增强检测")

    @field_validator("title")
    @classmethod
    def title_must_meet_demo_length(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("新闻标题不能为空")
        if len(cleaned) < 4:
            raise ValueError("新闻标题长度不能少于 4 个字符")
        return cleaned

    @field_validator("content")
    @classmethod
    def content_must_meet_demo_length(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("新闻正文不能为空")
        if len(cleaned) < 20:
            raise ValueError("新闻正文长度不能少于 20 个字符")
        return cleaned

    @field_validator("source_name", "source_url", "publish_time", mode="before")
    @classmethod
    def optional_metadata_must_be_clean_text(cls, value: Any) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None


class DetectEvidenceItem(BaseModel):
    knowledge_id: int | None = None
    candidate_id: str | None = None
    title: str
    summary: str | None = None
    category: str | None = None
    truth_label: str | None = None
    source_name: str | None = None
    source_url: str | None = None
    source_type: str | None = None
    source_label: str | None = None
    risk_level: str | None = None
    similarity_score: float | None = None
    rank_order: int | None = None
    # ── LLM arbitration fields ──
    relevance_score: float | None = None
    quality_score: float | None = None
    stance: str | None = None
    arbitration_reason: str | None = None
    rejection_reason: str | None = None
    publish_time: str | None = None


class SimilarNewsItem(BaseModel):
    title: str
    source_name: str | None = None
    source_url: str | None = None
    publish_time: str | None = None
    source_type: str | None = None
    risk_level: str | None = None
    similarity_score: float | None = None
    candidate_id: str | None = None
    rank_order: int | None = None
    relevance_score: float | None = None
    quality_score: float | None = None
    stance: str | None = None
    arbitration_reason: str | None = None
    relevance_reason: str | None = None


class EvidenceQualityOut(BaseModel):
    """LLM-evaluated evidence quality (coverage + consistency)."""

    coverage: float | None = None
    consistency: float | None = None
    score: float | None = None
    assessment: str | None = None


class DetectNewsResult(BaseModel):
    detection_id: int
    created_at: datetime | None = None
    publish_time: str | None = None
    source_name: str | None = None
    source_url: str | None = None
    final_score: float
    evidence_score: float
    llm_score: float
    rule_score: float
    risk_level: str
    judgement_result: str
    reason: str
    risk_points: list[str]
    keywords: list[str]
    evidence_list: list[DetectEvidenceItem]
    candidate_evidence_list: list[DetectEvidenceItem] = Field(default_factory=list)
    excluded_evidence: list[DetectEvidenceItem] = Field(default_factory=list)
    similar_news: list[SimilarNewsItem]
    suggestion: str
    agent_steps: list[str]
    disclaimer: str
    web_search_triggered: bool = False
    web_search_sources: int = 0
    evidence_quality: EvidenceQualityOut | None = None
    arbitration_status: str = "unavailable"
    quality_status: str = "unavailable"
    arbitration_error: str | None = None
    arbitration_attempts: int = Field(default=0, ge=0, le=2)
    analysis_contract_version: str | None = None
    knowledge_has_relevant_match: bool = False
    web_has_relevant_match: bool = False


class DetectNewsApiResponse(BaseModel):
    code: int
    message: str
    data: DetectNewsResult


DetectionTaskStatus = Literal["queued", "running", "succeeded", "failed"]


class DetectionTaskOut(BaseModel):
    task_id: str
    celery_task_id: str | None = None
    status: DetectionTaskStatus
    detection_id: int | None = None
    result: DetectNewsResult | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class DetectionTaskApiResponse(BaseModel):
    code: int
    message: str
    data: DetectionTaskOut


class ExtractPreviewRequest(BaseModel):
    """Request body for the detect-by-link preview/extract endpoint."""

    model_config = ConfigDict(extra="forbid")

    url: str = Field(..., min_length=1, max_length=2048)

    @field_validator("url")
    @classmethod
    def url_must_use_http_scheme(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("链接不能为空")
        if not (cleaned.lower().startswith("http://") or cleaned.lower().startswith("https://")):
            raise ValueError("链接必须以 http:// 或 https:// 开头")
        return cleaned


class ExtractPreviewData(BaseModel):
    """Auto-extracted article fields used to back-fill the detect form."""

    title: str
    content: str
    source_name: str | None = None
    source_url: str | None = None
    publish_time: str | None = None
    publish_time_precision: Literal["date", "datetime"] | None = None

    @model_validator(mode="after")
    def publish_time_must_match_precision(self) -> "ExtractPreviewData":
        if self.publish_time is None:
            if self.publish_time_precision is not None:
                raise ValueError("publish_time_precision requires publish_time")
            return self
        if self.publish_time_precision is None:
            raise ValueError("publish_time requires publish_time_precision")
        try:
            if self.publish_time_precision == "date":
                datetime.strptime(self.publish_time, "%Y-%m-%d")
            else:
                if "T" not in self.publish_time:
                    raise ValueError("datetime publication time must contain T")
                datetime.fromisoformat(self.publish_time.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("publish_time does not match publish_time_precision") from exc
        return self


class ExtractPreviewApiResponse(BaseModel):
    code: int
    message: str
    data: ExtractPreviewData


def parse_risk_points(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return []
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            return [cleaned]
        return parse_risk_points(parsed)
    return [str(value).strip()] if str(value).strip() else []
