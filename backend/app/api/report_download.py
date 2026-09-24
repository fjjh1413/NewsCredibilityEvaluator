from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import status
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from app.models.report import Report
from app.services.report_service import (
    ReportAccessDeniedError,
    ReportFileMissingError,
    ReportNotFoundError,
)
from app.utils.response import error_response


ReportPdfLoader = Callable[[Session, int, Any], tuple[Report, Path]]


def build_report_pdf_download_response(
    *,
    db: Session,
    report_id: int,
    current_user: Any,
    load_report_pdf: ReportPdfLoader,
) -> FileResponse | JSONResponse:
    try:
        report, pdf_file = load_report_pdf(db, report_id, current_user)
    except ReportNotFoundError as exc:
        return _download_error(exc, status.HTTP_404_NOT_FOUND)
    except ReportAccessDeniedError as exc:
        return _download_error(exc, status.HTTP_403_FORBIDDEN)
    except ReportFileMissingError as exc:
        return _download_error(exc, status.HTTP_404_NOT_FOUND)

    return FileResponse(
        path=pdf_file,
        media_type="application/pdf",
        filename=f"news-credibility-report-{report.id}.pdf",
    )


def _download_error(exc: Exception, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=error_response(str(exc), code=status_code),
    )
