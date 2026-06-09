from pydantic import BaseModel, Field


class StatisticsOverviewData(BaseModel):
    total_detections: int = Field(..., ge=0)
    today_detections: int = Field(..., ge=0)
    total_users: int = Field(..., ge=0)
    total_knowledge: int = Field(..., ge=0)
    total_high_risk: int = Field(..., ge=0)
    total_reports: int = Field(..., ge=0)


class StatisticsNameValueItem(BaseModel):
    name: str
    value: int = Field(..., ge=0)


class StatisticsKeywordItem(BaseModel):
    keyword: str
    count: int = Field(..., ge=0)


class DetectionTrendData(BaseModel):
    dates: list[str]
    counts: list[int]


class UserActivityData(BaseModel):
    dates: list[str]
    active_users: list[int]


class KnowledgeOverviewData(BaseModel):
    total_knowledge: int = Field(..., ge=0)
    category_distribution: list[StatisticsNameValueItem]
    truth_label_distribution: list[StatisticsNameValueItem]
    vector_status_distribution: list[StatisticsNameValueItem]


class StatisticsOverviewApiResponse(BaseModel):
    code: int
    message: str
    data: StatisticsOverviewData


class StatisticsDistributionApiResponse(BaseModel):
    code: int
    message: str
    data: list[StatisticsNameValueItem]


class StatisticsKeywordsApiResponse(BaseModel):
    code: int
    message: str
    data: list[StatisticsKeywordItem]


class DetectionTrendApiResponse(BaseModel):
    code: int
    message: str
    data: DetectionTrendData


class UserActivityApiResponse(BaseModel):
    code: int
    message: str
    data: UserActivityData


class KnowledgeOverviewApiResponse(BaseModel):
    code: int
    message: str
    data: KnowledgeOverviewData
