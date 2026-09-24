from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class RagSearchRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    content: str | None = None
    query: str | None = Field(default=None, min_length=1)
    top_k: int = Field(default=10, ge=1, le=50)
    category: str | None = Field(default=None, max_length=50)
    truth_label: str | None = Field(default=None, max_length=30)
    risk_level: str | None = Field(default=None, max_length=30)

    @field_validator("title", "content", "query")
    @classmethod
    def empty_strings_become_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @model_validator(mode="after")
    def require_search_text(self) -> "RagSearchRequest":
        if self.title or self.content or self.query:
            return self
        raise ValueError("title/content or query is required")


class RagSearchItem(BaseModel):
    id: int
    title: str
    summary: str
    category: str
    truth_label: str
    source_name: str
    vector_sync_status: str
    similarity_score: float | None = None
    raw_cosine_score: float | None = None
    fusion_score: float | None = None
    index_version: str | None = None
    parent_revision: str | None = None
    chunks: list[dict[str, Any]] = Field(default_factory=list)
    score_components: dict[str, Any] = Field(default_factory=dict)
    rerank_original_rank: int | None = None
    rule_rerank_score: float | None = None
    model_rerank_score: float | None = None
    model_rerank_reason: str | None = None
    rerank_score: float | None = None
    rerank_stage: str | None = None
    diversity_adjusted_rerank_score: float | None = None
    rerank_order: int | None = None


class RagSearchData(BaseModel):
    query: str
    top_k: int
    results: list[RagSearchItem]
    total: int


class RagSearchApiResponse(BaseModel):
    code: int
    message: str
    data: RagSearchData


class RagAuditItem(BaseModel):
    knowledge_id: int
    title: str | None = None
    expected_chunk_count: int
    actual_chunk_count: int
    issue_count: int
    issues: list[dict[str, Any]] = Field(default_factory=list)


class RagAuditData(BaseModel):
    status: str
    index_version: str | None = None
    total_items: int
    checked_items: int
    sample_limit: int | None = None
    items_with_issues: int
    issue_count: int
    issues_by_type: dict[str, int] = Field(default_factory=dict)
    items: list[RagAuditItem] = Field(default_factory=list)


class RagAuditApiResponse(BaseModel):
    code: int
    message: str
    data: RagAuditData
