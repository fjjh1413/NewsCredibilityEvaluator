from __future__ import annotations

import json
from typing import Any
from app.core.assessment import ASSESSMENT_COMPLETED, UNKNOWN_RISK_LEVEL, stored_assessment


DETECTION_DETAIL_PAYLOAD_FIELDS = (
    "assessment_reason",
    "retrieval_version",
    "index_version",
    "candidate_chunk_count",
    "candidate_parent_count",
    "stage_latency_ms",
    "publish_time",
    "source_name",
    "source_url",
    "candidate_evidence_list",
    "excluded_evidence",
    "similar_news",
    "core_claims",
    "agent_trace",
    "evidence_quality",
    "arbitration_quality",
    "arbitration_status",
    "quality_status",
    "arbitration_error",
    "arbitration_attempts",
    "analysis_contract_version",
    "knowledge_has_relevant_match",
    "web_has_relevant_match",
    "rag_query_count",
    "rag_query_strategy",
    "rag_supporting_span_count",
)


def read_detection_analysis_payload(record: object) -> dict[str, Any]:
    raw_payload = getattr(record, "analysis_payload", None)
    if isinstance(raw_payload, dict):
        return raw_payload
    if not isinstance(raw_payload, str) or not raw_payload.strip():
        return {}
    try:
        parsed = json.loads(raw_payload)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def restore_detection_detail_payload(
    detail: dict[str, Any],
    record: object,
) -> dict[str, Any]:
    analysis_payload = read_detection_analysis_payload(record)
    for field_name in DETECTION_DETAIL_PAYLOAD_FIELDS:
        if field_name in analysis_payload:
            detail[field_name] = analysis_payload[field_name]
    status, reason = stored_assessment(record, analysis_payload)
    detail["assessment_status"] = status
    detail["assessment_reason"] = reason
    if status not in {ASSESSMENT_COMPLETED, "legacy"}:
        detail.update(final_score=None, risk_level=UNKNOWN_RISK_LEVEL,
                      judgement_result=reason, is_high_risk=False)
    return detail
