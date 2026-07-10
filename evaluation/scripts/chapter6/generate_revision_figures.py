from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def _configure() -> None:
    plt.rcParams.update(
        {
            "font.sans-serif": ["Microsoft YaHei", "SimHei", "Arial Unicode MS"],
            "axes.unicode_minus": False,
            "figure.dpi": 120,
            "savefig.dpi": 320,
        }
    )


def _save(fig: plt.Figure, path: Path) -> None:
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def ablation_figure(results: Path, figures: Path) -> None:
    frame = pd.read_csv(results / "ablation_metrics.csv")
    frame = frame[
        frame["variant"].isin(
            ["Full", "No-Evidence-Quality", "No-Rule", "Use-All-Candidates"]
        )
    ]
    metrics = ["accuracy", "macro_f1", "weighted_f1", "high_risk_recall"]
    labels = ["Accuracy", "Macro-F1", "Weighted-F1", "高风险Recall"]
    x = np.arange(len(frame))
    width = 0.19
    fig, ax = plt.subplots(figsize=(11.5, 5.4))
    for index, (metric, label) in enumerate(zip(metrics, labels)):
        bars = ax.bar(x + (index - 1.5) * width, frame[metric], width, label=label)
        ax.bar_label(bars, fmt="%.3f", fontsize=8, padding=2)
    ax.set_xticks(x, frame["variant"])
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("指标值")
    ax.set_title("共同子集上的评分与仲裁消融（n=68）")
    ax.legend(ncol=2, loc="upper center")
    ax.grid(axis="y", alpha=0.25)
    _save(fig, figures / "ablation_metrics_comparison.png")


def web_figure(results: Path, figures: Path) -> None:
    frame = pd.read_csv(results / "web_low_coverage_summary.csv")
    pivot = frame.pivot(index="sample_id", columns="policy", values="final_score")
    x = np.arange(len(pivot))
    width = 0.34
    fig, ax = plt.subplots(figsize=(12.0, 5.4))
    bars1 = ax.bar(x - width / 2, pivot["Local-only"], width, label="Local-only")
    bars2 = ax.bar(x + width / 2, pivot["Local+Web"], width, label="Local+Web")
    ax.bar_label(bars1, fmt="%.1f", fontsize=9)
    ax.bar_label(bars2, fmt="%.1f", fontsize=9)
    ax.set_xticks(x, pivot.index)
    ax.tick_params(axis="x", rotation=35)
    ax.set_ylim(0, 110)
    ax.set_ylabel("最终分")
    ax.set_title("隔离低覆盖条件下Local-only与Local+Web配对结果")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)
    _save(fig, figures / "local_web_comparison.png")


def paired_ci_figure(results: Path, figures: Path) -> None:
    frame = pd.read_csv(results / "ablation_paired_statistics.csv")
    y = np.arange(len(frame))
    fig, ax = plt.subplots(figsize=(9.8, 5.0))
    for offset, metric, low, high, label, color in [
        (0.13, "accuracy_delta", "accuracy_ci_low", "accuracy_ci_high", "Accuracy差值", "#2B6CB0"),
        (-0.13, "macro_f1_delta", "macro_f1_ci_low", "macro_f1_ci_high", "Macro-F1差值", "#D97706"),
    ]:
        values = frame[metric].to_numpy()
        errors = np.vstack([values - frame[low].to_numpy(), frame[high].to_numpy() - values])
        ax.errorbar(values, y + offset, xerr=errors, fmt="o", capsize=4, label=label, color=color)
    ax.axvline(0, color="#444444", linewidth=1, linestyle="--")
    ax.set_yticks(y, frame["variant"])
    ax.set_xlabel("相对Full的指标差值（95%配对Bootstrap区间）")
    ax.set_title("消融方案配对差值与不确定性")
    ax.legend()
    ax.grid(axis="x", alpha=0.25)
    _save(fig, figures / "ablation_paired_confidence_intervals.png")


def performance_figure(results: Path, figures: Path) -> None:
    frame = pd.read_csv(results / "performance_stage_summary.csv")
    keep = frame[frame["stage"].isin(["search_evidence", "analyze_news_credibility", "calculate_rule_score"])]
    labels = [f"{row.policy}\n{row.stage}" for row in keep.itertuples()]
    y = np.arange(len(keep))
    fig, ax = plt.subplots(figsize=(9.2, 5.2))
    ax.barh(y + 0.17, keep["p50_ms"], 0.34, label="P50")
    ax.barh(y - 0.17, keep["p95_ms"], 0.34, label="P95")
    ax.set_yticks(y, labels)
    ax.set_xlabel("耗时（ms，对数坐标）")
    ax.set_xscale("log")
    ax.set_title("隔离低覆盖实验的分阶段耗时")
    ax.legend()
    ax.grid(axis="x", alpha=0.25)
    _save(fig, figures / "stage_latency_p50_p95.png")


def sensitivity_figure(results: Path, figures: Path) -> None:
    web = pd.read_csv(results / "web_trigger_threshold_sensitivity.csv")
    quality = pd.read_csv(results / "evidence_quality_weight_sensitivity_metrics.csv")
    risk = pd.read_csv(results / "risk_threshold_sensitivity_metrics.csv")
    fig, axes = plt.subplots(1, 3, figsize=(15.2, 4.7))

    axes[0].plot(web["top1_threshold"], web["trigger_rate"], marker="o", color="#2B6CB0")
    axes[0].axvline(0.45, color="#C73E1D", linestyle="--", linewidth=1, label="生产阈值0.45")
    axes[0].set_title("Top-1阈值与反事实触发率")
    axes[0].set_xlabel("Top-1阈值")
    axes[0].set_ylabel("触发率")
    axes[0].set_ylim(0, 1.0)
    axes[0].legend(fontsize=8)

    axes[1].plot(quality["evidence_quality_weight"], quality["accuracy"], marker="o", label="Accuracy")
    axes[1].plot(quality["evidence_quality_weight"], quality["macro_f1"], marker="s", label="Macro-F1")
    axes[1].axvline(0.30, color="#C73E1D", linestyle="--", linewidth=1, label="生产权重0.30")
    axes[1].set_title("证据质量权重敏感性（n=68）")
    axes[1].set_xlabel("证据质量权重")
    axes[1].set_ylim(0, 0.7)
    axes[1].legend(fontsize=8)

    axes[2].plot(risk["threshold_shift"], risk["accuracy"], marker="o", label="Accuracy")
    axes[2].plot(risk["threshold_shift"], risk["macro_f1"], marker="s", label="Macro-F1")
    axes[2].axvline(0, color="#C73E1D", linestyle="--", linewidth=1, label="生产分界点")
    axes[2].set_title("风险分界点同向平移（n=80）")
    axes[2].set_xlabel("分界点平移分值")
    axes[2].set_ylim(0, 0.5)
    axes[2].legend(fontsize=8)

    for ax in axes:
        ax.grid(alpha=0.25)
    _save(fig, figures / "parameter_sensitivity_overview.png")


def rq_figure(results: Path, figures: Path) -> None:
    frame = pd.read_csv(results / "rq_status.csv")
    status_value = {"已回答": 2, "部分回答": 1, "未回答": 0}
    colors = {"已回答": "#2E8B57", "部分回答": "#F0A202", "未回答": "#C73E1D"}
    values = [status_value[item] for item in frame["status"]]
    fig, ax = plt.subplots(figsize=(9.0, 4.6))
    bars = ax.bar(frame["rq_id"], values, color=[colors[item] for item in frame["status"]])
    ax.set_ylim(0, 2.35)
    ax.set_yticks([0, 1, 2], ["未回答", "部分回答", "已回答"])
    ax.set_title("RQ1—RQ8回答状态")
    ax.grid(axis="y", alpha=0.25)
    for bar, status in zip(bars, frame["status"]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.07, status, ha="center", fontsize=9)
    _save(fig, figures / "rq_status_overview.png")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", type=Path, required=True)
    args = parser.parse_args()
    results = args.results_dir.resolve()
    figures = results / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    _configure()
    ablation_figure(results, figures)
    paired_ci_figure(results, figures)
    web_figure(results, figures)
    performance_figure(results, figures)
    sensitivity_figure(results, figures)
    rq_figure(results, figures)
    manifest = {path.name: path.stat().st_size for path in sorted(figures.glob("*.png"))}
    (figures / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"figures={len(manifest)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
