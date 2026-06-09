from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.models.detection_record import DetectionRecord
from app.models.report import Report
from app.models.user import User


def get_report_by_id(db: Session, report_id: int) -> Report | None:
    return db.query(Report).filter(Report.id == report_id).first()


def get_report_by_detection_id(db: Session, detection_id: int) -> Report | None:
    return db.query(Report).filter(Report.detection_id == detection_id).first()


def get_admin_report_candidates(
    db: Session,
    keyword: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    user_id: int | None = None,
    detection_id: int | None = None,
) -> list[Report]:
    query = (
        db.query(Report)
        .options(joinedload(Report.detection))
        .outerjoin(DetectionRecord, Report.detection_id == DetectionRecord.id)
        .outerjoin(User, Report.user_id == User.id)
    )

    if keyword:
        pattern = f"%{keyword.strip()}%"
        query = query.filter(
            or_(
                Report.report_title.like(pattern),
                DetectionRecord.input_title.like(pattern),
                User.username.like(pattern),
                User.email.like(pattern),
            )
        )
    if start_date:
        query = query.filter(Report.created_at >= start_date)
    if end_date:
        query = query.filter(Report.created_at <= end_date)
    if user_id is not None:
        query = query.filter(Report.user_id == user_id)
    if detection_id is not None:
        query = query.filter(Report.detection_id == detection_id)

    return query.order_by(Report.created_at.desc(), Report.id.desc()).all()


def save_generated_report(
    db: Session,
    detection: DetectionRecord,
    report_title: str,
    html_path: str,
    pdf_path: str,
    api_prefix: str,
) -> tuple[Report, tuple[str | None, str | None]]:
    try:
        report = get_report_by_detection_id(db, detection.id)
        old_paths = (
            (report.html_path, report.pdf_path)
            if report is not None
            else (None, None)
        )
        if report is None:
            report = Report(
                detection_id=detection.id,
                user_id=detection.user_id,
                report_title=report_title,
                html_path=html_path,
                pdf_path=pdf_path,
            )
        else:
            report.user_id = detection.user_id
            report.report_title = report_title
            report.html_path = html_path
            report.pdf_path = pdf_path
            report.created_at = datetime.now()

        db.add(report)
        db.flush()
        detection.report_url = (
            f"{api_prefix.rstrip('/')}/report/download/{report.id}"
        )
        db.add(detection)
        db.commit()
        db.refresh(report)
        return report, old_paths
    except Exception:
        db.rollback()
        raise
