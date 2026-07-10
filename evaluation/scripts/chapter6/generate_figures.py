from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _configure_fonts() -> None:
    candidates = [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simsun.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
    ]
    selected = next((path for path in candidates if path.exists()), None)
    if selected:
        font_manager.fontManager.addfont(str(selected))
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=str(selected)).get_name()
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 150
    plt.rcParams["savefig.dpi"] = 300


def _save(fig: plt.Figure, path: Path) -> None:
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def dataset_distribution(results: Path, figures: Path) -> None:
    rows = [row for row in _rows(results / "dataset_summary.csv") if row["role"] == "标签分布"]
    labels = [row["group"] for row in rows]
    values = [int(row["count"]) for row in rows]
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    bars = ax.bar(labels, values, color=["#222222", "#555555", "#888888", "#bbbbbb"], edgecolor="black")
    ax.set_ylabel("样本数")
    ax.set_title("评测数据集类别分布")
    ax.set_ylim(0, max(values) * 1.25)
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.4, str(value), ha="center", va="bottom")
    _save(fig, figures / "dataset_class_distribution.png")


def confusion_matrix(results: Path, figures: Path) -> None:
    rows = _rows(results / "confusion_matrix.csv")
    labels = [row["gold_label"] for row in rows]
    matrix = np.array([[int(row[label]) for label in labels] for row in rows])
    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    image = ax.imshow(matrix, cmap="Greys", vmin=0, vmax=max(1, matrix.max()))
    ax.set_xticks(range(len(labels)), labels=labels, rotation=25, ha="right")
    ax.set_yticks(range(len(labels)), labels=labels)
    ax.set_xlabel("预测类别")
    ax.set_ylabel("真实类别")
    ax.set_title("四分类混淆矩阵")
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            color = "white" if matrix[i, j] > matrix.max() / 2 else "black"
            ax.text(j, i, str(matrix[i, j]), ha="center", va="center", color=color)
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    _save(fig, figures / "classification_confusion_matrix.png")


def retrieval_curve(results: Path, figures: Path) -> None:
    rows = _rows(results / "retrieval_metrics.csv")
    k_values = [int(row["k"]) for row in rows]
    recall = [float(row["recall_at_k"]) for row in rows]
    fig, ax = plt.subplots(figsize=(6.8, 4.3))
    ax.plot(k_values, recall, color="black", marker="o", linewidth=1.8)
    ax.set_xticks(k_values)
    ax.set_ylim(0, 1.08)
    ax.set_xlabel("Top-K")
    ax.set_ylabel("Recall@K")
    ax.set_title("本地检索Recall@K（强对应评测知识条件）")
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    for k, value in zip(k_values, recall):
        ax.text(k, value + 0.025, f"{value:.2f}", ha="center")
    _save(fig, figures / "retrieval_recall_at_k.png")


def per_class_f1(results: Path, figures: Path) -> None:
    rows = [row for row in _rows(results / "classification_metrics.csv") if row["scope"] == "class"]
    labels = [row["label"] for row in rows]
    values = [float(row["f1"]) for row in rows]
    fig, ax = plt.subplots(figsize=(7.0, 4.4))
    bars = ax.bar(labels, values, color="#777777", edgecolor="black")
    ax.set_ylim(0, 1.0)
    ax.set_ylabel("F1")
    ax.set_title("各风险类别F1")
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.025, f"{value:.3f}", ha="center")
    _save(fig, figures / "classification_per_class_f1.png")


def arbitration_outcomes(results: Path, figures: Path) -> None:
    row = _rows(results / "arbitration_metrics.csv")[0]
    labels = ["契约通过", "重试耗尽", "模型服务失败"]
    values = [int(row["contract_ok"]), int(row["retry_exhausted"]), int(row["provider_error"])]
    fig, ax = plt.subplots(figsize=(6.8, 4.4))
    bars = ax.bar(labels, values, color=["#333333", "#888888", "#bbbbbb"], edgecolor="black")
    ax.set_ylabel("样本数")
    ax.set_title("既有运行证据仲裁状态")
    ax.set_ylim(0, max(values) * 1.2)
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.8, str(value), ha="center")
    _save(fig, figures / "arbitration_status_distribution.png")


def response_time(results: Path, figures: Path) -> None:
    rows = _rows(results / "performance_results.csv")
    label_map = {
        "本地检索+模型（联网允许但实际未触发）": "端到端本地+模型",
        "历史记录分页（MySQL只读）": "历史分页",
        "管理员统计概览（MySQL只读）": "统计概览",
        "PDF生成（既有检测记录内容）": "PDF生成",
        "URL提取（既有评测样本URL）": "URL提取",
    }
    labels = [label_map.get(row["path"], row["path"]) for row in rows]
    values = [max(float(row["mean_ms"]), 0.01) for row in rows]
    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    bars = ax.barh(labels, values, color="#777777", edgecolor="black")
    ax.set_xscale("log")
    ax.set_xlabel("平均响应时间/ms（对数坐标）")
    ax.set_title("不同运行路径平均响应时间")
    for bar, value in zip(bars, values):
        ax.text(value * 1.08, bar.get_y() + bar.get_height() / 2, f"{value:.2f}", va="center")
    _save(fig, figures / "response_time_summary.png")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    results = run_dir / "results"
    figures = run_dir / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    _configure_fonts()
    dataset_distribution(results, figures)
    confusion_matrix(results, figures)
    retrieval_curve(results, figures)
    per_class_f1(results, figures)
    arbitration_outcomes(results, figures)
    response_time(results, figures)
    print(f"figures=6; output={figures}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
