from __future__ import annotations

import argparse
import copy
import csv
import json
import math
import random
import statistics
import sys
import time
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable
from unittest.mock import patch

from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    precision_recall_fscore_support,
)


LABELS = ["可信新闻", "存疑信息", "疑似谣言", "高风险谣言"]
LABEL_ALIASES = {
    "可信": "可信新闻",
    "存疑": "存疑信息",
    "疑似谣言": "疑似谣言",
    "高风险": "高风险谣言",
}


def classify_score(score: float) -> str:
    if score >= 80:
        return "可信新闻"
    if score >= 60:
        return "存疑信息"
    if score >= 40:
        return "疑似谣言"
    return "高风险谣言"


def analyze_web_trigger_thresholds(
    rows: list[dict[str, Any]], thresholds: list[float]
) -> list[dict[str, Any]]:
    """Count counterfactual triggers for the top-1 rule only.

    This deliberately does not infer web-search outcomes. It answers only how
    often the saved top-1 similarities would cross each threshold.
    """
    similarities = [
        float(row["top_similarity"])
        for row in rows
        if str(row.get("top_similarity") or "").strip()
    ]
    result: list[dict[str, Any]] = []
    for threshold in thresholds:
        triggered = sum(value < threshold for value in similarities)
        result.append(
            {
                "top1_threshold": round(float(threshold), 4),
                "sample_count": len(similarities),
                "trigger_count": triggered,
                "trigger_rate": round(triggered / len(similarities), 4)
                if similarities
                else 0.0,
                "no_trigger_count": len(similarities) - triggered,
                "scope_note": "仅根据已保存Top-1相似度反事实计数；未实际调用联网服务",
            }
        )
    return result


def analyze_evidence_quality_weights(
    rows: list[dict[str, Any]], weights: list[float]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Vary evidence-quality weight while preserving the LLM:rule ratio 5:2."""
    predictions: list[dict[str, Any]] = []
    metrics: list[dict[str, Any]] = []
    for weight in weights:
        if not 0 <= weight <= 1:
            raise ValueError("Evidence-quality weight must be between 0 and 1")
        variant_rows: list[dict[str, Any]] = []
        remaining = 1 - weight
        for row in rows:
            if bool(row.get("has_effective_evidence")):
                score = (
                    float(row["llm_score"]) * remaining * (5 / 7)
                    + float(row["evidence_quality_score"]) * weight
                    + float(row["rule_score"]) * remaining * (2 / 7)
                )
            else:
                score = float(row["llm_score"]) * 0.6 + float(row["rule_score"]) * 0.4
            out = {
                **row,
                "evidence_quality_weight": round(float(weight), 4),
                "final_score": round(score, 2),
                "predicted_label": classify_score(score),
            }
            variant_rows.append(out)
            predictions.append(out)
        metric = _metric_row(
            f"EQ-Weight-{weight:.2f}",
            variant_rows,
            "有效证据分支保持LLM:规则=5:2；无证据分支不变；离线重算",
        )
        metric["evidence_quality_weight"] = round(float(weight), 4)
        metrics.append(metric)
    return predictions, metrics


def _classify_shifted_score(score: float, shift: float) -> str:
    if score >= 80 + shift:
        return "可信新闻"
    if score >= 60 + shift:
        return "存疑信息"
    if score >= 40 + shift:
        return "疑似谣言"
    return "高风险谣言"


def analyze_risk_threshold_shifts(
    rows: list[dict[str, Any]], shifts: list[float]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    predictions: list[dict[str, Any]] = []
    metrics: list[dict[str, Any]] = []
    for shift in shifts:
        variant_rows: list[dict[str, Any]] = []
        for row in rows:
            score = float(row["final_score"])
            out = {
                **row,
                "contract_status": row.get("contract_status", "not_applicable"),
                "threshold_shift": float(shift),
                "trusted_cutoff": 80 + float(shift),
                "suspicious_cutoff": 60 + float(shift),
                "rumor_cutoff": 40 + float(shift),
                "predicted_label": _classify_shifted_score(score, float(shift)),
            }
            variant_rows.append(out)
            predictions.append(out)
        metric = _metric_row(
            f"Risk-Threshold-Shift-{shift:+g}",
            variant_rows,
            "三个生产风险分界点同向平移；仅作探索性离线重分类",
        )
        metric.update(
            {
                "threshold_shift": float(shift),
                "trusted_cutoff": 80 + float(shift),
                "suspicious_cutoff": 60 + float(shift),
                "rumor_cutoff": 40 + float(shift),
            }
        )
        metrics.append(metric)

    distances = [
        min(abs(float(row["final_score"]) - cutoff) for cutoff in (40, 60, 80))
        for row in rows
    ]
    proximity = []
    for margin in (2, 5):
        count = sum(distance <= margin for distance in distances)
        proximity.append(
            {
                "margin": margin,
                "sample_count": count,
                "sample_rate": round(count / len(distances), 4) if distances else 0.0,
                "total_samples": len(distances),
                "scope_note": "与40/60/80任一生产分界点的绝对距离不超过该边界",
            }
        )
    return predictions, metrics, proximity


def recompute_ablation_score(
    *,
    variant: str,
    llm_score: float,
    evidence_quality_score: float,
    rule_score: float,
    has_effective_evidence: bool,
    is_llm_degraded: bool,
) -> float:
    """Re-score one saved observation without changing production logic.

    Removed components are not replaced by zero. Remaining production weights
    are normalized to sum to one. A variant is unavailable when removing the
    rule component leaves a degraded observation with no score source.
    """
    if variant == "Full":
        if is_llm_degraded:
            return round(rule_score, 2)
        if not has_effective_evidence:
            return round(llm_score * 0.6 + rule_score * 0.4, 2)
        return round(
            llm_score * 0.5 + evidence_quality_score * 0.3 + rule_score * 0.2,
            2,
        )
    if variant == "No-Evidence-Quality":
        if is_llm_degraded:
            return round(rule_score, 2)
        if not has_effective_evidence:
            return round(llm_score * 0.6 + rule_score * 0.4, 2)
        return round(llm_score * (5 / 7) + rule_score * (2 / 7), 2)
    if variant == "No-Rule":
        if is_llm_degraded:
            return math.nan
        if not has_effective_evidence:
            return round(llm_score, 2)
        return round(llm_score * 0.625 + evidence_quality_score * 0.375, 2)
    raise ValueError(f"Unsupported variant: {variant}")


def derive_no_focused_retry_outcome(
    *,
    initial_contract_valid: bool,
    is_llm_degraded: bool,
    llm_score: float,
    rule_score_without_evidence: float,
    full_score: float,
) -> dict[str, Any]:
    if initial_contract_valid:
        score = round(full_score, 2)
        status = "initial_contract_ok"
    elif is_llm_degraded:
        score = round(rule_score_without_evidence, 2)
        status = "provider_error"
    else:
        score = round(llm_score * 0.6 + rule_score_without_evidence * 0.4, 2)
        status = "initial_contract_rejected"
    return {
        "final_score": score,
        "predicted_label": classify_score(score),
        "status": status,
    }


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        if fields:
            writer.writeheader()
            writer.writerows(rows)


def _metric_row(variant: str, rows: list[dict[str, Any]], note: str) -> dict[str, Any]:
    gold = [row["gold_label"] for row in rows]
    predicted = [row["predicted_label"] for row in rows]
    precision, recall, f1, _ = precision_recall_fscore_support(
        gold,
        predicted,
        labels=LABELS,
        zero_division=0,
    )
    _, _, macro_f1, _ = precision_recall_fscore_support(
        gold, predicted, labels=LABELS, average="macro", zero_division=0
    )
    _, _, weighted_f1, _ = precision_recall_fscore_support(
        gold, predicted, labels=LABELS, average="weighted", zero_division=0
    )
    applicable_contract_rows = [
        row for row in rows if row["contract_status"] != "not_applicable"
    ]
    contract_pass_rate: float | str = "N/A"
    if applicable_contract_rows:
        contract_pass_rate = round(
            sum(
                row["contract_status"] in {"ok", "no_evidence"}
                for row in applicable_contract_rows
            )
            / len(applicable_contract_rows),
            4,
        )
    result: dict[str, Any] = {
        "variant": variant,
        "sample_count": len(rows),
        "accuracy": round(float(accuracy_score(gold, predicted)), 4),
        "macro_f1": round(float(macro_f1), 4),
        "weighted_f1": round(float(weighted_f1), 4),
        "balanced_accuracy": round(float(balanced_accuracy_score(gold, predicted)), 4),
        "high_risk_recall": round(float(recall[LABELS.index("高风险谣言")]), 4),
        "mean_final_score": round(statistics.fmean(row["final_score"] for row in rows), 4),
        "contract_pass_rate": contract_pass_rate,
        "note": note,
    }
    for index, label in enumerate(LABELS):
        prefix = {
            "可信新闻": "trusted",
            "存疑信息": "suspicious",
            "疑似谣言": "rumor",
            "高风险谣言": "high_risk",
        }[label]
        result[f"{prefix}_precision"] = round(float(precision[index]), 4)
        result[f"{prefix}_recall"] = round(float(recall[index]), 4)
        result[f"{prefix}_f1"] = round(float(f1[index]), 4)
    return result


def _percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def summarize_stage_timings(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[float]] = {}
    for row in rows:
        raw = row.get("stage_timings_ms") or "{}"
        timings = json.loads(raw) if isinstance(raw, str) else dict(raw)
        for stage, value in timings.items():
            grouped.setdefault((str(row["policy"]), str(stage)), []).append(float(value))

    summary: list[dict[str, Any]] = []
    for (policy, stage), values in sorted(grouped.items()):
        summary.append(
            {
                "policy": policy,
                "stage": stage,
                "sample_count": len(values),
                "mean_ms": round(statistics.fmean(values), 2),
                "p50_ms": round(_percentile(values, 0.50), 2),
                "p95_ms": round(_percentile(values, 0.95), 2),
                "min_ms": round(min(values), 2),
                "max_ms": round(max(values), 2),
                "stddev_ms": round(statistics.pstdev(values), 2),
                "scope_note": "隔离低覆盖实验；本地检索为空结果；数据库保存为内存模拟",
            }
        )
    return summary


def _macro_f1(gold: list[str], predicted: list[str]) -> float:
    scores: list[float] = []
    for label in LABELS:
        tp = sum(truth == label and guess == label for truth, guess in zip(gold, predicted))
        fp = sum(truth != label and guess == label for truth, guess in zip(gold, predicted))
        fn = sum(truth == label and guess != label for truth, guess in zip(gold, predicted))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        scores.append(
            2 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )
    return statistics.fmean(scores)


def _accuracy(gold: list[str], predicted: list[str]) -> float:
    return sum(truth == guess for truth, guess in zip(gold, predicted)) / len(gold)


def paired_bootstrap_comparison(
    baseline_rows: list[dict[str, Any]],
    variant_rows: list[dict[str, Any]],
    *,
    baseline_name: str,
    variant_name: str,
    iterations: int = 5000,
    seed: int = 20260701,
) -> dict[str, Any]:
    baseline = {row["sample_id"]: row for row in baseline_rows}
    variant = {row["sample_id"]: row for row in variant_rows}
    sample_ids = sorted(set(baseline) & set(variant))
    if not sample_ids:
        raise ValueError("Paired comparison has no shared samples")

    gold = [baseline[sid]["gold_label"] for sid in sample_ids]
    baseline_pred = [baseline[sid]["predicted_label"] for sid in sample_ids]
    variant_pred = [variant[sid]["predicted_label"] for sid in sample_ids]
    accuracy_delta = _accuracy(gold, variant_pred) - _accuracy(gold, baseline_pred)
    macro_delta = _macro_f1(gold, variant_pred) - _macro_f1(gold, baseline_pred)

    rng = random.Random(seed)
    accuracy_deltas: list[float] = []
    macro_deltas: list[float] = []
    for _ in range(iterations):
        indices = [rng.randrange(len(sample_ids)) for _ in sample_ids]
        boot_gold = [gold[index] for index in indices]
        boot_baseline = [baseline_pred[index] for index in indices]
        boot_variant = [variant_pred[index] for index in indices]
        accuracy_deltas.append(
            float(
                _accuracy(boot_gold, boot_variant)
                - _accuracy(boot_gold, boot_baseline)
            )
        )
        macro_deltas.append(
            _macro_f1(boot_gold, boot_variant) - _macro_f1(boot_gold, boot_baseline)
        )

    baseline_only_correct = sum(
        base == truth and candidate != truth
        for truth, base, candidate in zip(gold, baseline_pred, variant_pred)
    )
    variant_only_correct = sum(
        base != truth and candidate == truth
        for truth, base, candidate in zip(gold, baseline_pred, variant_pred)
    )
    discordant = baseline_only_correct + variant_only_correct
    if discordant:
        tail = min(baseline_only_correct, variant_only_correct)
        exact_p = min(
            1.0,
            2
            * sum(
                math.comb(discordant, value) * (0.5**discordant)
                for value in range(tail + 1)
            ),
        )
    else:
        exact_p = 1.0

    return {
        "baseline": baseline_name,
        "variant": variant_name,
        "sample_count": len(sample_ids),
        "accuracy_delta": round(accuracy_delta, 4),
        "accuracy_ci_low": round(_percentile(accuracy_deltas, 0.025), 4),
        "accuracy_ci_high": round(_percentile(accuracy_deltas, 0.975), 4),
        "macro_f1_delta": round(macro_delta, 4),
        "macro_f1_ci_low": round(_percentile(macro_deltas, 0.025), 4),
        "macro_f1_ci_high": round(_percentile(macro_deltas, 0.975), 4),
        "baseline_only_correct": baseline_only_correct,
        "variant_only_correct": variant_only_correct,
        "discordant_pairs": discordant,
        "mcnemar_exact_p": round(exact_p, 6),
        "bootstrap_iterations": iterations,
        "seed": seed,
    }


def run_ablation(project_root: Path, output_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    backend = project_root / "backend"
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))

    from app.db.session import SessionLocal
    from app.models.detection_record import DetectionRecord
    from app.services.rule_score_service import calculate_rule_score

    news = _read_csv(project_root / "evaluation" / "datasets" / "news_eval.csv")
    per_case = _read_csv(project_root / "evaluation" / "output" / "per_case_results.csv")
    news_by_title = {row["title"]: row for row in news}
    case_by_id = {row["sample_id"]: row for row in per_case}

    start = datetime(2026, 6, 24, 20, 50, 0)
    end = datetime(2026, 6, 24, 21, 30, 0)
    observations: list[dict[str, Any]] = []
    with SessionLocal() as db:
        records = (
            db.query(DetectionRecord)
            .filter(DetectionRecord.input_title.in_(list(news_by_title)))
            .filter(DetectionRecord.created_at >= start, DetectionRecord.created_at <= end)
            .all()
        )
        for record in records:
            source = news_by_title.get(record.input_title)
            if source is None:
                continue
            case = case_by_id[source["sample_id"]]
            try:
                payload = json.loads(record.analysis_payload or "{}")
            except json.JSONDecodeError:
                payload = {}
            evidence_quality = payload.get("evidence_quality") or {}
            contract_status = str(payload.get("arbitration_status") or "unavailable")
            candidates = list(payload.get("candidate_evidence_list") or [])
            use_all_rule = calculate_rule_score(
                title=source["title"],
                content=source["content"],
                source_name=payload.get("source_name"),
                evidence_list=candidates,
            )
            observations.append(
                {
                    "sample_id": source["sample_id"],
                    "gold_label": LABEL_ALIASES.get(source["gold_label"], source["gold_label"]),
                    "llm_score": float(record.llm_score),
                    "evidence_quality_score": float(evidence_quality.get("score") or 0),
                    "rule_score": float(record.rule_score),
                    "use_all_rule_score": float(use_all_rule.get("rule_score") or 0),
                    "full_score_saved": float(record.final_score),
                    "has_effective_evidence": bool(list(record.evidence_matches)),
                    "candidate_count": len(candidates),
                    "is_llm_degraded": contract_status == "provider_error",
                    "contract_status": contract_status,
                    "total_latency_ms": float(case["total_latency_ms"]),
                }
            )

    observations.sort(key=lambda row: row["sample_id"])
    common = [row for row in observations if not row["is_llm_degraded"]]
    prediction_rows: list[dict[str, Any]] = []
    metric_rows: list[dict[str, Any]] = []

    for variant in ["Full", "No-Evidence-Quality", "No-Rule", "Use-All-Candidates"]:
        variant_rows: list[dict[str, Any]] = []
        for row in common:
            scoring_variant = "Full" if variant == "Use-All-Candidates" else variant
            score = recompute_ablation_score(
                variant=scoring_variant,
                llm_score=row["llm_score"],
                evidence_quality_score=row["evidence_quality_score"],
                rule_score=(
                    row["use_all_rule_score"]
                    if variant == "Use-All-Candidates"
                    else row["rule_score"]
                ),
                has_effective_evidence=(
                    row["candidate_count"] > 0
                    if variant == "Use-All-Candidates"
                    else row["has_effective_evidence"]
                ),
                is_llm_degraded=row["is_llm_degraded"],
            )
            predicted = classify_score(score)
            out = {
                **row,
                "variant": variant,
                "final_score": score,
                "predicted_label": predicted,
                "contract_status": (
                    "not_applicable"
                    if variant == "Use-All-Candidates"
                    else row["contract_status"]
                ),
                "weight_policy": {
                    "Full": "生产分支原权重",
                    "No-Evidence-Quality": "移除证据质量分后，剩余权重按5:2归一化；无证据/降级分支不变",
                    "No-Rule": "移除规则分后，有证据分支按5:3归一化；无证据分支仅用LLM分",
                    "Use-All-Candidates": "跳过仲裁并将全部候选作为有效证据；复用同次LLM分与证据质量分，重新计算规则分",
                }[variant],
            }
            prediction_rows.append(out)
            variant_rows.append(out)
        metric_rows.append(
            _metric_row(
                variant,
                variant_rows,
                (
                    "共同可评估子集；跳过契约校验并使用全部候选；离线重算未重复调用模型"
                    if variant == "Use-All-Candidates"
                    else "共同可评估子集；排除仅剩规则分的LLM降级样本，离线重算未重复调用模型"
                ),
            )
        )

    full_all: list[dict[str, Any]] = []
    for row in observations:
        score = row["full_score_saved"]
        full_all.append({**row, "final_score": score, "predicted_label": classify_score(score)})
    metric_rows.append(
        _metric_row(
            "Full-All",
            full_all,
            "完整80条原始运行；包含规则降级样本；用于总体结果，不与No-Rule作净效应比较",
        )
    )
    metric_rows.append(
        _metric_row(
            "No-Web",
            full_all,
            "原运行80条联网触发为0，实际执行路径与Full-All完全相同",
        )
    )

    _write_csv(output_dir / "ablation_predictions.csv", prediction_rows)
    _write_csv(output_dir / "ablation_metrics.csv", metric_rows)
    by_variant = {
        variant: [row for row in prediction_rows if row["variant"] == variant]
        for variant in ["Full", "No-Evidence-Quality", "No-Rule", "Use-All-Candidates"]
    }
    paired_rows = [
        paired_bootstrap_comparison(
            by_variant["Full"],
            by_variant[variant],
            baseline_name="Full",
            variant_name=variant,
        )
        for variant in ["No-Evidence-Quality", "No-Rule", "Use-All-Candidates"]
    ]
    _write_csv(output_dir / "ablation_paired_statistics.csv", paired_rows)
    return prediction_rows, metric_rows


def run_parameter_sensitivity(
    project_root: Path,
    output_dir: Path,
    ablation_predictions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    formal_rows = _read_csv(project_root / "evaluation" / "output" / "per_case_results.csv")
    formal_success = [
        {
            **row,
            "gold_label": LABEL_ALIASES.get(row["gold_label"], row["gold_label"]),
            "final_score": float(row["final_score"]),
        }
        for row in formal_rows
        if _truthy(row.get("success"))
    ]

    web_rows = analyze_web_trigger_thresholds(
        formal_success, [0.45, 0.60, 0.75, 0.80, 0.85, 0.90]
    )
    _write_csv(output_dir / "web_trigger_threshold_sensitivity.csv", web_rows)

    full_common = [
        row for row in ablation_predictions if row.get("variant") == "Full"
    ]
    eq_predictions, eq_metrics = analyze_evidence_quality_weights(
        full_common, [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
    )
    _write_csv(
        output_dir / "evidence_quality_weight_sensitivity_predictions.csv",
        eq_predictions,
    )
    _write_csv(
        output_dir / "evidence_quality_weight_sensitivity_metrics.csv", eq_metrics
    )

    risk_predictions, risk_metrics, risk_proximity = analyze_risk_threshold_shifts(
        formal_success, [-5, 0, 5]
    )
    _write_csv(
        output_dir / "risk_threshold_sensitivity_predictions.csv", risk_predictions
    )
    _write_csv(output_dir / "risk_threshold_sensitivity_metrics.csv", risk_metrics)
    _write_csv(output_dir / "risk_threshold_proximity.csv", risk_proximity)

    combined: list[dict[str, Any]] = []
    for k in (1, 3, 5, 10):
        combined.append(
            {
                "parameter": "Top-K",
                "value": k,
                "metric": "Recall@K",
                "metric_value": 1.0,
                "sample_count": 80,
                "data_scope": "既有80条整体评测（探索性，非验证集调参）",
            }
        )
    for row in web_rows:
        combined.append(
            {
                "parameter": "Web-Top1-Threshold",
                "value": row["top1_threshold"],
                "metric": "Counterfactual-Trigger-Rate",
                "metric_value": row["trigger_rate"],
                "sample_count": row["sample_count"],
                "data_scope": "仅Top-1规则反事实计数；未调用联网服务",
            }
        )
    for row in eq_metrics:
        for metric_name in ("accuracy", "macro_f1"):
            combined.append(
                {
                    "parameter": "Evidence-Quality-Weight",
                    "value": row["evidence_quality_weight"],
                    "metric": metric_name,
                    "metric_value": row[metric_name],
                    "sample_count": row["sample_count"],
                    "data_scope": "68条共同子集离线重算；保持LLM:规则=5:2",
                }
            )
    for row in risk_metrics:
        for metric_name in ("accuracy", "macro_f1"):
            combined.append(
                {
                    "parameter": "Risk-Threshold-Shift",
                    "value": row["threshold_shift"],
                    "metric": metric_name,
                    "metric_value": row[metric_name],
                    "sample_count": row["sample_count"],
                    "data_scope": "正式80条原运行保存分数离线重分类",
                }
            )
    for row in risk_proximity:
        combined.append(
            {
                "parameter": "Risk-Boundary-Margin",
                "value": row["margin"],
                "metric": "sample_rate",
                "metric_value": row["sample_rate"],
                "sample_count": row["total_samples"],
                "data_scope": "与40/60/80任一生产分界点的距离",
            }
        )
    _write_csv(output_dir / "sensitivity_analysis.csv", combined)
    return combined


def _timed(stage_times: dict[str, list[float]], name: str, fn: Callable[..., Any]) -> Callable[..., Any]:
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        try:
            return fn(*args, **kwargs)
        finally:
            stage_times.setdefault(name, []).append((time.perf_counter() - start) * 1000)

    return wrapper


def merge_web_summary_rows(
    existing: list[dict[str, Any]],
    new: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged = {
        (str(row["sample_id"]), str(row["policy"])): dict(row)
        for row in existing
    }
    for row in new:
        merged[(str(row["sample_id"]), str(row["policy"]))] = dict(row)
    policy_order = {"Local-only": 0, "Local+Web": 1}
    return sorted(
        merged.values(),
        key=lambda row: (
            str(row["sample_id"]),
            policy_order.get(str(row["policy"]), 99),
        ),
    )


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def summarize_web_pair_results(
    rows: list[dict[str, Any]],
    *,
    bootstrap_iterations: int = 5000,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        normalized.append(
            {
                **row,
                "final_score": float(row.get("final_score") or 0),
                "total_ms": float(row.get("total_ms") or 0),
                "web_candidate_count": int(float(row.get("web_candidate_count") or 0)),
                "web_effective_count": int(float(row.get("web_effective_count") or 0)),
                "web_triggered": _truthy(row.get("web_triggered")),
                "contract_status": str(row.get("arbitration_status") or "unavailable"),
            }
        )

    metrics: list[dict[str, Any]] = []
    by_policy: dict[str, list[dict[str, Any]]] = {}
    for policy in ["Local-only", "Local+Web"]:
        policy_rows = [row for row in normalized if row["policy"] == policy]
        by_policy[policy] = policy_rows
        metric = _metric_row(
            policy,
            policy_rows,
            "隔离低覆盖配对样本；本地知识固定为空；数据库保存为内存模拟",
        )
        metric["policy"] = metric.pop("variant")
        latencies = [row["total_ms"] for row in policy_rows]
        metric.update(
            {
                "triggered_count": sum(row["web_triggered"] for row in policy_rows),
                "web_candidate_count": sum(row["web_candidate_count"] for row in policy_rows),
                "web_effective_count": sum(row["web_effective_count"] for row in policy_rows),
                "provider_error_count": sum(
                    row["contract_status"] == "provider_error" for row in policy_rows
                ),
                "mean_ms": round(statistics.fmean(latencies), 2),
                "p50_ms": round(_percentile(latencies, 0.50), 2),
                "p95_ms": round(_percentile(latencies, 0.95), 2),
            }
        )
        metrics.append(metric)

    paired = paired_bootstrap_comparison(
        by_policy["Local-only"],
        by_policy["Local+Web"],
        baseline_name="Local-only",
        variant_name="Local+Web",
        iterations=bootstrap_iterations,
        seed=20260702,
    )
    local_map = {row["sample_id"]: row for row in by_policy["Local-only"]}
    web_map = {row["sample_id"]: row for row in by_policy["Local+Web"]}
    shared = sorted(set(local_map) & set(web_map))
    paired["label_change_count"] = sum(
        local_map[sid]["predicted_label"] != web_map[sid]["predicted_label"]
        for sid in shared
    )
    paired["mean_score_delta"] = round(
        statistics.fmean(
            web_map[sid]["final_score"] - local_map[sid]["final_score"]
            for sid in shared
        ),
        4,
    )
    return metrics, paired


def run_low_coverage_web_experiment(
    project_root: Path,
    output_dir: Path,
    sample_ids: list[str],
    *,
    append_existing: bool = False,
) -> list[dict[str, Any]]:
    backend = project_root / "backend"
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))

    from app.db.session import SessionLocal
    from app.schemas.detection import DetectNewsRequest
    from app.services import detection_service as ds

    news = _read_csv(project_root / "evaluation" / "datasets" / "news_eval.csv")
    selected = [row for row in news if row["sample_id"] in set(sample_ids)]
    selected.sort(key=lambda row: sample_ids.index(row["sample_id"]))
    if len(selected) != len(sample_ids):
        missing = sorted(set(sample_ids) - {row["sample_id"] for row in selected})
        raise ValueError(f"Unknown sample ids: {missing}")

    raw_dir = output_dir / "web_low_coverage_raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "web_low_coverage_summary.csv"
    existing = (
        _read_csv(summary_path)
        if append_existing and summary_path.exists()
        else []
    )
    existing_keys = {
        (row["sample_id"], row["policy"])
        for row in existing
    }
    new_summary: list[dict[str, Any]] = []
    with SessionLocal() as db:
        for source in selected:
            for policy, allow_web in [("Local-only", False), ("Local+Web", True)]:
                if (source["sample_id"], policy) in existing_keys:
                    continue
                stage_times: dict[str, list[float]] = {}
                fake_id = len(existing) + len(new_summary) + 1

                def empty_search(*args: Any, **kwargs: Any) -> list[Any]:
                    return []

                def fake_save(db_arg: Any, detection_in: Any) -> Any:
                    return SimpleNamespace(id=fake_id, created_at=datetime.now(timezone.utc))

                started_at = datetime.now(timezone.utc).isoformat()
                wall_start = time.perf_counter()
                error = ""
                result: dict[str, Any] = {}
                originals = {
                    "extract_keywords": ds.extract_keywords,
                    "search_evidence": ds.search_evidence,
                    "analyze_news_credibility": ds.analyze_news_credibility,
                    "analyze_evidence_arbitration": ds.analyze_evidence_arbitration,
                    "calculate_rule_score": ds.calculate_rule_score,
                }
                try:
                    with ExitStack() as stack:
                        stack.enter_context(patch.object(ds, "_search_top10_evidence", _timed(stage_times, "local_retrieval", empty_search)))
                        stack.enter_context(patch.object(ds, "save_detection_record", _timed(stage_times, "database_save_mock", fake_save)))
                        for name, fn in originals.items():
                            stack.enter_context(patch.object(ds, name, _timed(stage_times, name, fn)))
                        result = ds.detect_news_credibility(
                            db=db,
                            payload=DetectNewsRequest(
                                title=source["title"],
                                content=source["content"],
                                source_url=source.get("url") or None,
                                enable_web_search=allow_web,
                            ),
                            current_user=None,
                        )
                except Exception as exc:  # preserve actual experiment failure
                    error = f"{type(exc).__name__}: {exc}"
                total_ms = round((time.perf_counter() - wall_start) * 1000, 2)
                candidate_list = result.get("candidate_evidence_list") or []
                effective = result.get("evidence_list") or []
                row = {
                    "sample_id": source["sample_id"],
                    "topic_id": source["topic_id"],
                    "gold_label": LABEL_ALIASES.get(source["gold_label"], source["gold_label"]),
                    "policy": policy,
                    "isolated_local_kb_count": 0,
                    "success": not bool(error),
                    "web_triggered": bool(result.get("web_search_triggered", False)),
                    "web_candidate_count": sum(item.get("source_type") == "web_search" for item in candidate_list),
                    "web_effective_count": sum(item.get("source_type") == "web_search" for item in effective),
                    "candidate_count": len(candidate_list),
                    "effective_evidence_count": len(effective),
                    "final_score": result.get("final_score", ""),
                    "predicted_label": result.get("risk_level", ""),
                    "arbitration_status": result.get("arbitration_status", ""),
                    "total_ms": total_ms,
                    "stage_timings_ms": json.dumps(
                        {name: round(sum(values), 2) for name, values in stage_times.items()},
                        ensure_ascii=False,
                    ),
                    "started_at_utc": started_at,
                    "error": error,
                }
                new_summary.append(row)
                raw_path = raw_dir / f"{source['sample_id']}_{policy.replace('+', '_').replace('-', '_')}.json"
                raw_path.write_text(
                    json.dumps(
                        {
                            "experiment": row,
                            "result": result,
                            "isolation": "本地检索函数在进程内替换为空结果；正式Chroma与MySQL均未修改；保存函数替换为内存对象",
                        },
                        ensure_ascii=False,
                        indent=2,
                        default=str,
                    ),
                    encoding="utf-8",
                )

    summary = merge_web_summary_rows(existing, new_summary)
    _write_csv(summary_path, summary)
    _write_csv(output_dir / "performance_stage_summary.csv", summarize_stage_timings(summary))
    web_metrics, web_paired = summarize_web_pair_results(summary)
    _write_csv(output_dir / "web_low_coverage_metrics.csv", web_metrics)
    _write_csv(output_dir / "web_low_coverage_paired_statistics.csv", [web_paired])
    return summary


def _retry_ablation_outputs(
    summary: list[dict[str, Any]],
    output_dir: Path,
) -> None:
    full_rows: list[dict[str, Any]] = []
    no_retry_rows: list[dict[str, Any]] = []
    for row in summary:
        full_rows.append(
            {
                "sample_id": row["sample_id"],
                "gold_label": row["gold_label"],
                "predicted_label": row["full_predicted_label"],
                "final_score": float(row["full_final_score"]),
                "contract_status": row["full_arbitration_status"],
            }
        )
        no_retry_rows.append(
            {
                "sample_id": row["sample_id"],
                "gold_label": row["gold_label"],
                "predicted_label": row["no_retry_predicted_label"],
                "final_score": float(row["no_retry_final_score"]),
                "contract_status": (
                    "ok" if _truthy(row["initial_contract_valid"]) else "retry_disabled"
                ),
            }
        )
    metrics = [
        _metric_row("Full", full_rows, "同一次首次模型输出；允许一次聚焦重试"),
        _metric_row(
            "No-Focused-Retry",
            no_retry_rows,
            "同一次首次模型输出；首次契约失败时直接采用无证据分支",
        ),
    ]
    paired = paired_bootstrap_comparison(
        full_rows,
        no_retry_rows,
        baseline_name="Full",
        variant_name="No-Focused-Retry",
        iterations=5000,
        seed=20260703,
    )
    paired["label_change_count"] = sum(
        full["predicted_label"] != no_retry["predicted_label"]
        for full, no_retry in zip(full_rows, no_retry_rows)
    )
    paired["retry_triggered_count"] = sum(
        _truthy(row["retry_triggered"]) for row in summary
    )
    paired["retry_fixed_count"] = sum(
        _truthy(row["retry_triggered"])
        and row["full_arbitration_status"] == "ok"
        for row in summary
    )
    _write_csv(output_dir / "retry_ablation_metrics.csv", metrics)
    _write_csv(output_dir / "retry_ablation_paired_statistics.csv", [paired])


def run_retry_ablation_experiment(
    project_root: Path,
    output_dir: Path,
    sample_ids: list[str],
    *,
    append_existing: bool = False,
) -> list[dict[str, Any]]:
    backend = project_root / "backend"
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))

    from app.db.session import SessionLocal
    from app.schemas.detection import DetectNewsRequest
    from app.services import detection_service as ds
    from app.services.rule_score_service import calculate_rule_score

    news = _read_csv(project_root / "evaluation" / "datasets" / "news_eval.csv")
    selected = [row for row in news if row["sample_id"] in set(sample_ids)]
    selected.sort(key=lambda row: sample_ids.index(row["sample_id"]))
    if len(selected) != len(sample_ids):
        missing = sorted(set(sample_ids) - {row["sample_id"] for row in selected})
        raise ValueError(f"Unknown sample ids: {missing}")

    summary_path = output_dir / "retry_ablation_summary.csv"
    existing = (
        _read_csv(summary_path)
        if append_existing and summary_path.exists()
        else []
    )
    existing_ids = {row["sample_id"] for row in existing}
    new_rows: list[dict[str, Any]] = []
    raw_dir = output_dir / "retry_ablation_raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    with SessionLocal() as db:
        for source in selected:
            if source["sample_id"] in existing_ids:
                continue
            captured: dict[str, Any] = {"initial": None, "retry": None}
            fake_id = len(existing) + len(new_rows) + 1

            def fake_save(db_arg: Any, detection_in: Any) -> Any:
                return SimpleNamespace(id=fake_id, created_at=datetime.now(timezone.utc))

            original_initial = ds.analyze_news_credibility
            original_retry = ds.analyze_evidence_arbitration

            def capture_initial(*args: Any, **kwargs: Any) -> dict[str, Any]:
                value = original_initial(*args, **kwargs)
                captured["initial"] = copy.deepcopy(value)
                return value

            def capture_retry(*args: Any, **kwargs: Any) -> dict[str, Any]:
                value = original_retry(*args, **kwargs)
                captured["retry"] = copy.deepcopy(value)
                return value

            wall_start = time.perf_counter()
            error = ""
            result: dict[str, Any] = {}
            try:
                with ExitStack() as stack:
                    stack.enter_context(patch.object(ds, "save_detection_record", fake_save))
                    stack.enter_context(patch.object(ds, "analyze_news_credibility", capture_initial))
                    stack.enter_context(patch.object(ds, "analyze_evidence_arbitration", capture_retry))
                    result = ds.detect_news_credibility(
                        db=db,
                        payload=DetectNewsRequest(
                            title=source["title"],
                            content=source["content"],
                            source_url=source.get("url") or None,
                            enable_web_search=False,
                        ),
                        current_user=None,
                    )
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
            total_ms = round((time.perf_counter() - wall_start) * 1000, 2)
            if error:
                row = {
                    "sample_id": source["sample_id"],
                    "topic_id": source["topic_id"],
                    "gold_label": LABEL_ALIASES.get(source["gold_label"], source["gold_label"]),
                    "success": False,
                    "error": error,
                    "total_ms": total_ms,
                }
                new_rows.append(row)
                continue

            initial = captured["initial"] or {}
            candidates = result.get("candidate_evidence_list") or []
            is_degraded = ds._is_llm_failure(initial)
            initial_ranking = {"errors": ["provider_error"]}
            quality_errors: list[str] = []
            if not is_degraded:
                arbitration = initial.get("evidence_arbitration")
                initial_ranking = (
                    ds.validate_and_apply_llm_ranking(candidates, arbitration)
                    if isinstance(arbitration, dict)
                    else {"errors": ["missing evidence_arbitration"]}
                )
                quality_errors = ds._validate_evidence_quality(initial.get("evidence_quality"))
            initial_contract_valid = not initial_ranking["errors"] and not quality_errors
            rule_without = calculate_rule_score(
                title=source["title"],
                content=source["content"],
                source_name=None,
                evidence_list=[],
            )
            no_retry = derive_no_focused_retry_outcome(
                initial_contract_valid=initial_contract_valid,
                is_llm_degraded=is_degraded,
                llm_score=float(initial.get("llm_score") or 0),
                rule_score_without_evidence=float(rule_without.get("rule_score") or 0),
                full_score=float(result.get("final_score") or 0),
            )
            row = {
                "sample_id": source["sample_id"],
                "topic_id": source["topic_id"],
                "gold_label": LABEL_ALIASES.get(source["gold_label"], source["gold_label"]),
                "success": True,
                "candidate_count": len(candidates),
                "initial_contract_valid": initial_contract_valid,
                "initial_contract_errors": "; ".join(
                    [*initial_ranking["errors"], *quality_errors]
                ),
                "retry_triggered": captured["retry"] is not None,
                "full_arbitration_status": result.get("arbitration_status", ""),
                "full_final_score": result.get("final_score", ""),
                "full_predicted_label": result.get("risk_level", ""),
                "no_retry_status": no_retry["status"],
                "no_retry_final_score": no_retry["final_score"],
                "no_retry_predicted_label": no_retry["predicted_label"],
                "total_ms": total_ms,
                "started_at_utc": datetime.now(timezone.utc).isoformat(),
                "error": "",
            }
            new_rows.append(row)
            (raw_dir / f"{source['sample_id']}.json").write_text(
                json.dumps(
                    {
                        "summary": row,
                        "initial_llm_result": captured["initial"],
                        "focused_retry_result": captured["retry"],
                        "full_result": result,
                        "isolation": "读取正式MySQL/Chroma；关闭联网；保存函数替换为内存对象；生产数据零写入",
                    },
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                ),
                encoding="utf-8",
            )

    merged = {row["sample_id"]: row for row in existing}
    merged.update({row["sample_id"]: row for row in new_rows})
    summary = [merged[sid] for sid in sorted(merged)]
    successful = [row for row in summary if _truthy(row.get("success"))]
    _write_csv(summary_path, summary)
    if successful:
        _retry_ablation_outputs(successful, output_dir)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-web", action="store_true")
    parser.add_argument("--append-web", action="store_true")
    parser.add_argument("--run-retry-ablation", action="store_true")
    parser.add_argument("--append-retry", action="store_true")
    parser.add_argument(
        "--web-sample-ids",
        default="NEWS-EVAL-001,NEWS-EVAL-006,NEWS-EVAL-012",
    )
    parser.add_argument(
        "--retry-sample-ids",
        default="NEWS-EVAL-001,NEWS-EVAL-006,NEWS-EVAL-011,NEWS-EVAL-016",
    )
    args = parser.parse_args()
    project_root = args.project_root.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    predictions, metrics = run_ablation(project_root, output_dir)
    print(f"ablation_predictions={len(predictions)} metrics={len(metrics)}")
    sensitivity = run_parameter_sensitivity(project_root, output_dir, predictions)
    print(f"sensitivity_rows={len(sensitivity)}")
    existing_web_summary = output_dir / "web_low_coverage_summary.csv"
    if existing_web_summary.exists() and not args.run_web:
        existing_rows = _read_csv(existing_web_summary)
        _write_csv(
            output_dir / "performance_stage_summary.csv",
            summarize_stage_timings(existing_rows),
        )
        web_metrics, web_paired = summarize_web_pair_results(existing_rows)
        _write_csv(output_dir / "web_low_coverage_metrics.csv", web_metrics)
        _write_csv(output_dir / "web_low_coverage_paired_statistics.csv", [web_paired])
    if args.run_web:
        rows = run_low_coverage_web_experiment(
            project_root,
            output_dir,
            [item.strip() for item in args.web_sample_ids.split(",") if item.strip()],
            append_existing=args.append_web,
        )
        print(f"web_runs={len(rows)}")
    if args.run_retry_ablation:
        retry_rows = run_retry_ablation_experiment(
            project_root,
            output_dir,
            [
                item.strip()
                for item in args.retry_sample_ids.split(",")
                if item.strip()
            ],
            append_existing=args.append_retry,
        )
        print(f"retry_ablation_runs={len(retry_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
