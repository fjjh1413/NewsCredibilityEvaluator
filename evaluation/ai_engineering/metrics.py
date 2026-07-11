"""Offline AI engineering metrics and quality gates.

This module evaluates captured detection outputs. It intentionally avoids
database, network, or model calls so it can run in unit tests and CI.
"""

from __future__ import annotations

import math
import statistics
from datetime import datetime, timezone
from typing import Any, Iterable, Sequence


SCHEMA_VERSION = "ai-engineering-eval/v1"
DEFAULT_K = 5

DEFAULT_GATES: dict[str, float] = {
    "min_contract_valid_rate": 1.0,
    "min_risk_level_accuracy": 0.8,
    "min_context_precision_at_k": 0.6,
    "min_context_recall_at_k": 0.6,
    "min_score_in_range_rate": 0.8,
    "max_degraded_rate": 0.05,
    "max_total_latency_ms_p95": 60000.0,
}

DEGRADED_STATUSES = {
    "degraded",
    "failed",
    "failure",
    "error",
    "provider_error",
    "parse_failed",
    "retry_exhausted",
    "timeout",
}


def _safe_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _clean_id(value: Any) -> str:
    return str(value).strip()


def _as_id_set(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        parts = value.split(",")
    elif isinstance(value, Iterable):
        parts = list(value)
    else:
        parts = [value]
    return {_clean_id(part) for part in parts if _clean_id(part)}


def _dedupe(ids: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in ids:
        clean = _clean_id(item)
        if clean and clean not in seen:
            seen.add(clean)
            result.append(clean)
    return result


def _mean(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return round(statistics.mean(values), 4)


def _rate(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(count / total, 4)


def _percentile(values: Sequence[float], percentile: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return round(sorted_values[0], 2)
    rank = percentile / 100.0 * (len(sorted_values) - 1)
    lower = int(math.floor(rank))
    upper = int(math.ceil(rank))
    if lower == upper:
        return round(sorted_values[lower], 2)
    weight = rank - lower
    value = sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight
    return round(value, 2)


def context_precision_at_k(
    retrieved_ids: Sequence[str],
    relevant_ids: Iterable[str],
    k: int = DEFAULT_K,
) -> float:
    """Average precision over the top-k retrieved evidence IDs."""
    relevant = {_clean_id(item) for item in relevant_ids if _clean_id(item)}
    if not relevant or k <= 0:
        return 0.0

    top_k = _dedupe(list(retrieved_ids))[:k]
    hits = 0
    precision_sum = 0.0
    for rank, evidence_id in enumerate(top_k, start=1):
        if evidence_id in relevant:
            hits += 1
            precision_sum += hits / rank

    denominator = min(len(relevant), k)
    if denominator == 0:
        return 0.0
    return round(precision_sum / denominator, 4)


def context_recall_at_k(
    retrieved_ids: Sequence[str],
    relevant_ids: Iterable[str],
    k: int = DEFAULT_K,
) -> float:
    """Recall over the top-k retrieved evidence IDs."""
    relevant = {_clean_id(item) for item in relevant_ids if _clean_id(item)}
    if not relevant or k <= 0:
        return 0.0
    top_k = set(_dedupe(list(retrieved_ids))[:k])
    return round(len(top_k & relevant) / len(relevant), 4)


def rag_hit_at_k(
    retrieved_ids: Sequence[str],
    relevant_ids: Iterable[str],
    k: int = DEFAULT_K,
) -> float:
    """Return 1 when at least one relevant ID appears in the top-k."""
    relevant = {_clean_id(item) for item in relevant_ids if _clean_id(item)}
    if not relevant or k <= 0:
        return 0.0
    top_k = set(_dedupe(list(retrieved_ids))[:k])
    return 1.0 if top_k & relevant else 0.0


def reciprocal_rank_at_k(
    retrieved_ids: Sequence[str],
    relevant_ids: Iterable[str],
    k: int = DEFAULT_K,
) -> float:
    """Reciprocal rank of the first relevant ID in the top-k window."""
    relevant = {_clean_id(item) for item in relevant_ids if _clean_id(item)}
    if not relevant or k <= 0:
        return 0.0
    for rank, retrieved_id in enumerate(_dedupe(list(retrieved_ids))[:k], start=1):
        if retrieved_id in relevant:
            return round(1 / rank, 4)
    return 0.0


def validate_prediction_contract(prediction: dict[str, Any]) -> list[str]:
    """Validate the minimum output contract required by the eval gate."""
    errors: list[str] = []

    if not isinstance(prediction.get("risk_level"), str) or not prediction.get("risk_level", "").strip():
        errors.append("risk_level")

    final_score = _safe_float(prediction.get("final_score"))
    if final_score is None or final_score < 0 or final_score > 100:
        errors.append("final_score")

    evidence = _extract_selected_evidence(prediction)
    if not evidence:
        errors.append("evidence_list")

    if not isinstance(prediction.get("arbitration_status"), str) or not prediction.get("arbitration_status", "").strip():
        errors.append("arbitration_status")

    stage_latency = prediction.get("stage_latency_ms")
    if stage_latency is not None and not isinstance(stage_latency, dict):
        errors.append("stage_latency_ms")
    elif isinstance(stage_latency, dict):
        for value in stage_latency.values():
            latency = _safe_float(value)
            if latency is None or latency < 0:
                errors.append("stage_latency_ms")
                break

    return errors


def evaluate_cases(
    cases: Sequence[dict[str, Any]],
    gates: dict[str, float] | None = None,
    k: int = DEFAULT_K,
) -> dict[str, Any]:
    """Evaluate cases and return metrics, gate status, and per-case details."""
    thresholds = dict(DEFAULT_GATES)
    if gates:
        thresholds.update(gates)

    per_case: list[dict[str, Any]] = []
    contract_valid = 0
    risk_expected = 0
    risk_correct = 0
    score_expected = 0
    score_in_range = 0
    context_precisions: list[float] = []
    context_recalls: list[float] = []
    rag_hits: list[float] = []
    rag_reciprocal_ranks: list[float] = []
    parent_recalls: list[float] = []
    rag_claim_coverages: list[float] = []
    rag_empty_count = 0
    degraded_count = 0
    total_latencies: list[float] = []
    arbitration_quality_present = 0
    claim_coverages: list[float] = []
    high_quality_contradictions = 0

    for index, case in enumerate(cases, start=1):
        case_id = str(case.get("case_id") or case.get("sample_id") or f"case-{index}")
        expected = case.get("expected") if isinstance(case.get("expected"), dict) else {}
        prediction = case.get("prediction") if isinstance(case.get("prediction"), dict) else {}

        contract_errors = validate_prediction_contract(prediction)
        if not contract_errors:
            contract_valid += 1

        expected_risks = _expected_risk_levels(expected)
        predicted_risk = str(prediction.get("risk_level") or "").strip()
        risk_match = None
        if expected_risks:
            risk_expected += 1
            risk_match = predicted_risk in expected_risks
            if risk_match:
                risk_correct += 1

        score_match = None
        final_score = _safe_float(prediction.get("final_score"))
        score_range = _score_range(expected)
        if score_range is not None:
            score_expected += 1
            low, high = score_range
            score_match = final_score is not None and low <= final_score <= high
            if score_match:
                score_in_range += 1

        relevant_ids = _expected_relevant_ids(expected)
        retrieved_ids = _extract_ranked_evidence_ids(prediction)
        ranked_evidence = _extract_ranked_evidence(prediction)
        if not ranked_evidence:
            rag_empty_count += 1
        context_precision = None
        context_recall = None
        rag_hit = None
        rag_mrr = None
        if relevant_ids:
            context_precision = context_precision_at_k(retrieved_ids, relevant_ids, k)
            context_recall = context_recall_at_k(retrieved_ids, relevant_ids, k)
            context_precisions.append(context_precision)
            context_recalls.append(context_recall)
            rag_hit = rag_hit_at_k(retrieved_ids, relevant_ids, k)
            rag_mrr = reciprocal_rank_at_k(retrieved_ids, relevant_ids, k)
            rag_hits.append(rag_hit)
            rag_reciprocal_ranks.append(rag_mrr)

        relevant_parent_ids = _expected_relevant_parent_ids(expected)
        retrieved_parent_ids = _extract_ranked_parent_ids(prediction)
        parent_recall = None
        if relevant_parent_ids:
            parent_recall = context_recall_at_k(
                retrieved_parent_ids,
                relevant_parent_ids,
                k,
            )
            parent_recalls.append(parent_recall)

        expected_claim_ids = _expected_claim_ids(expected)
        retrieved_claim_ids = _extract_ranked_claim_ids(prediction, k)
        rag_claim_coverage = None
        if expected_claim_ids:
            rag_claim_coverage = round(
                len(expected_claim_ids & retrieved_claim_ids) / len(expected_claim_ids),
                4,
            )
            rag_claim_coverages.append(rag_claim_coverage)

        degraded = _is_degraded(prediction)
        if degraded:
            degraded_count += 1

        total_latency = _total_latency_ms(prediction)
        if total_latency is not None:
            total_latencies.append(total_latency)

        arbitration_quality = _extract_arbitration_quality(prediction)
        if arbitration_quality:
            arbitration_quality_present += 1
            claim_coverage = _safe_float(arbitration_quality.get("claim_coverage"))
            if claim_coverage is not None:
                claim_coverages.append(claim_coverage)
            if arbitration_quality.get("has_high_quality_contradiction") is True:
                high_quality_contradictions += 1

        per_case.append({
            "case_id": case_id,
            "contract_valid": not contract_errors,
            "contract_errors": contract_errors,
            "risk_level_match": risk_match,
            "score_in_range": score_match,
            "context_precision_at_k": context_precision,
            "context_recall_at_k": context_recall,
            "rag_hit_at_k": rag_hit,
            "rag_mrr_at_k": rag_mrr,
            "parent_recall_at_k": parent_recall,
            "rag_claim_coverage_at_k": rag_claim_coverage,
            "degraded": degraded,
            "total_latency_ms": total_latency,
            "claim_coverage": (
                _safe_float(arbitration_quality.get("claim_coverage"))
                if arbitration_quality
                else None
            ),
        })

    total_cases = len(cases)
    metrics = {
        "total_cases": total_cases,
        "contract_valid_rate": _rate(contract_valid, total_cases),
        "risk_level_accuracy": _rate(risk_correct, risk_expected),
        "score_in_range_rate": 1.0 if score_expected == 0 else _rate(score_in_range, score_expected),
        "context_precision_at_k": _mean(context_precisions),
        "context_recall_at_k": _mean(context_recalls),
        "rag_hit_rate_at_k": _mean(rag_hits),
        "rag_mrr_at_k": _mean(rag_reciprocal_ranks),
        "parent_recall_at_k": _mean(parent_recalls),
        "rag_claim_coverage_at_k": _mean(rag_claim_coverages),
        "rag_empty_rate": _rate(rag_empty_count, total_cases),
        "degraded_rate": _rate(degraded_count, total_cases),
        "total_latency_ms_p95": _percentile(total_latencies, 95),
        "arbitration_quality_present_rate": _rate(arbitration_quality_present, total_cases),
        "claim_coverage_avg": _mean(claim_coverages),
        "high_quality_contradiction_rate": _rate(high_quality_contradictions, total_cases),
        "evaluated_with_k": k,
    }
    gate = _evaluate_gate(metrics, thresholds)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics,
        "gate": gate,
        "per_case": per_case,
    }


def _evaluate_gate(metrics: dict[str, Any], gates: dict[str, float]) -> dict[str, Any]:
    checks = [
        ("contract_valid_rate", metrics["contract_valid_rate"], gates["min_contract_valid_rate"], ">="),
        ("risk_level_accuracy", metrics["risk_level_accuracy"], gates["min_risk_level_accuracy"], ">="),
        ("context_precision_at_k", metrics["context_precision_at_k"], gates["min_context_precision_at_k"], ">="),
        ("context_recall_at_k", metrics["context_recall_at_k"], gates["min_context_recall_at_k"], ">="),
        ("score_in_range_rate", metrics["score_in_range_rate"], gates["min_score_in_range_rate"], ">="),
        ("degraded_rate", metrics["degraded_rate"], gates["max_degraded_rate"], "<="),
        ("total_latency_ms_p95", metrics["total_latency_ms_p95"], gates["max_total_latency_ms_p95"], "<="),
    ]
    failures: list[dict[str, Any]] = []
    for metric, actual, threshold, direction in checks:
        passed = actual >= threshold if direction == ">=" else actual <= threshold
        if not passed:
            failures.append({
                "metric": metric,
                "actual": actual,
                "threshold": threshold,
                "direction": direction,
            })
    return {
        "passed": not failures,
        "failures": failures,
        "thresholds": gates,
    }


def _expected_risk_levels(expected: dict[str, Any]) -> set[str]:
    levels = _as_id_set(expected.get("acceptable_risk_levels"))
    if not levels:
        levels = _as_id_set(expected.get("risk_level"))
    return levels


def _score_range(expected: dict[str, Any]) -> tuple[float, float] | None:
    raw_range = expected.get("score_range")
    if not isinstance(raw_range, Sequence) or isinstance(raw_range, (str, bytes)):
        return None
    if len(raw_range) != 2:
        return None
    low = _safe_float(raw_range[0])
    high = _safe_float(raw_range[1])
    if low is None or high is None:
        return None
    return (min(low, high), max(low, high))


def _expected_relevant_ids(expected: dict[str, Any]) -> set[str]:
    relevant = _as_id_set(expected.get("relevant_evidence_ids"))
    if not relevant:
        relevant = _as_id_set(expected.get("relevant_knowledge_ids"))
    return relevant


def _expected_relevant_parent_ids(expected: dict[str, Any]) -> set[str]:
    relevant = _as_id_set(expected.get("relevant_parent_ids"))
    if not relevant:
        relevant = _as_id_set(expected.get("relevant_knowledge_ids"))
    return relevant


def _expected_claim_ids(expected: dict[str, Any]) -> set[str]:
    claim_ids = _as_id_set(expected.get("required_claim_ids"))
    if not claim_ids:
        claim_ids = _as_id_set(expected.get("claim_ids"))
    return claim_ids


def _extract_selected_evidence(prediction: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("evidence_list", "evidences", "similar_news"):
        value = prediction.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _extract_ranked_evidence(prediction: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("candidate_evidence_list", "candidate_evidences", "retrieved_evidence_list"):
        value = prediction.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return _extract_selected_evidence(prediction)


def _extract_ranked_evidence_ids(prediction: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for evidence in _extract_ranked_evidence(prediction):
        evidence_id = _evidence_id(evidence)
        if evidence_id:
            ids.append(evidence_id)
    return ids


def _extract_ranked_parent_ids(prediction: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for evidence in _extract_ranked_evidence(prediction):
        value = evidence.get("knowledge_id")
        if value is None and isinstance(evidence.get("metadata"), dict):
            value = evidence["metadata"].get("knowledge_id")
        if value is not None and _clean_id(value):
            ids.append(_clean_id(value))
    return ids


def _extract_ranked_claim_ids(prediction: dict[str, Any], k: int) -> set[str]:
    claim_ids: set[str] = set()
    for evidence in _extract_ranked_evidence(prediction)[: max(0, k)]:
        claim_ids.update(_as_id_set(evidence.get("claim_ids")))
    return claim_ids


def _extract_arbitration_quality(prediction: dict[str, Any]) -> dict[str, Any]:
    direct = prediction.get("arbitration_quality")
    if isinstance(direct, dict):
        return direct
    evidence_quality = prediction.get("evidence_quality")
    if isinstance(evidence_quality, dict):
        nested = evidence_quality.get("backend_arbitration_quality")
        if isinstance(nested, dict):
            return nested
    return {}


def _evidence_id(evidence: dict[str, Any]) -> str:
    for key in ("evidence_id", "candidate_id", "chunk_id", "knowledge_id", "id"):
        value = evidence.get(key)
        if value is not None and _clean_id(value):
            return _clean_id(value)
    for key in ("url", "source_url", "title"):
        value = evidence.get(key)
        if value is not None and _clean_id(value):
            return _clean_id(value)
    return ""


def _is_degraded(prediction: dict[str, Any]) -> bool:
    if prediction.get("error") or prediction.get("error_message"):
        return True
    for key in ("arbitration_status", "quality_status", "status"):
        value = str(prediction.get(key) or "").strip().lower()
        if value in DEGRADED_STATUSES:
            return True
    return False


def _total_latency_ms(prediction: dict[str, Any]) -> float | None:
    explicit = _safe_float(prediction.get("total_latency_ms"))
    if explicit is not None and explicit >= 0:
        return explicit

    stage_latency = prediction.get("stage_latency_ms")
    if not isinstance(stage_latency, dict):
        return None

    total = 0.0
    found = False
    for value in stage_latency.values():
        latency = _safe_float(value)
        if latency is not None and latency >= 0:
            total += latency
            found = True
    return round(total, 2) if found else None
