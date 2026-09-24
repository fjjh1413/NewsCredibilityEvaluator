"""Metrics computation for news credibility evaluation.

All functions operate on the per-case results list and produce structured
metric dicts.  No function mutates its input.
"""

from __future__ import annotations

import json
import math
import statistics
from collections import Counter
from typing import Any


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _safe_float(value: Any) -> float | None:
    """Return *value* as float, or None when unparseable / missing."""
    if value is None:
        return None
    try:
        f = float(value)
        if math.isfinite(f):
            return f
    except (TypeError, ValueError):
        pass
    return None


def _is_truthy(value: Any) -> bool:
    """Treat truthy values consistently across metrics."""
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes")
    return bool(value)


def _parse_numeric_id_set(value: Any) -> set[int]:
    """Parse comma/list IDs into an integer set for parent knowledge metrics."""
    ids: set[int] = set()
    if isinstance(value, str):
        parts = value.split(",")
    elif isinstance(value, list):
        parts = value
    else:
        return ids

    for part in parts:
        if isinstance(part, (int, float)) and not isinstance(part, bool):
            ids.add(int(part))
            continue
        text = str(part).strip()
        if text.isdigit():
            ids.add(int(text))
    return ids


def _parse_numeric_id_list(value: Any) -> list[int]:
    """Parse comma/list IDs into an integer list, preserving rank order."""
    ids: list[int] = []
    if isinstance(value, str):
        parts = value.split(",")
    elif isinstance(value, list):
        parts = value
    else:
        return ids

    for part in parts:
        if isinstance(part, (int, float)) and not isinstance(part, bool):
            ids.append(int(part))
            continue
        text = str(part).strip()
        if text.isdigit():
            ids.append(int(text))
    return ids


def _parse_text_id_set(value: Any) -> set[str]:
    """Parse comma/list IDs into a string set for chunk-level metrics."""
    if isinstance(value, str):
        parts = value.split(",")
    elif isinstance(value, list):
        parts = value
    else:
        return set()
    return {str(part).strip() for part in parts if str(part).strip()}


def _parse_text_id_list(value: Any) -> list[str]:
    """Parse comma/list IDs into a string list, preserving rank order."""
    if isinstance(value, str):
        parts = value.split(",")
    elif isinstance(value, list):
        parts = value
    else:
        return []
    return [str(part).strip() for part in parts if str(part).strip()]


def _ranked_retrieval_stats(
    pairs: list[tuple[set[Any], list[Any]]],
    k_values: list[int],
) -> dict[str, Any]:
    """Compute Hit@K, Recall@K, and MRR for ranked retrieval pairs."""
    hit_at_k: dict[int, float] = {}
    recall_at_k: dict[int, float] = {}
    reciprocal_ranks: list[float] = []

    if not pairs:
        return {
            "hit_at_k": {},
            "recall_at_k": {},
            "mrr": None,
        }

    for k in k_values:
        hit_count = 0
        recall_sum = 0.0
        for relevant, retrieved in pairs:
            top_k = retrieved[:k]
            if any(rid in relevant for rid in top_k):
                hit_count += 1
            recall_sum += len(set(top_k) & relevant) / len(relevant)
        hit_at_k[k] = round(hit_count / len(pairs), 4)
        recall_at_k[k] = round(recall_sum / len(pairs), 4)

    for relevant, retrieved in pairs:
        for rank, rid in enumerate(retrieved, start=1):
            if rid in relevant:
                reciprocal_ranks.append(1.0 / rank)
                break
        else:
            reciprocal_ranks.append(0.0)

    return {
        "hit_at_k": hit_at_k,
        "recall_at_k": recall_at_k,
        "mrr": round(statistics.mean(reciprocal_ranks), 4),
    }


# ---------------------------------------------------------------------------
# 1. sample counts
# ---------------------------------------------------------------------------

def compute_sample_counts(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Return total, valid, success, failed, and per-label counts."""
    total = len(results)
    valid = [r for r in results if not r.get("is_demo", False)]
    success = [r for r in valid if r.get("success")]
    failed = [r for r in valid if not r.get("success")]

    gold_labels = Counter(
        r["gold_label"] for r in valid if r.get("gold_label")
    )
    predicted_labels = Counter(
        r["predicted_label"] for r in success if r.get("predicted_label")
    )

    return {
        "total_samples": total,
        "demo_samples_excluded": total - len(valid),
        "valid_samples": len(valid),
        "success_count": len(success),
        "failure_count": len(failed),
        "gold_label_distribution": dict(gold_labels),
        "predicted_label_distribution": dict(predicted_labels),
        "assessment_status_counts": dict(Counter(r.get("assessment_status") or "legacy" for r in valid)),
        "abstained_count": sum(r.get("assessment_status") in {"insufficient_evidence", "degraded"} for r in valid),
        "degraded_count": sum(r.get("assessment_status") == "degraded" for r in valid),
    }


# ---------------------------------------------------------------------------
# 2. response time (latency)
# ---------------------------------------------------------------------------

def _percentile(sorted_values: list[float], p: float) -> float:
    """Linear-interpolation percentile (same method as numpy)."""
    if not sorted_values:
        return 0.0
    n = len(sorted_values)
    rank = p / 100.0 * (n - 1)
    lower = int(math.floor(rank))
    upper = int(math.ceil(rank))
    if lower == upper:
        return sorted_values[lower]
    weight = rank - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def compute_latency_stats(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute overall and per-stage latency statistics."""
    success = [r for r in results if r.get("success") and not r.get("is_demo", False)]
    latencies = {
        "total_latency_ms": [],
        "parse_latency_ms": [],
        "local_retrieval_latency_ms": [],
        "web_search_latency_ms": [],
        "llm_latency_ms": [],
        "report_latency_ms": [],
        "db_save_latency_ms": [],
    }

    for r in success:
        for key in latencies:
            val = _safe_float(r.get(key))
            if val is not None:
                latencies[key].append(val)

    def _stats(values: list[float]) -> dict[str, float]:
        if not values:
            return {"avg": 0.0, "p50": 0.0, "p95": 0.0, "max": 0.0, "count": 0}
        sv = sorted(values)
        return {
            "avg": round(statistics.mean(sv), 2),
            "p50": round(_percentile(sv, 50), 2),
            "p95": round(_percentile(sv, 95), 2),
            "max": round(sv[-1], 2),
            "count": len(sv),
        }

    return {key: _stats(vals) for key, vals in latencies.items()}


# ---------------------------------------------------------------------------
# 3. web search trigger rate
# ---------------------------------------------------------------------------

def compute_web_trigger_rate(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute web search trigger rate and breakdown by reason."""
    valid = [r for r in results if not r.get("is_demo", False)]
    # Only count samples where web search was allowed
    allowed = [r for r in valid if _is_truthy(r.get("web_search_allowed"))]
    triggered = [r for r in allowed if _is_truthy(r.get("web_search_triggered"))]

    reason_counts: Counter = Counter()
    for r in triggered:
        reason = (r.get("web_trigger_reason") or "unknown").strip()
        if reason:
            reason_counts[reason] += 1

    rate = len(triggered) / len(allowed) if allowed else 0.0

    return {
        "web_search_allowed_count": len(allowed),
        "web_search_triggered_count": len(triggered),
        "web_trigger_rate": round(rate, 4),
        "web_trigger_reasons": dict(reason_counts),
    }


# ---------------------------------------------------------------------------
# 4. local retrieval effectiveness
# ---------------------------------------------------------------------------

def _compute_retrieval_metrics_legacy(
    results: list[dict[str, Any]],
    k_values: list[int] | None = None,
) -> dict[str, Any]:
    """Compute Hit@K, Recall@K, and MRR for samples with human-annotated
    *relevant_knowledge_ids*.

    Only samples whose ``relevant_knowledge_ids`` field is non-empty are
    included.  An empty dataset produces zero-filled metrics (never NaN).
    """
    if k_values is None:
        k_values = [1, 3, 5, 10]

    # Filter to samples with human relevance annotations
    annotated = [
        r for r in results
        if not r.get("is_demo", False)
        and r.get("success")
        and r.get("relevant_knowledge_ids")
    ]

    if not annotated:
        return {
            "annotated_sample_count": 0,
            "note": "No samples had relevant_knowledge_ids — Hit@K / Recall@K / MRR unavailable.",
            "hit_at_k": {},
            "recall_at_k": {},
            "mrr": None,
        }

    # Parse annotations
    for r in annotated:
        raw = r["relevant_knowledge_ids"]
        if isinstance(raw, str):
            r["_relevant_ids"] = {
                int(x.strip()) for x in raw.split(",") if x.strip().isdigit()
            }
        elif isinstance(raw, list):
            r["_relevant_ids"] = {int(x) for x in raw if isinstance(x, (int, float))}
        else:
            r["_relevant_ids"] = set()

        # Parse retrieved IDs from retrieved_knowledge_ids field
        raw_ret = r.get("retrieved_knowledge_ids", "")
        if isinstance(raw_ret, str):
            r["_retrieved_ids"] = [
                int(x.strip()) for x in raw_ret.split(",") if x.strip().isdigit()
            ]
        elif isinstance(raw_ret, list):
            r["_retrieved_ids"] = [int(x) for x in raw_ret if isinstance(x, (int, float))]
        else:
            r["_retrieved_ids"] = []

    # Hit@K and Recall@K
    hit_at_k: dict[int, float] = {}
    recall_at_k: dict[int, float] = {}
    reciprocal_ranks: list[float] = []

    for k in k_values:
        hit_count = 0
        recall_sum = 0.0
        for r in annotated:
            top_k = r["_retrieved_ids"][:k]
            relevant = r["_relevant_ids"]
            if not relevant:
                continue
            if any(rid in relevant for rid in top_k):
                hit_count += 1
            recall_sum += len(set(top_k) & relevant) / len(relevant)
        hit_at_k[k] = round(hit_count / len(annotated), 4)
        recall_at_k[k] = round(recall_sum / len(annotated), 4)

    # MRR
    for r in annotated:
        relevant = r["_relevant_ids"]
        retrieved = r["_retrieved_ids"]
        for rank, rid in enumerate(retrieved, start=1):
            if rid in relevant:
                reciprocal_ranks.append(1.0 / rank)
                break
        else:
            reciprocal_ranks.append(0.0)

    mrr = round(statistics.mean(reciprocal_ranks), 4) if reciprocal_ranks else 0.0

    return {
        "annotated_sample_count": len(annotated),
        "k_values": k_values,
        "hit_at_k": hit_at_k,
        "recall_at_k": recall_at_k,
        "mrr": mrr,
    }


def compute_retrieval_metrics(
    results: list[dict[str, Any]],
    k_values: list[int] | None = None,
) -> dict[str, Any]:
    """Compute parent-level and chunk-level retrieval metrics."""
    if k_values is None:
        k_values = [1, 3, 5, 10]

    parent_pairs: list[tuple[set[int], list[int]]] = []
    chunk_pairs: list[tuple[set[str], list[str]]] = []

    for row in results:
        if row.get("is_demo", False) or not row.get("success"):
            continue

        relevant_parent_ids = _parse_numeric_id_set(row.get("relevant_knowledge_ids"))
        if relevant_parent_ids:
            parent_pairs.append((
                relevant_parent_ids,
                _parse_numeric_id_list(row.get("retrieved_knowledge_ids")),
            ))

        relevant_chunk_ids = _parse_text_id_set(row.get("relevant_chunk_ids"))
        if relevant_chunk_ids:
            chunk_pairs.append((
                relevant_chunk_ids,
                _parse_text_id_list(row.get("retrieved_chunk_ids")),
            ))

    parent_stats = _ranked_retrieval_stats(parent_pairs, k_values)
    chunk_stats = _ranked_retrieval_stats(chunk_pairs, k_values)

    metrics: dict[str, Any] = {
        "annotated_sample_count": len(parent_pairs),
        "k_values": k_values,
        "hit_at_k": parent_stats["hit_at_k"],
        "recall_at_k": parent_stats["recall_at_k"],
        "mrr": parent_stats["mrr"],
        "chunk_annotated_sample_count": len(chunk_pairs),
        "chunk_hit_at_k": chunk_stats["hit_at_k"],
        "chunk_recall_at_k": chunk_stats["recall_at_k"],
        "chunk_mrr": chunk_stats["mrr"],
    }
    if not parent_pairs:
        metrics["note"] = (
            "No samples had relevant_knowledge_ids - Hit@K / Recall@K / MRR unavailable."
        )
    if not chunk_pairs:
        metrics["chunk_note"] = (
            "No samples had relevant_chunk_ids - chunk-level retrieval metrics unavailable."
        )
    return metrics


# ---------------------------------------------------------------------------
# 5. classification metrics
# ---------------------------------------------------------------------------

ALL_RISK_LEVELS = ("可信新闻", "存疑信息", "疑似谣言", "高风险谣言")


def compute_classification_metrics(
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compute Accuracy, Macro P/R/F1, per-class metrics, and confusion matrix.

    Only samples with a valid *gold_label* and *predicted_label* are used.
    An empty result set produces zero-filled metrics (never NaN).
    """
    labeled = [
        r for r in results
        if not r.get("is_demo", False)
        and r.get("success")
        and r.get("gold_label") in ALL_RISK_LEVELS
        and r.get("gold_eligible", True) is True
        and (r.get("predicted_label") in ALL_RISK_LEVELS
             or r.get("assessment_status") in {"insufficient_evidence", "degraded"})
    ]

    if not labeled:
        return {
            "labeled_sample_count": 0,
            "note": "No samples had complete gold_label + predicted_label — classification metrics unavailable.",
            "accuracy": None,
            "macro_precision": None,
            "macro_recall": None,
            "macro_f1": None,
            "per_class": {},
            "confusion_matrix": {},
        }

    golds = [r["gold_label"] for r in labeled]
    preds = ["无法判断" if r.get("assessment_status") in {"insufficient_evidence", "degraded"}
             else r["predicted_label"] for r in labeled]

    # Accuracy
    correct = sum(1 for g, p in zip(golds, preds) if g == p)
    accuracy = round(correct / len(golds), 4)

    # Per-class and macro
    per_class: dict[str, dict[str, Any]] = {}
    precisions: list[float] = []
    recalls: list[float] = []
    f1s: list[float] = []

    for label in ALL_RISK_LEVELS:
        tp = sum(1 for g, p in zip(golds, preds) if g == label and p == label)
        fp = sum(1 for g, p in zip(golds, preds) if g != label and p == label)
        fn = sum(1 for g, p in zip(golds, preds) if g == label and p != label)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

        per_class[label] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        }

        if sum(1 for g in golds if g == label) > 0:  # only include classes present in gold
            precisions.append(precision)
            recalls.append(recall)
            f1s.append(f1)

    macro_precision = round(statistics.mean(precisions), 4) if precisions else 0.0
    macro_recall = round(statistics.mean(recalls), 4) if recalls else 0.0
    macro_f1 = round(statistics.mean(f1s), 4) if f1s else 0.0

    # Confusion matrix (gold (rows) × pred (cols))
    confusion: dict[str, dict[str, int]] = {}
    for g_label in ALL_RISK_LEVELS:
        confusion[g_label] = {p_label: 0 for p_label in (*ALL_RISK_LEVELS, "无法判断")}
    for g, p in zip(golds, preds):
        confusion[g][p] += 1

    return {
        "labeled_sample_count": len(labeled),
        "accuracy": accuracy,
        "accuracy_denominator_includes_abstentions": True,
        "abstention_count": sum(p == "无法判断" for p in preds),
        "assessment_coverage": round(sum(p != "无法判断" for p in preds) / len(preds), 4),
        "selective_accuracy": round(correct / sum(p != "无法判断" for p in preds), 4) if any(p != "无法判断" for p in preds) else None,
        "macro_precision": macro_precision,
        "macro_recall": macro_recall,
        "macro_f1": macro_f1,
        "per_class": per_class,
        "confusion_matrix": confusion,
    }


# ---------------------------------------------------------------------------
# 6. inter-rater agreement
# ---------------------------------------------------------------------------

def compute_inter_rater_agreement(
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compute raw agreement rate and Cohen's Kappa for dual-reviewed samples.

    Only samples where both *reviewer_1_label* AND *reviewer_2_label* are
    valid risk-level strings are included.
    """
    dual = [
        r for r in results
        if not r.get("is_demo", False)
        and r.get("human_review_status", "adjudicated") == "adjudicated"
        and r.get("reviewer_1_label") in ALL_RISK_LEVELS
        and r.get("reviewer_2_label") in ALL_RISK_LEVELS
    ]

    if not dual:
        return {
            "dual_reviewed_count": 0,
            "raw_agreement_rate": None,
            "cohens_kappa": None,
            "note": "No dual-reviewed samples — inter-rater agreement unavailable.",
        }

    r1 = [r["reviewer_1_label"] for r in dual]
    r2 = [r["reviewer_2_label"] for r in dual]

    # Raw agreement — always computable when we have at least 1 sample
    agreements = sum(1 for a, b in zip(r1, r2) if a == b)
    raw_agreement = agreements / len(dual)

    # Cohen's Kappa requires at least 2 samples
    if len(dual) < 2:
        return {
            "dual_reviewed_count": len(dual),
            "raw_agreement_rate": round(raw_agreement, 4),
            "cohens_kappa": None,
            "note": "Only one dual-reviewed sample -- Cohen's Kappa requires at least 2 samples.",
        }

    # Cohen's Kappa
    n = len(dual)
    # Observed agreement matrix
    categories = list(ALL_RISK_LEVELS)
    obs = {c1: {c2: 0 for c2 in categories} for c1 in categories}
    for a, b in zip(r1, r2):
        obs[a][b] += 1

    p_o = agreements / n

    p_e = 0.0
    for c in categories:
        row_sum = sum(obs[c].values())
        col_sum = sum(obs[c2][c] for c2 in categories)
        p_e += (row_sum * col_sum) / (n * n)

    kappa = (p_o - p_e) / (1 - p_e) if (1 - p_e) > 0 else 1.0

    return {
        "dual_reviewed_count": len(dual),
        "raw_agreement_rate": round(raw_agreement, 4),
        "cohens_kappa": round(kappa, 4),
        "note": None,
    }


# ---------------------------------------------------------------------------
# 7. evidence citation completeness
# ---------------------------------------------------------------------------

def compute_evidence_completeness(
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compute evidence citation completeness metrics."""
    success = [r for r in results if r.get("success") and not r.get("is_demo", False)]

    if not success:
        return {
            "note": "No successful samples — evidence completeness metrics unavailable.",
        }

    total = len(success)

    # At least one valid evidence
    has_evidence = [r for r in success if r.get("evidence_count", 0) > 0]
    has_valid_evidence = [r for r in success if r.get("valid_evidence_count", 0) > 0]

    # Key fields complete among those with evidence
    fields_complete = [r for r in has_evidence if r.get("citation_fields_complete")]

    # Valid URL among those with evidence
    valid_url_count = sum(
        1 for r in has_evidence if r.get("evidence_has_valid_url")
    )

    # Evidence insufficient + correct hint
    evidence_insufficient_with_hint = sum(
        1 for r in success
        if r.get("evidence_count", 0) == 0
        and r.get("has_evidence_insufficient_hint")
    )

    # Conclusion exists but zero evidence
    conclusion_no_evidence = sum(
        1 for r in success
        if r.get("evidence_count", 0) == 0
        and r.get("predicted_label")
    )

    return {
        "total_successful": total,
        "at_least_one_evidence_count": len(has_evidence),
        "at_least_one_evidence_rate": round(len(has_evidence) / total, 4),
        "at_least_one_valid_evidence_count": len(has_valid_evidence),
        "at_least_one_valid_evidence_rate": round(len(has_valid_evidence) / total, 4),
        "citation_fields_complete_count": len(fields_complete),
        "citation_fields_complete_rate": round(len(fields_complete) / max(len(has_evidence), 1), 4),
        "evidence_has_valid_url_count": valid_url_count,
        "evidence_has_valid_url_rate": round(valid_url_count / max(len(has_evidence), 1), 4),
        "evidence_insufficient_with_hint_count": evidence_insufficient_with_hint,
        "conclusion_without_evidence_count": conclusion_no_evidence,
    }


# ---------------------------------------------------------------------------
# 8. stability
# ---------------------------------------------------------------------------

def compute_stability_metrics(
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compute stability / robustness metrics."""
    valid = [r for r in results if not r.get("is_demo", False)]
    total = len(valid)
    if total == 0:
        return {"note": "No valid samples — stability metrics unavailable."}

    success = [r for r in valid if r.get("success")]
    failed = [r for r in valid if not r.get("success")]

    # Error type breakdown
    error_types: Counter = Counter()
    for r in failed:
        et = r.get("error_type") or "unknown"
        error_types[et] += 1

    # Among successful, count degradations
    n_success = len(success)
    timeout_count = sum(1 for r in success if r.get("is_timeout"))
    llm_parse_fallback = sum(1 for r in success if r.get("llm_parse_fallback_used"))
    embedding_failed = sum(1 for r in success if r.get("embedding_failed"))
    chroma_failed = sum(1 for r in success if r.get("chroma_failed"))
    web_search_failed = sum(1 for r in success if r.get("web_search_failed"))
    save_failed = sum(1 for r in success if r.get("save_failed"))

    return {
        "overall_success_rate": round(n_success / total, 4),
        "timeout_rate": round(timeout_count / n_success, 4) if n_success else 0.0,
        "llm_parse_fallback_rate": round(llm_parse_fallback / n_success, 4) if n_success else 0.0,
        "embedding_failure_rate": round(embedding_failed / n_success, 4) if n_success else 0.0,
        "chroma_failure_rate": round(chroma_failed / n_success, 4) if n_success else 0.0,
        "web_search_failure_rate": round(web_search_failed / n_success, 4) if n_success else 0.0,
        "save_failure_rate": round(save_failed / n_success, 4) if n_success else 0.0,
        "error_type_breakdown": dict(error_types),
    }


# ---------------------------------------------------------------------------
# aggregate
# ---------------------------------------------------------------------------

def compute_all_metrics(
    results: list[dict[str, Any]],
    k_values: list[int] | None = None,
) -> dict[str, Any]:
    """Run all metric computations and return a single structured dict."""
    return {
        "sample_counts": compute_sample_counts(results),
        "latency": compute_latency_stats(results),
        "web_search": compute_web_trigger_rate(results),
        "retrieval": compute_retrieval_metrics(results, k_values=k_values),
        "classification": compute_classification_metrics(results),
        "inter_rater_agreement": compute_inter_rater_agreement(results),
        "evidence_completeness": compute_evidence_completeness(results),
        "stability": compute_stability_metrics(results),
    }
