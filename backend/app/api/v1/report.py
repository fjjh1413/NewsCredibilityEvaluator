from fastapi import APIRouter, Depends, Path, status
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.report import ReportGenerateApiResponse, ReportOut
from app.services.report_service import (
    ReportAccessDeniedError,
    ReportFileMissingError,
    ReportGenerationError,
    ReportNotFoundError,
    generate_detection_report,
    get_report_download_url,
    get_report_pdf_for_download,
)
from app.utils.response import error_response, success_response


router = APIRouter(prefix="/report", tags=["report"])


@router.post(
    "/generate/{detection_id}",
    response_model=ReportGenerateApiResponse,
)
def generate_report(
    detection_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict | JSONResponse:
    try:
        report = generate_detection_report(db, detection_id, current_user)
    except ReportNotFoundError as exc:
        return _error(exc, status.HTTP_404_NOT_FOUND)
    except ReportAccessDeniedError as exc:
        return _error(exc, status.HTTP_403_FORBIDDEN)
    except ReportGenerationError as exc:
        return _error(exc, status.HTTP_500_INTERNAL_SERVER_ERROR)

    data = ReportOut(
        id=report.id,
        detection_id=report.detection_id,
        user_id=report.user_id,
        report_title=report.report_title,
        download_url=get_report_download_url(report),
        created_at=report.created_at,
    ).model_dump(mode="json")
    return success_response(message="报告生成成功", data=data)


@router.get("/download/{report_id}", response_model=None)
def download_report(
    report_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileResponse | JSONResponse:
    try:
        report, pdf_file = get_report_pdf_for_download(db, report_id, current_user)
    except ReportNotFoundError as exc:
        return _error(exc, status.HTTP_404_NOT_FOUND)
    except ReportAccessDeniedError as exc:
        return _error(exc, status.HTTP_403_FORBIDDEN)
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
