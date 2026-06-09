import re
from collections import Counter
from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.crud import statistics_crud
from app.models.detection_record import DetectionRecord
from app.models.knowledge_item import KnowledgeItem


DEFAULT_TREND_DAYS = 7
DEFAULT_ACTIVITY_DAYS = 30
MAX_RANGE_DAYS = 366


class StatisticsServiceError(Exception):
    """Base exception for administrator statistics failures."""


class StatisticsRangeError(StatisticsServiceError):
    pass


def get_statistics_overview(
    db: Session,
    today: date | None = None,
) -> dict[str, int]:
    return statistics_crud.get_overview_counts(db, today or date.today())


def get_detection_trend(
    db: Session,
    days: int = DEFAULT_TREND_DAYS,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, list[Any]]:
    start, end = resolve_date_range(
        days=days,
        start_date=start_date,
        end_date=end_date,
    )
    rows = statistics_crud.get_detection_trend_rows(db, start, end)
    counts = _date_count_map(rows)
    dates = _date_sequence(start, end)
    return {
        "dates": [item.isoformat() for item in dates],
        "counts": [counts.get(item.isoformat(), 0) for item in dates],
    }


def get_risk_distribution(
    db: Session,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict[str, Any]]:
    start, end = resolve_optional_date_range(start_date, end_date)
    rows = statistics_crud.get_detection_distribution_rows(
        db,
        DetectionRecord.risk_level,
        start,
        end,
    )
    return _normalize_distribution(rows, empty_label="未标记")


def get_category_distribution(
    db: Session,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict[str, Any]]:
    start, end = resolve_optional_date_range(start_date, end_date)
    rows = statistics_crud.get_detection_distribution_rows(
        db,
        DetectionRecord.category,
        start,
        end,
    )
    return _normalize_distribution(rows, empty_label="未分类")


def get_keyword_statistics(
    db: Session,
    limit: int = 20,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict[str, Any]]:
    start, end = resolve_optional_date_range(start_date, end_date)
    values = statistics_crud.get_detection_keyword_values(db, start, end)
    counter: Counter[str] = Counter()
    for value in values:
        for keyword in _parse_keywords(value):
            counter[keyword] += 1
    return [
        {"keyword": keyword, "count": count}
        for keyword, count in counter.most_common(max(1, min(limit, 100)))
    ]


def get_user_activity(
    db: Session,
    days: int = DEFAULT_ACTIVITY_DAYS,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, list[Any]]:
    start, end = resolve_date_range(
        days=days,
        start_date=start_date,
        end_date=end_date,
    )
    rows = statistics_crud.get_user_activity_rows(db, start, end)
    counts = _date_count_map(rows)
    dates = _date_sequence(start, end)
    return {
        "dates": [item.isoformat() for item in dates],
        "active_users": [counts.get(item.isoformat(), 0) for item in dates],
    }


def get_knowledge_overview(db: Session) -> dict[str, Any]:
    return {
        "total_knowledge": statistics_crud.get_knowledge_total(db),
        "category_distribution": _normalize_distribution(
            statistics_crud.get_knowledge_distribution_rows(
                db,
                KnowledgeItem.category,
            ),
            empty_label="未分类",
        ),
        "truth_label_distribution": _normalize_distribution(
            statistics_crud.get_knowledge_distribution_rows(
                db,
                KnowledgeItem.truth_label,
            ),
            empty_label="未标记",
        ),
        "vector_status_distribution": _normalize_distribution(
            statistics_crud.get_knowledge_distribution_rows(
                db,
                KnowledgeItem.vector_sync_status,
            ),
            empty_label="未标记",
        ),
    }


def resolve_date_range(
    days: int,
    start_date: date | None,
    end_date: date | None,
) -> tuple[date, date]:
    safe_days = max(1, min(days, MAX_RANGE_DAYS))
    end = end_date or date.today()
    start = start_date or (end - timedelta(days=safe_days - 1))
    _validate_date_range(start, end)
    return start, end


def resolve_optional_date_range(
    start_date: date | None,
    end_date: date | None,
) -> tuple[date | None, date | None]:
    if start_date is None and end_date is None:
        return None, None
    end = end_date or date.today()
    start = start_date or (end - timedelta(days=DEFAULT_ACTIVITY_DAYS - 1))
    _validate_date_range(start, end)
    return start, end


def _validate_date_range(start: date, end: date) -> None:
    if start > end:
        raise StatisticsRangeError("开始日期不能晚于结束日期")
    if (end - start).days + 1 > MAX_RANGE_DAYS:
        raise StatisticsRangeError(f"统计时间范围不能超过 {MAX_RANGE_DAYS} 天")


def _date_sequence(start: date, end: date) -> list[date]:
    return [
        start + timedelta(days=offset)
        for offset in range((end - start).days + 1)
    ]


def _date_count_map(rows: list[tuple[Any, int]]) -> dict[str, int]:
    return {_normalize_date_key(day): int(count or 0) for day, count in rows}


def _normalize_date_key(value: Any) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return str(value)[:10]


def _normalize_distribution(
    rows: list[tuple[Any, int]],
    empty_label: str,
) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    for name, count in rows:
        label = str(name).strip() if name is not None else ""
        counts[label or empty_label] += int(count or 0)
    return [
        {"name": name, "value": value}
        for name, value in sorted(
            counts.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]


def _parse_keywords(value: str) -> list[str]:
    keywords: list[str] = []
    for item in re.split(r"[,，;；\n]+", value):
        keyword = item.strip()
        if keyword and keyword not in keywords:
            keywords.append(keyword)
    return keywords
