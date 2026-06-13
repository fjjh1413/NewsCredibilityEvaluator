import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.crud.detection_crud import get_detection_record_by_id
from app.crud.report_crud import (
    get_admin_report_candidates,
    get_report_by_id,
    save_generated_report,
)
from app.crud.user import get_user_by_id
from app.models.detection_record import DetectionRecord
from app.models.report import Report
from app.schemas.detection import parse_risk_points


logger = logging.getLogger(__name__)

REPORT_TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates" / "reports"
REPORT_TEMPLATE_NAME = "detection_report.html"
REPORT_FILE_NAME_PATTERN = re.compile(r"^report_[0-9a-f]{32}\.(?:pdf|html)$")
NEWS_SUMMARY_MAX_LENGTH = 240
REPORT_DISCLAIMER = (
    "本报告由智闻辨真系统基于已有检测记录与检索证据自动生成，仅用于辅助判断，"
    "不能替代人工事实核查、权威机构结论或专业法律意见。"
)


class ReportServiceError(Exception):
    """Base exception for report generation and download failures."""


class ReportNotFoundError(ReportServiceError):
    pass


class ReportAccessDeniedError(ReportServiceError):
    pass


class ReportGenerationError(ReportServiceError):
    pass


class ReportFileMissingError(ReportServiceError):
    pass


def list_admin_reports(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
    status: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    user_id: int | None = None,
    detection_id: int | None = None,
) -> dict[str, Any]:
    safe_page = max(page, 1)
    safe_page_size = max(1, min(page_size, 100))
    normalized_status = status.strip().lower() if status else None
    candidates = get_admin_report_candidates(
        db,
        keyword=keyword,
        start_date=start_date,
        end_date=end_date,
        user_id=user_id,
        detection_id=detection_id,
    )
    items = [_build_admin_report_item(db, report) for report in candidates]
    if normalized_status:
        items = [item for item in items if item["status"] == normalized_status]

    total = len(items)
    start = (safe_page - 1) * safe_page_size
    end = start + safe_page_size
    return {
        "total": total,
        "page": safe_page,
        "page_size": safe_page_size,
        "items": items[start:end],
    }


def get_admin_report_detail(db: Session, report_id: int) -> dict[str, Any]:
    report = get_report_by_id(db, report_id)
    if report is None:
        raise ReportNotFoundError("报告不存在")

    data = _build_admin_report_item(db, report)
    detection = _get_report_detection(db, report)
    data.update(
        {
            "report_title": report.report_title,
            "news_summary": build_news_summary(detection),
            "report_path": report.pdf_path,
        }
    )
    return data


def generate_detection_report(
    db: Session,
    detection_id: int,
    current_user: Any,
) -> Report:
    detection = get_detection_record_by_id(db, detection_id)
    if detection is None:
        raise ReportNotFoundError("检测记录不存在")
    _ensure_owner_or_admin(detection.user_id, current_user)

    owner = (
        get_user_by_id(db, detection.user_id)
        if detection.user_id is not None
        else None
    )
    context = _build_report_context(detection, owner)
    report_title = f"新闻可信度检测报告 - {detection.input_title}"[:255]
    settings = get_settings()
    report_root = Path(settings.report_path)
    report_dir = report_root / f"detection_{detection.id}"
    file_stem = f"report_{uuid4().hex}"
    html_file = report_dir / f"{file_stem}.html"
    pdf_file = report_dir / f"{file_stem}.pdf"

    try:
        report_dir.mkdir(parents=True, exist_ok=True)
        html_content = _render_report_html(context)
        html_file.write_text(html_content, encoding="utf-8")
        _convert_html_to_pdf(html_content, pdf_file)
        report, old_paths = save_generated_report(
            db=db,
            detection=detection,
            report_title=report_title,
            html_path=html_file.relative_to(report_root).as_posix(),
            pdf_path=pdf_file.relative_to(report_root).as_posix(),
            api_prefix=settings.api_prefix,
        )
    except ReportServiceError:
        _remove_files(html_file, pdf_file)
        raise
    except Exception as exc:
        _remove_files(html_file, pdf_file)
        logger.exception("Failed to generate report for detection %s", detection_id)
        raise ReportGenerationError(f"PDF 报告生成失败：{exc}") from exc

    _remove_stored_files(report_root, old_paths)
    return report


def get_report_pdf_for_download(
    db: Session,
    report_id: int,
    current_user: Any,
) -> tuple[Report, Path]:
    report = get_report_by_id(db, report_id)
    if report is None:
        raise ReportNotFoundError("报告不存在")
    _ensure_owner_or_admin(report.user_id, current_user)
    if not report.pdf_path:
        raise ReportFileMissingError("报告尚未生成 PDF 文件")

    pdf_file = _resolve_stored_path(Path(get_settings().report_path), report.pdf_path)
    if not pdf_file.is_file():
        raise ReportFileMissingError("PDF 报告文件不存在，请重新生成")
    return report, pdf_file


def get_report_download_url(report: Report) -> str:
    return f"{get_settings().api_prefix.rstrip('/')}/report/download/{report.id}"


def get_admin_report_download_url(report: Report) -> str:
    return f"{get_settings().api_prefix.rstrip('/')}/admin/reports/{report.id}/download"


def build_news_summary(
    detection: DetectionRecord | None,
    max_length: int = NEWS_SUMMARY_MAX_LENGTH,
) -> str:
    source = ""
    if detection is not None:
        source = (
            getattr(detection, "summary", None)
            or getattr(detection, "news_summary", None)
            or getattr(detection, "input_summary", None)
            or getattr(detection, "input_content", None)
            or ""
        )
    text = re.sub(r"\s+", " ", str(source)).strip()
    if not text:
        return "暂无摘要"
    if len(text) <= max_length:
        return text
    return f"{text[:max_length].rstrip()}..."


def _render_report_html(context: dict[str, Any]) -> str:
    try:
        environment = Environment(
            loader=FileSystemLoader(str(REPORT_TEMPLATE_DIR)),
            autoescape=select_autoescape(("html", "xml")),
        )
        template = environment.get_template(REPORT_TEMPLATE_NAME)
        return template.render(**context)
    except Exception as exc:
        raise ReportGenerationError(f"HTML 报告模板渲染失败：{exc}") from exc


def _convert_html_to_pdf(html_content: str, pdf_file: Path) -> None:
    try:
        from xhtml2pdf import pisa
    except ImportError as exc:
        raise ReportGenerationError(
            "PDF 生成依赖未安装，请执行 pip install -r requirements.txt"
        ) from exc

    try:
        with pdf_file.open("wb") as target:
            result = pisa.CreatePDF(
                src=html_content,
                dest=target,
                encoding="utf-8",
            )
    except Exception as exc:
        raise ReportGenerationError(f"HTML 转换 PDF 失败：{exc}") from exc
    if result.err:
        raise ReportGenerationError("HTML 转换 PDF 失败，请检查报告模板和字体配置")


def _build_report_context(
    detection: DetectionRecord,
    owner: Any | None,
) -> dict[str, Any]:
    evidence_items = [
        {
            "rank_order": evidence.rank_order,
            "title": evidence.title,
            "summary": evidence.summary,
            "source_name": evidence.source_name,
            "similarity": _format_similarity(evidence.similarity_score),
        }
        for evidence in detection.evidence_matches
    ]
    return {
        "report_title": f"新闻可信度检测报告 - {detection.input_title}"[:255],
        "news_title": detection.input_title,
        "news_summary": build_news_summary(detection),
        "username": getattr(owner, "username", None) or "游客/未知用户",
        "detection_time": _format_datetime(detection.created_at),
        "generated_time": _format_datetime(datetime.now()),
        "final_score": _format_score(detection.final_score),
        "risk_level": detection.risk_level,
        "judgement_result": detection.judgement_result,
        "reason": detection.reason or "未提供 AI 分析理由",
        "risk_points": parse_risk_points(detection.risk_points),
        "keywords": _parse_keywords(detection.keywords),
        "evidence_items": evidence_items,
        "similar_news": evidence_items,
        "suggestion": detection.suggestion or "建议结合权威来源进行人工复核。",
        "disclaimer": REPORT_DISCLAIMER,
    }


def _ensure_owner_or_admin(owner_id: int | None, current_user: Any) -> None:
    if getattr(current_user, "role", None) == "admin":
        return
    current_user_id = getattr(current_user, "id", None)
    if owner_id is None or current_user_id is None or int(owner_id) != int(current_user_id):
        raise ReportAccessDeniedError("无权生成或下载该检测记录的报告")


def _resolve_stored_path(report_root: Path, stored_path: str) -> Path:
    root = report_root.resolve()
    candidate = Path(stored_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root):
        raise ReportFileMissingError("报告文件路径无效")
    if not REPORT_FILE_NAME_PATTERN.fullmatch(resolved.name):
        raise ReportFileMissingError(
            "Invalid report file name: only generated report_<uuid>.pdf or report_<uuid>.html is allowed"
        )
    return resolved


def _build_admin_report_item(db: Session, report: Report) -> dict[str, Any]:
    detection = _get_report_detection(db, report)
    owner = get_user_by_id(db, report.user_id) if report.user_id is not None else None
    file_name, file_size, report_status = _report_file_info(report)
    return {
        "report_id": int(report.id),
        "detection_id": int(report.detection_id),
        "user_id": report.user_id,
        "username": getattr(owner, "username", None),
        "news_title": getattr(detection, "input_title", None) or report.report_title,
        "risk_level": getattr(detection, "risk_level", None),
        "final_score": _score_or_none(getattr(detection, "final_score", None)),
        "file_name": file_name,
        "file_size": file_size,
        "status": report_status,
        "download_url": get_admin_report_download_url(report) if report_status == "generated" else None,
        "created_at": report.created_at,
        "updated_at": report.updated_at,
    }


def _get_report_detection(db: Session, report: Report) -> DetectionRecord | None:
    return getattr(report, "detection", None) or get_detection_record_by_id(
        db,
        report.detection_id,
    )


def _report_file_info(report: Report) -> tuple[str | None, int | None, str]:
    if not report.pdf_path:
        return None, None, "missing"

    file_name = Path(report.pdf_path).name
    try:
        pdf_file = _resolve_stored_path(Path(get_settings().report_path), report.pdf_path)
    except ReportFileMissingError:
        return file_name, None, "missing"

    if not pdf_file.is_file():
        return file_name, None, "missing"

    try:
        return pdf_file.name, pdf_file.stat().st_size, "generated"
    except OSError:
        return file_name, None, "missing"


def _score_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _remove_stored_files(
    report_root: Path,
    stored_paths: tuple[str | None, str | None],
) -> None:
    for stored_path in stored_paths:
        if not stored_path:
            continue
        try:
            _remove_files(_resolve_stored_path(report_root, stored_path))
        except ReportFileMissingError:
            logger.warning("Ignored invalid stored report path: %s", stored_path)


def _remove_files(*paths: Path) -> None:
    for path in paths:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Failed to remove obsolete report file: %s", path)


def _parse_keywords(value: str | None) -> list[str]:
    if not value:
        return []
    keywords: list[str] = []
    for item in re.split(r"[,，;；\n]+", value):
        keyword = item.strip()
        if keyword and keyword not in keywords:
            keywords.append(keyword)
    return keywords


def _format_datetime(value: datetime | None) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else "--"


def _format_score(value: Any) -> str:
    try:
        return f"{float(value):.1f}"
    except (TypeError, ValueError):
        return "--"


def _format_similarity(value: Any) -> str:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return "--"
    if 0 <= score <= 1:
        return f"{score * 100:.1f}%"
    return f"{score:.1f}%"
