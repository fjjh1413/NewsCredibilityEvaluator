from __future__ import annotations

import math

from evaluation.scripts.chapter6.run_revision_experiments import (
    analyze_evidence_quality_weights,
    analyze_risk_threshold_shifts,
    analyze_web_trigger_thresholds,
    classify_score,
    derive_no_focused_retry_outcome,
    merge_web_summary_rows,
    paired_bootstrap_comparison,
    recompute_ablation_score,
    summarize_web_pair_results,
    summarize_stage_timings,
)


def test_analyze_web_trigger_thresholds_counts_strictly_lower_top1_scores() -> None:
    rows = [
        {"sample_id": "A", "top_similarity": "0.45"},
        {"sample_id": "B", "top_similarity": "0.70"},
        {"sample_id": "C", "top_similarity": "0.90"},
    ]

    result = analyze_web_trigger_thresholds(rows, [0.45, 0.75, 0.95])

    assert [row["trigger_count"] for row in result] == [0, 2, 3]
    assert result[1]["trigger_rate"] == 0.6667


def test_analyze_evidence_quality_weights_preserves_llm_rule_ratio() -> None:
    rows = [
        {
            "sample_id": "A",
            "gold_label": "存疑信息",
            "llm_score": 50.0,
            "evidence_quality_score": 100.0,
            "rule_score": 50.0,
            "has_effective_evidence": True,
            "contract_status": "ok",
        }
    ]

    predictions, metrics = analyze_evidence_quality_weights(rows, [0.0, 0.3])

    assert predictions[0]["final_score"] == 50.0
    assert predictions[1]["final_score"] == 65.0
    assert metrics[0]["mean_final_score"] == 50.0
    assert metrics[1]["mean_final_score"] == 65.0


def test_analyze_risk_threshold_shifts_reclassifies_with_shifted_boundaries() -> None:
    rows = [
        {"sample_id": "A", "gold_label": "可信新闻", "final_score": 79.0},
        {"sample_id": "B", "gold_label": "疑似谣言", "final_score": 39.0},
    ]

    predictions, metrics, proximity = analyze_risk_threshold_shifts(rows, [-5, 0, 5])

    shifted_down = [row for row in predictions if row["threshold_shift"] == -5]
    assert shifted_down[0]["predicted_label"] == "可信新闻"
    assert next(row for row in metrics if row["threshold_shift"] == 0)["accuracy"] == 0.0
    assert next(row for row in proximity if row["margin"] == 2)["sample_count"] == 2


def test_recompute_no_evidence_quality_renormalizes_remaining_weights() -> None:
    score = recompute_ablation_score(
        variant="No-Evidence-Quality",
        llm_score=70,
        evidence_quality_score=80,
        rule_score=90,
        has_effective_evidence=True,
        is_llm_degraded=False,
    )

    assert score == 75.71


def test_recompute_no_rule_renormalizes_remaining_weights() -> None:
    score = recompute_ablation_score(
        variant="No-Rule",
        llm_score=70,
        evidence_quality_score=80,
        rule_score=90,
        has_effective_evidence=True,
        is_llm_degraded=False,
    )

    assert score == 73.75


def test_no_rule_is_unavailable_when_only_rule_branch_exists() -> None:
    score = recompute_ablation_score(
        variant="No-Rule",
        llm_score=0,
        evidence_quality_score=0,
        rule_score=90,
        has_effective_evidence=False,
        is_llm_degraded=True,
    )

    assert math.isnan(score)


def test_classify_score_uses_production_thresholds() -> None:
    assert classify_score(80) == "可信新闻"
    assert classify_score(60) == "存疑信息"
    assert classify_score(40) == "疑似谣言"
    assert classify_score(39.99) == "高风险谣言"


def test_summarize_stage_timings_reports_distribution_per_policy_and_stage() -> None:
    rows = [
        {"policy": "Local+Web", "stage_timings_ms": '{"search_evidence": 10, "analyze_news_credibility": 100}'},
        {"policy": "Local+Web", "stage_timings_ms": '{"search_evidence": 30, "analyze_news_credibility": 200}'},
    ]

    summary = summarize_stage_timings(rows)

    search = next(row for row in summary if row["stage"] == "search_evidence")
    assert search["sample_count"] == 2
    assert search["mean_ms"] == 20.0
    assert search["p50_ms"] == 20.0
    assert search["min_ms"] == 10.0
    assert search["max_ms"] == 30.0


def test_paired_bootstrap_identical_predictions_has_zero_delta_interval() -> None:
    baseline = [
        {"sample_id": "A", "gold_label": "可信新闻", "predicted_label": "可信新闻"},
        {"sample_id": "B", "gold_label": "高风险谣言", "predicted_label": "疑似谣言"},
    ]
    variant = [dict(row) for row in baseline]

    result = paired_bootstrap_comparison(
        baseline,
        variant,
        baseline_name="Full",
        variant_name="Use-All-Candidates",
        iterations=200,
        seed=7,
    )

    assert result["accuracy_delta"] == 0.0
    assert result["accuracy_ci_low"] == 0.0
    assert result["accuracy_ci_high"] == 0.0
    assert result["macro_f1_delta"] == 0.0
    assert result["discordant_pairs"] == 0


def test_merge_web_summary_rows_replaces_same_sample_policy_without_duplicates() -> None:
    existing = [
        {"sample_id": "A", "policy": "Local-only", "final_score": "80"},
        {"sample_id": "A", "policy": "Local+Web", "final_score": "70"},
    ]
    new = [
        {"sample_id": "A", "policy": "Local+Web", "final_score": "75"},
        {"sample_id": "B", "policy": "Local-only", "final_score": "60"},
    ]

    merged = merge_web_summary_rows(existing, new)

    assert len(merged) == 3
    assert next(row for row in merged if row["sample_id"] == "A" and row["policy"] == "Local+Web")["final_score"] == "75"


def test_summarize_web_pair_results_counts_triggers_candidates_and_label_changes() -> None:
    rows = [
        {"sample_id": "A", "gold_label": "可信新闻", "policy": "Local-only", "predicted_label": "可信新闻", "web_triggered": "False", "web_candidate_count": "0", "web_effective_count": "0", "arbitration_status": "no_evidence", "total_ms": "10"},
        {"sample_id": "A", "gold_label": "可信新闻", "policy": "Local+Web", "predicted_label": "存疑信息", "web_triggered": "True", "web_candidate_count": "5", "web_effective_count": "1", "arbitration_status": "ok", "total_ms": "20"},
    ]
    for sample_id, label in [("B", "存疑信息"), ("C", "疑似谣言"), ("D", "高风险谣言")]:
        rows.extend(
            [
                {"sample_id": sample_id, "gold_label": label, "policy": "Local-only", "predicted_label": label, "web_triggered": "False", "web_candidate_count": "0", "web_effective_count": "0", "arbitration_status": "no_evidence", "total_ms": "10"},
                {"sample_id": sample_id, "gold_label": label, "policy": "Local+Web", "predicted_label": label, "web_triggered": "True", "web_candidate_count": "5", "web_effective_count": "1", "arbitration_status": "ok", "total_ms": "20"},
            ]
        )

    metrics, paired = summarize_web_pair_results(rows, bootstrap_iterations=100)

    web = next(row for row in metrics if row["policy"] == "Local+Web")
    assert web["triggered_count"] == 4
    assert web["web_candidate_count"] == 20
    assert web["web_effective_count"] == 4
    assert paired["label_change_count"] == 1


def test_derive_no_focused_retry_uses_no_evidence_branch_after_invalid_contract() -> None:
    outcome = derive_no_focused_retry_outcome(
        initial_contract_valid=False,
        is_llm_degraded=False,
        llm_score=40,
        rule_score_without_evidence=100,
        full_score=70,
    )

    assert outcome["final_score"] == 64.0
    assert outcome["predicted_label"] == "存疑信息"
    assert outcome["status"] == "initial_contract_rejected"


def test_derive_no_focused_retry_matches_full_when_initial_contract_is_valid() -> None:
    outcome = derive_no_focused_retry_outcome(
        initial_contract_valid=True,
        is_llm_degraded=False,
        llm_score=40,
        rule_score_without_evidence=100,
        full_score=52,
    )

    assert outcome["final_score"] == 52.0
    assert outcome["status"] == "initial_contract_ok"
