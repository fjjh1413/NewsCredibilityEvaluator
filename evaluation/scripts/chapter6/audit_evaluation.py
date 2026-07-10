from __future__ import annotations

import csv
import hashlib
from difflib import SequenceMatcher
from itertools import combinations
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


VALID_LABELS = {
    "可信",
    "存疑",
    "谣言",
    "高风险",
    "可信新闻",
    "存疑信息",
    "疑似谣言",
    "高风险谣言",
}


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(line for line in handle if not line.lstrip().startswith("#"))
        rows = [
            {key: (value or "").strip() for key, value in row.items() if key is not None}
            for row in reader
        ]
        return list(reader.fieldnames or []), rows


def _issue(
    issue_type: str,
    row: dict[str, str],
    *,
    field: str,
    details: str,
    related_ids: str = "",
    severity: str = "warning",
) -> dict[str, str]:
    return {
        "issue_type": issue_type,
        "sample_id": row.get("sample_id", ""),
        "related_ids": related_ids,
        "field": field,
        "details": details,
        "severity": severity,
        "check_scope": "offline",
    }


def _normalized_text(value: str) -> str:
    return "".join(value.split()).casefold()


def _duplicate_issues(
    rows: list[dict[str, str]], field: str, issue_type: str
) -> list[dict[str, str]]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        value = _normalized_text(row.get(field, ""))
        if value:
            groups[value].append(row)

    issues: list[dict[str, str]] = []
    for group in groups.values():
        if len(group) < 2:
            continue
        ids = [row.get("sample_id", "") for row in group]
        for row in group:
            related = ",".join(sample_id for sample_id in ids if sample_id != row.get("sample_id"))
            issues.append(
                _issue(
                    issue_type,
                    row,
                    field=field,
                    related_ids=related,
                    details=f"{field}在{len(group)}条样本中完全重复",
                )
            )
    return issues


def find_near_duplicate_pairs(
    rows: list[dict[str, str]], *, field: str, threshold: float = 0.80
) -> list[dict[str, Any]]:
    """Return non-identical row pairs whose normalized text meets a ratio threshold."""
    pairs: list[dict[str, Any]] = []
    for left, right in combinations(rows, 2):
        left_text = _normalized_text(left.get(field, ""))
        right_text = _normalized_text(right.get(field, ""))
        if not left_text or not right_text or left_text == right_text:
            continue
        similarity = SequenceMatcher(None, left_text, right_text, autojunk=False).ratio()
        if similarity >= threshold:
            pairs.append(
                {
                    "sample_id_a": left.get("sample_id", ""),
                    "sample_id_b": right.get("sample_id", ""),
                    "topic_id_a": left.get("topic_id", ""),
                    "topic_id_b": right.get("topic_id", ""),
                    "same_topic": left.get("topic_id", "") == right.get("topic_id", ""),
                    "field": field,
                    "similarity": round(similarity, 6),
                }
            )
    return sorted(pairs, key=lambda item: (-item["similarity"], item["sample_id_a"], item["sample_id_b"]))


def analyze_news_dataset(path: str | Path, *, check_urls: bool = False) -> dict[str, Any]:
    """Audit an existing news CSV without modifying it."""
    dataset_path = Path(path)
    fields, rows = _read_csv(dataset_path)
    split_field = next(
        (name for name in ("split", "data_split", "dataset_split") if name in fields),
        None,
    )
    split_counts = Counter(
        (row.get(split_field, "") if split_field else "") or "未提供" for row in rows
    )
    label_counts = Counter(row.get("gold_label", "") or "缺失" for row in rows)

    issues: list[dict[str, str]] = []
    issues.extend(_duplicate_issues(rows, "url", "duplicate_url"))
    issues.extend(_duplicate_issues(rows, "title", "duplicate_title"))
    issues.extend(_duplicate_issues(rows, "content", "duplicate_content"))

    for row in rows:
        label = row.get("gold_label", "")
        if not label:
            issues.append(_issue("missing_label", row, field="gold_label", details="标签为空", severity="error"))
        elif label not in VALID_LABELS:
            issues.append(_issue("invalid_label", row, field="gold_label", details=f"未知标签：{label}", severity="error"))
        if not row.get("gold_label_source", ""):
            issues.append(_issue("missing_label_basis", row, field="gold_label_source", details="标签依据为空"))
        content = row.get("content", "")
        if not content:
            issues.append(_issue("empty_content", row, field="content", details="正文为空", severity="error"))
        elif len(content) < 20:
            issues.append(_issue("short_content", row, field="content", details=f"正文仅{len(content)}个字符"))
        raw_url = row.get("url", "")
        parsed = urlparse(raw_url)
        if raw_url and (parsed.scheme not in {"http", "https"} or not parsed.hostname):
            issues.append(_issue("invalid_url_syntax", row, field="url", details="URL不是有效HTTP/HTTPS地址"))

    return {
        "summary": {
            "dataset": str(dataset_path),
            "sha256": sha256_file(dataset_path),
            "sample_count": len(rows),
            "field_names": fields,
            "label_counts": dict(label_counts),
            "split_field": split_field or "未提供",
            "split_counts": dict(split_counts),
            "topic_count": len({row.get("topic_id") for row in rows if row.get("topic_id")}),
            "url_network_check": "not_run" if not check_urls else "pending",
        },
        "issues": issues,
        "rows": rows,
    }
