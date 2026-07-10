from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from pathlib import Path
from typing import Any


def _json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _jaccard(left: str, right: str) -> float:
    a = {item for item in str(left).split(",") if item}
    b = {item for item in str(right).split(",") if item}
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b) if a | b else 1.0


def _row(metric: str, original: Any, reproduction: Any, note: str = "") -> dict[str, Any]:
    left = _number(original)
    right = _number(reproduction)
    difference = round(right - left, 6) if left is not None and right is not None else note
    return {"metric": metric, "original": original, "reproduction": reproduction, "difference_or_note": difference}


def finalize(project_root: Path, run_dir: Path) -> list[dict[str, Any]]:
    original_dir = project_root / "evaluation" / "output"
    reproduction_dir = run_dir / "results" / "reproduction_raw"
    required = [reproduction_dir / "metrics.json", reproduction_dir / "per_case_results.csv", reproduction_dir / "run_metadata.json"]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise RuntimeError(f"复现尚未完成，缺少：{missing}")

    original_metrics = _json(original_dir / "metrics.json")
    reproduction_metrics = _json(reproduction_dir / "metrics.json")
    original_meta = _json(original_dir / "run_metadata.json")
    reproduction_meta = _json(reproduction_dir / "run_metadata.json")
    original_cases = {row["sample_id"]: row for row in _csv(original_dir / "per_case_results.csv")}
    reproduction_cases = {row["sample_id"]: row for row in _csv(reproduction_dir / "per_case_results.csv")}
    shared = sorted(set(original_cases) & set(reproduction_cases))

    label_matches = sum(original_cases[sid]["predicted_label"] == reproduction_cases[sid]["predicted_label"] for sid in shared)
    score_differences = []
    pair_standard_deviations = []
    retrieval_jaccards = []
    for sid in shared:
        old_score = _number(original_cases[sid].get("final_score"))
        new_score = _number(reproduction_cases[sid].get("final_score"))
        if old_score is not None and new_score is not None:
            score_differences.append(new_score - old_score)
            pair_standard_deviations.append(statistics.pstdev([old_score, new_score]))
        retrieval_jaccards.append(_jaccard(original_cases[sid].get("retrieved_knowledge_ids", ""), reproduction_cases[sid].get("retrieved_knowledge_ids", "")))

    old_class = original_metrics["classification"]
    new_class = reproduction_metrics["classification"]
    old_latency = original_metrics["latency"]["total_latency_ms"]
    new_latency = reproduction_metrics["latency"]["total_latency_ms"]
    rows = [
        _row("dataset_sha256", original_meta.get("dataset_file_hash"), reproduction_meta.get("dataset_file_hash"), "一致" if original_meta.get("dataset_file_hash") == reproduction_meta.get("dataset_file_hash") else "不一致"),
        _row("success_count", original_metrics["sample_counts"]["success_count"], reproduction_metrics["sample_counts"]["success_count"]),
        _row("failure_count", original_metrics["sample_counts"]["failure_count"], reproduction_metrics["sample_counts"]["failure_count"]),
        _row("accuracy", old_class["accuracy"], new_class["accuracy"]),
        _row("macro_precision", old_class["macro_precision"], new_class["macro_precision"]),
        _row("macro_recall", old_class["macro_recall"], new_class["macro_recall"]),
        _row("macro_f1", old_class["macro_f1"], new_class["macro_f1"]),
        _row("mean_latency_ms", old_latency["avg"], new_latency["avg"]),
        _row("p50_latency_ms", old_latency["p50"], new_latency["p50"]),
        _row("p95_latency_ms", old_latency["p95"], new_latency["p95"]),
        _row("web_trigger_count", original_metrics["web_search"]["web_search_triggered_count"], reproduction_metrics["web_search"]["web_search_triggered_count"]),
        _row("at_least_one_valid_evidence_rate", original_metrics["evidence_completeness"]["at_least_one_valid_evidence_rate"], reproduction_metrics["evidence_completeness"]["at_least_one_valid_evidence_rate"]),
        _row("risk_label_consistency_rate", 1.0, round(label_matches / len(shared), 6) if shared else 0.0, f"{label_matches}/{len(shared)}逐样本预测一致"),
        _row("mean_final_score_difference", 0.0, round(statistics.fmean(score_differences), 6) if score_differences else 0.0, "复现减原运行"),
        _row("mean_pair_score_stddev", 0.0, round(statistics.fmean(pair_standard_deviations), 6) if pair_standard_deviations else 0.0, "每样本两次分数总体标准差均值"),
        _row("retrieved_candidate_jaccard", 1.0, round(statistics.fmean(retrieval_jaccards), 6) if retrieval_jaccards else 0.0, "候选知识ID集合；不是有效证据集合"),
    ]
    output = run_dir / "results" / "existing_experiment_reproduction.csv"
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["metric", "original", "reproduction", "difference_or_note"])
        writer.writeheader()
        writer.writerows(rows)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    rows = finalize(args.project_root.resolve(), args.run_dir.resolve())
    print(f"reproduction_metrics={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
