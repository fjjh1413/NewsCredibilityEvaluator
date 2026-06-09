from datetime import datetime

from pydantic import BaseModel, Field


class ReportOut(BaseModel):
    id: int
    detection_id: int
    user_id: int | None = None
    report_title: str
    download_url: str
    created_at: datetime


class ReportGenerateApiResponse(BaseModel):
    code: int
    message: str
    data: ReportOut


class AdminReportItem(BaseModel):
    report_id: int
    detection_id: int
    user_id: int | None = None
    username: str | None = None
    news_title: str
    risk_level: str | None = None
    final_score: float | None = None
    file_name: str | None = None
    file_size: int | None = None
    status: str
    download_url: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class AdminReportListData(BaseModel):
    total: int = Field(..., ge=0)
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1)
    items: list[AdminReportItem]


class AdminReportDetail(AdminReportItem):
    report_title: str
    news_summary: str
    report_path: str | None = None


class AdminReportListApiResponse(BaseModel):
    code: int
    message: str
    data: AdminReportListData


class AdminReportDetailApiResponse(BaseModel):
    code: int
    message: str
    data: AdminReportDetail
