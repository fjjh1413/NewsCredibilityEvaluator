import re
from collections import Counter
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.crud.high_risk_crud import (
    get_admin_high_risk_records,
    get_high_risk_record,
    get_public_high_risk_category_rows,
    get_public_high_risk_keyword_values,
    get_public_high_risk_ranking,
    get_public_high_risk_records,
    save_high_risk_record,
)
from app.models.detection_record import DetectionRecord
from app.schemas.detection import parse_risk_points


class HighRiskNotFoundError(Exception):
    pass


class HighRiskConflictError(Exception):
    pass


def list_public_high_risk(
    db: Session,
    **filters: Any,
) -> tuple[list[dict[str, Any]], int]:
    records, total = get_public_high_risk_records(db, **filters)
    return [_public_item(record) for record in records], total


def list_public_high_risk_ranking(
    db: Session,
    limit: int = 10,
) -> list[dict[str, Any]]:
    return [_public_item(record) for record in get_public_high_risk_ranking(db, limit)]


def get_public_high_risk_keywords(
    db: Session,
    limit: int = 10,
) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for value in get_public_high_risk_keyword_values(db):
        counter.update(_split_keywords(value))
    return [
        {"keyword": keyword, "count": count}
        for keyword, count in counter.most_common(max(1, min(limit, 100)))
    ]


def get_public_high_risk_categories(db: Session) -> list[dict[str, Any]]:
    return [
        {"category": category or "未分类", "count": int(count)}
        for category, count in get_public_high_risk_category_rows(db)
    ]


def list_admin_high_risk(
    db: Session,
    **filters: Any,
) -> tuple[list[dict[str, Any]], int]:
    records, total = get_admin_high_risk_records(db, **filters)
    return [_admin_item(record) for record in records], total


def get_admin_high_risk_detail(db: Session, record_id: int) -> dict[str, Any]:
    return _admin_detail(_require_record(db, record_id))


def update_high_risk_review(
    db: Session,
    record_id: int,
    review_status: str,
    admin_id: int,
    admin_remark: str | None = None,
) -> dict[str, Any]:
    record = _require_record(db, record_id)
    record.review_status = review_status
    if admin_remark is not None:
        record.admin_remark = admin_remark

    if review_status == "pending":
        record.reviewed_at = None
        record.reviewed_by = None
        record.is_public = False
    else:
        record.reviewed_at = datetime.now()
        record.reviewed_by = admin_id
        if review_status == "rejected":
            record.is_public = False

    return _admin_detail(save_high_risk_record(db, record))


def update_high_risk_public_status(
    db: Session,
    record_id: int,
    is_public: bool,
) -> dict[str, Any]:
    record = _require_record(db, record_id)
    if is_public and (
        not record.is_high_risk or record.review_status != "approved"
    ):
        raise HighRiskConflictError("请先审核通过后再公开展示")

    record.is_public = is_public
    return _admin_detail(save_high_risk_record(db, record))


def update_high_risk_remark(
    db: Session,
    record_id: int,
    admin_remark: str | None,
) -> dict[str, Any]:
    record = _require_record(db, record_id)
    record.admin_remark = admin_remark
    return _admin_detail(save_high_risk_record(db, record))


def _require_record(db: Session, record_id: int) -> DetectionRecord:
    record = get_high_risk_record(db, record_id)
    if record is None:
        raise HighRiskNotFoundError("高风险检测记录不存在")
    return record


def _public_item(record: DetectionRecord) -> dict[str, Any]:
    return {
        "id": int(record.id),
        "title": record.input_title,
        "summary": _build_summary(record),
        "category": record.category or "未分类",
        "final_score": _score(record.final_score),
        "risk_level": record.risk_level or "未知风险等级",
        "keywords": _split_keywords(record.keywords),
        "published_at": record.reviewed_at or record.created_at,
    }


def _admin_item(record: DetectionRecord) -> dict[str, Any]:
    return {
        "id": int(record.id),
        "user_id": record.user_id,
        "input_title": record.input_title,
        "category": record.category,
        "final_score": _score(record.final_score),
        "risk_level": record.risk_level,
        "is_high_risk": bool(record.is_high_risk),
        "review_status": record.review_status or "pending",
        "is_public": bool(record.is_public),
        "admin_remark": record.admin_remark,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "reviewed_at": record.reviewed_at,
        "reviewed_by": record.reviewed_by,
    }


def _admin_detail(record: DetectionRecord) -> dict[str, Any]:
    data = _admin_item(record)
    data.update(
        {
            "input_content": record.input_content,
            "keywords": _split_keywords(record.keywords),
            "evidence_score": _score(record.evidence_score),
            "llm_score": _score(record.llm_score),
            "rule_score": _score(record.rule_score),
            "judgement_result": record.judgement_result,
            "reason": record.reason,
            "risk_points": parse_risk_points(record.risk_points),
            "suggestion": record.suggestion,
            "evidence_matches": [
                {
                    "id": int(evidence.id),
                    "knowledge_id": evidence.knowledge_id,
                    "title": evidence.title,
                    "summary": evidence.summary,
                    "source_name": evidence.source_name,
                    "similarity_score": _score(evidence.similarity_score),
                    "rank_order": evidence.rank_order,
                }
                for evidence in record.evidence_matches
            ],
        }
    )
    return data


def _build_summary(record: DetectionRecord, max_length: int = 150) -> str:
    source = record.input_content or record.reason or record.judgement_result or ""
    text = re.sub(r"\s+", " ", source).strip()
    if not text:
        return "暂无摘要"
    return text if len(text) <= max_length else f"{text[:max_length]}..."


def _split_keywords(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        items = value
    else:
        items = re.split(r"[,，;；\n]+", str(value))
    return list(dict.fromkeys(str(item).strip() for item in items if str(item).strip()))


def _score(value: Any) -> float:
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
