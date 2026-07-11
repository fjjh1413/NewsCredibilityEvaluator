from typing import Any

from pydantic import BaseModel, ConfigDict


class AiEngineeringSummaryData(BaseModel):
    model_config = ConfigDict(extra="allow")

    source: dict[str, Any]
    schema_version: str
    generated_at: str | None = None
    metrics: dict[str, Any]
    gate: dict[str, Any]
    per_case: list[dict[str, Any]]


class AiEngineeringSummaryApiResponse(BaseModel):
    code: int
    message: str
    data: AiEngineeringSummaryData
