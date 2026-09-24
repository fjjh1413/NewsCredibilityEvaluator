"""Fail-closed publication gate for project-specific four-level gold data.

Upstream CFEVER labels are legitimate three-class annotations, but do not
constitute an independently reviewed mapping into this application's four levels.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

LEAKAGE_PATTERNS = (
    r"(?:可信|存疑|疑似谣言|高风险)[：: ]*样本",
    r"该样本用于测试|该知识条目仅用于测试|现有评测知识条目|核验依据是",
    r"(?:预期|期望|应该|应当|能否).{0,15}输出.{0,8}[‘'\"“]?(?:可信|存疑|疑似谣言|高风险)",
)
LABELS = {"可信", "可信新闻", "存疑", "存疑信息", "疑似谣言", "高风险", "高风险谣言"}


def leakage_findings(row: dict[str, Any]) -> list[str]:
    """Inspect model-visible fields, never annotation columns. Heuristic, not proof."""
    return [f"{field}: {pattern}" for field in ("title", "content")
            for pattern in LEAKAGE_PATTERNS if re.search(pattern, str(row.get(field, "")))]


def gold_issues(row: dict[str, Any]) -> list[str]:
    issues = leakage_findings(row)
    if row.get("gold_label") not in LABELS:
        issues.append("missing project four-level gold label")
    if row.get("human_review_status") != "adjudicated":
        issues.append("human review is not adjudicated")
    reviewers = [str(row.get(f"reviewer_{i}_id", "")).strip() for i in (1, 2)]
    if not all(reviewers) or reviewers[0] == reviewers[1]:
        issues.append("two distinct reviewer identities required")
    for i in (1, 2):
        if row.get(f"reviewer_{i}_type") != "human" or row.get(f"reviewer_{i}_label") not in LABELS:
            issues.append(f"reviewer {i} human annotation missing")
    if not row.get("adjudication_reason") or not row.get("source_record_ids"):
        issues.append("adjudication reason and source provenance required")
    return issues


def audit_dataset(rows: list[dict[str, Any]]) -> dict[str, Any]:
    failures = {str(r.get("sample_id", i)): gold_issues(r) for i, r in enumerate(rows)}
    failures = {key: value for key, value in failures.items() if value}
    leakage = {str(r.get("sample_id", i)): leakage_findings(r) for i, r in enumerate(rows)}
    leakage = {key: value for key, value in leakage.items() if value}
    return {"sample_count": len(rows), "publication_eligible": bool(rows) and not failures,
            "eligible_count": len(rows) - len(failures), "leakage_count": len(leakage),
            "issues": failures, "leakage_findings": leakage,
            "limitation": "Automated checks validate provenance fields; they cannot prove reviewer identity or detect every semantic leak."}


def verify_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = []
    for relative, expected in data.get("files", {}).items():
        file = path.parent / relative
        if not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest() != expected:
            errors.append(relative)
    if not data.get("files") or errors:
        raise ValueError(f"Frozen dataset hash mismatch: {errors or ['empty manifest']}")
    return data
