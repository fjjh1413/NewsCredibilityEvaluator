from datetime import datetime

from fastapi import APIRouter, Depends, Path, Query, Request, status
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_admin
from app.db.session import get_db
from app.models.user import User
from app.schemas.report import (
    AdminReportDetailApiResponse,
    AdminReportListApiResponse,
)
from app.services.report_service import (
    ReportFileMissingError,
    ReportNotFoundError,
    delete_admin_report_record,
    get_admin_report_detail,
    get_report_pdf_for_download,
    list_admin_reports,
)
from app.services.system_log_service import get_request_ip, record_system_log
from app.utils.response import error_response, success_response


router = APIRouter(prefix="/admin/reports", tags=["admin-reports"])


@router.get("", response_model=AdminReportListApiResponse)
def read_admin_reports(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = Query(default=None),
    status: str | None = Query(default=None),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    user_id: int | None = Query(default=None, ge=1),
    detection_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict:
    data = list_admin_reports(
        db,
        page=page,
        page_size=page_size,
        keyword=keyword,
        status=status,
        start_date=start_date,
        end_date=end_date,
        user_id=user_id,
        detection_id=detection_id,
    )
    return success_response(data=data)


@router.get("/{report_id}", response_model=AdminReportDetailApiResponse)
def read_admin_report_detail(
    report_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict | JSONResponse:
    try:
        data = get_admin_report_detail(db, report_id)
    except ReportNotFoundError as exc:
        return _error(exc, status.HTTP_404_NOT_FOUND)
    return success_response(data=data)


@router.delete("/{report_id}", response_model=None)
def delete_admin_report(
    request: Request,
    report_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict | JSONResponse:
    try:
        deleted_id = delete_admin_report_record(db, report_id)
    except ReportNotFoundError as exc:
        return _error(exc, status.HTTP_404_NOT_FOUND)

    record_system_log(
        db,
        user_id=current_admin.id,
        module="report",
        action="delete",
        description=f"Admin deleted report report_id={deleted_id}",
        ip_address=get_request_ip(request),
        target_type="report",
        target_id=deleted_id,
        result_status="success",
    )
    return success_response(message="deleted", data={"id": deleted_id})


@router.get("/{report_id}/download", response_model=None)
def download_admin_report(
    report_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> FileResponse | JSONResponse:
    try:
        report, pdf_file = get_report_pdf_for_download(db, report_id, current_admin)
    except ReportNotFoundError as exc:
        return _error(exc, status.HTTP_404_NOT_FOUND)
    except ReportFileMissingError as exc:
        return _error(exc, status.HTTP_404_NOT_FOUND)

    return FileResponse(
        path=pdf_file,
        media_type="application/pdf",
        filename=f"news-credibility-report-{report.id}.pdf",
    )


def _error(exc: Exception, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=error_response(str(exc), code=status_code),
    )
