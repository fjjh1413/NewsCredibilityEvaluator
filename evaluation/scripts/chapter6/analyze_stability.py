from __future__ import annotations

import argparse
import csv
import itertools
import math
import statistics
from pathlib import Path
from typing import Any


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _candidate_set(value: Any) -> set[str]:
    return {item.strip() for item in str(value or "").split(",") if item.strip()}


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    return len(left & right) / len(left | right)


def summarize_stability(
    runs: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, float | int], list[dict[str, Any]]]:
    """Summarize repeated runs over their exact shared sample intersection."""
    if len(runs) < 3:
        raise ValueError("稳定性分析至少需要三次运行")

    indexed = {
        run_name: {str(row.get("sample_id")): row for row in rows if row.get("sample_id")}
        for run_name, rows in runs.items()
    }
    shared_ids = sorted(set.intersection(*(set(rows) for rows in indexed.values())))
    if not shared_ids:
        raise ValueError("三次运行没有共同样本")

    per_sample: list[dict[str, Any]] = []
    all_latencies: list[float] = []
    score_stddevs: list[float] = []
    score_ranges: list[float] = []
    candidate_jaccards: list[float] = []

    for sample_id in shared_ids:
        rows = [indexed[run_name][sample_id] for run_name in runs]
        labels = [str(row.get("predicted_label", "")) for row in rows]
        scores = [number for row in rows if (number := _number(row.get("final_score"))) is not None]
        latencies = [number for row in rows if (number := _number(row.get("total_latency_ms"))) is not None]
        candidate_sets = [_candidate_set(row.get("retrieved_knowledge_ids")) for row in rows]
        pair_jaccards = [_jaccard(left, right) for left, right in itertools.combinations(candidate_sets, 2)]

        score_stddev = statistics.pstdev(scores) if len(scores) > 1 else 0.0
        score_range = max(scores) - min(scores) if scores else 0.0
        mean_jaccard = statistics.fmean(pair_jaccards) if pair_jaccards else 1.0
        all_latencies.extend(latencies)
        score_stddevs.append(score_stddev)
        score_ranges.append(score_range)
        candidate_jaccards.append(mean_jaccard)
        per_sample.append(
            {
                "sample_id": sample_id,
                "prediction_all_same": len(set(labels)) == 1,
                "predicted_labels": " | ".join(labels),
                "score_mean": round(statistics.fmean(scores), 6) if scores else "",
                "score_stddev": round(score_stddev, 6),
                "score_range": round(score_range, 6),
                "candidate_pairwise_jaccard": round(mean_jaccard, 6),
                "latency_mean_ms": round(statistics.fmean(latencies), 6) if latencies else "",
            }
        )

    summary: dict[str, float | int] = {
        "repeat_count": len(runs),
        "shared_sample_count": len(shared_ids),
        "prediction_all_same_rate": round(
            sum(bool(row["prediction_all_same"]) for row in per_sample) / len(per_sample), 6
        ),
        "mean_final_score_stddev": round(statistics.fmean(score_stddevs), 6),
        "max_final_score_range": round(max(score_ranges), 6),
        "mean_candidate_pairwise_jaccard": round(statistics.fmean(candidate_jaccards), 6),
        "latency_avg_ms": round(statistics.fmean(all_latencies), 6),
        "latency_p50_ms": round(_percentile(all_latencies, 0.50), 6),
        "latency_p95_ms": round(_percentile(all_latencies, 0.95), 6),
        "latency_stddev_ms": round(statistics.pstdev(all_latencies), 6),
    }
    return summary, per_sample


def write_stability_outputs(
    runs: dict[str, list[dict[str, Any]]], output_dir: Path
) -> tuple[Path, Path]:
    summary, per_sample = summarize_stability(runs)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "stability_metrics.csv"
    notes = {
        "repeat_count": "原运行、完整复现和第三次子集运行",
        "shared_sample_count": "仅统计三次运行共同样本",
        "prediction_all_same_rate": "同一样本三次预测标签完全一致的比例",
        "mean_final_score_stddev": "逐样本三次最终分总体标准差的均值",
        "max_final_score_range": "逐样本最大分差中的最大值",
        "mean_candidate_pairwise_jaccard": "每样本三对候选知识ID集合Jaccard的均值",
        "latency_avg_ms": "共同样本全部重复观测",
        "latency_p50_ms": "线性插值百分位数",
        "latency_p95_ms": "线性插值百分位数",
        "latency_stddev_ms": "总体标准差",
    }
    with summary_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["metric", "value", "note"])
        writer.writeheader()
        for metric, value in summary.items():
            writer.writerow({"metric": metric, "value": value, "note": notes[metric]})

    per_sample_path = output_dir / "stability_per_sample.csv"
    with per_sample_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(per_sample[0]))
        writer.writeheader()
        writer.writerows(per_sample)
    return summary_path, per_sample_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--original-dir", type=Path, required=True)
    parser.add_argument("--reproduction-dir", type=Path, required=True)
    parser.add_argument("--third-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    runs = {
        "original": _read_csv(args.original_dir / "per_case_results.csv"),
        "reproduction": _read_csv(args.reproduction_dir / "per_case_results.csv"),
        "third": _read_csv(args.third_dir / "per_case_results.csv"),
    }
    summary_path, per_sample_path = write_stability_outputs(runs, args.output_dir)
    print(f"summary={summary_path}")
    print(f"per_sample={per_sample_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
