"""Separate completion of a request from availability of a supported verdict."""

from __future__ import annotations

import math
from typing import Any


UNKNOWN_RISK_LEVEL = "无法判断"
ASSESSMENT_COMPLETED = "completed"
ASSESSMENT_INSUFFICIENT = "insufficient_evidence"
ASSESSMENT_DEGRADED = "degraded"


def assessment_outcome(
    *, provider_failed: bool, arbitration_status: str, quality_status: str,
    evidence_count: int,
) -> tuple[str, str]:
    if provider_failed or arbitration_status in {
        "provider_error", "retry_exhausted", "invalid_response", "unavailable"
    } or (arbitration_status == "ok" and quality_status != "ok"):
        return ASSESSMENT_DEGRADED, "模型分析或证据校验未完整成功，暂时无法判断，请稍后重试或人工核查。"
    if not evidence_count or arbitration_status == "no_evidence":
        return ASSESSMENT_INSUFFICIENT, "未获得可用于判断的有效证据，暂时无法判断，请补充来源或人工核查。"
    if arbitration_status != "ok" or quality_status != "ok":
        return ASSESSMENT_DEGRADED, "分析状态不完整，暂时无法判断，请重新检测或人工核查。"
    return ASSESSMENT_COMPLETED, "模型分析与证据校验已完成；结果仍需结合原始来源人工复核。"


def stored_assessment(record: Any, payload: dict[str, Any]) -> tuple[str, str]:
    """Interpret legacy snapshots conservatively without inventing missing evidence."""
    status = payload.get("assessment_status") or getattr(record, "assessment_status", None)
    if status in {ASSESSMENT_COMPLETED, ASSESSMENT_INSUFFICIENT, ASSESSMENT_DEGRADED}:
        reason = payload.get("assessment_reason") or {
            ASSESSMENT_COMPLETED: "模型分析与证据校验已完成。",
            ASSESSMENT_INSUFFICIENT: "有效证据不足，暂时无法判断。",
            ASSESSMENT_DEGRADED: "分析未完整成功，暂时无法判断。",
        }[status]
        return status, reason
    arbitration = payload.get("arbitration_status")
    if arbitration:
        evidence_count = len(getattr(record, "evidence_matches", []) or [])
        if arbitration == "ok" and payload.get("quality_status") == "ok" and evidence_count:
            quality = payload.get("evidence_quality")
            coverage = quality.get("coverage") if isinstance(quality, dict) else None
            if coverage is None:
                return "legacy", "历史记录未保存完整的证据覆盖诊断。"
            if isinstance(coverage, bool) or not isinstance(coverage, (int, float)) or not math.isfinite(coverage) or not 0 <= coverage <= 100:
                return ASSESSMENT_DEGRADED, "历史证据覆盖数据无效，暂时无法判断。"
            if coverage == 0:
                evidence_count = 0
        return assessment_outcome(
            provider_failed=arbitration == "provider_error",
            arbitration_status=arbitration,
            quality_status=payload.get("quality_status", "unavailable"),
            evidence_count=evidence_count,
        )
    return "legacy", "历史记录未保存完整的分析状态。"
