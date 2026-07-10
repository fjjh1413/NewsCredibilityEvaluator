"""Report generation for news credibility evaluation.

Generates:
- ``metrics.json`` — all quantitative metrics
- ``run_metadata.json`` — environment, config, and run info
- ``evaluation_report.md`` — human-readable summary
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _json_default(obj: Any) -> Any:
    """Handle non-serializable types in JSON output."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, set):
        return sorted(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _write_json(path: Path, data: dict[str, Any]) -> None:
    """Write JSON with consistent formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=_json_default)


def compute_file_hash(file_path: str | Path) -> str:
    """Compute SHA-256 hash of a file."""
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha.update(chunk)
    return sha.hexdigest()


def get_system_info() -> dict[str, str]:
    """Gather OS and Python version info."""
    info: dict[str, str] = {
        "os": platform.system(),
        "os_release": platform.release(),
        "os_version": platform.version(),
        "python_version": sys.version,
    }

    # CPU info
    try:
        info["cpu_count_logical"] = str(os.cpu_count() or "unknown")
    except Exception:
        info["cpu_count_logical"] = "unknown"

    try:
        import psutil
        mem = psutil.virtual_memory()
        info["memory_total_gb"] = f"{mem.total / (1024**3):.1f}"
    except ImportError:
        info["memory_total_gb"] = "psutil not installed"

    return info


def generate_run_metadata(
    output_dir: str | Path,
    dataset_path: str | Path,
    run_args: dict[str, Any],
    config_info: dict[str, Any],
) -> dict[str, Any]:
    """Generate and persist run_metadata.json."""
    output_dir = Path(output_dir)
    dataset_path = Path(dataset_path)

    metadata: dict[str, Any] = {
        "commit_hash": run_args.get("commit_hash", "unknown"),
        "run_date": datetime.now(timezone.utc).isoformat(),
        "os": platform.system(),
        "os_release": platform.release(),
        "python_version": sys.version,
        "cpu_count_logical": os.cpu_count(),
        "memory_note": "use psutil for detailed memory info",
        "model_name": config_info.get("model_name", "unknown"),
        "embedding_provider": config_info.get("embedding_provider", "unknown"),
        "embedding_model": config_info.get("embedding_model", "unknown"),
        "top_k_rag": config_info.get("top_k_rag"),
        "rag_top1_threshold": config_info.get("rag_top1_threshold"),
        "rag_top1_moderate": config_info.get("rag_top1_moderate"),
        "rag_min_meaningful": config_info.get("rag_min_meaningful"),
        "web_trigger_rules": {
            "top1_below_trigger": config_info.get("rag_top1_threshold"),
            "moderate_top1_below": config_info.get("rag_top1_moderate"),
            "min_meaningful_results": config_info.get("rag_min_meaningful"),
        },
        "scoring_formula": config_info.get("scoring_formula"),
        "dataset_file_hash": run_args.get("dataset_hash", "not computed"),
        "web_search_enabled_global": run_args.get("allow_web_search", False),
        "sample_limit": run_args.get("sample_limit"),
        "command": run_args.get("command", ""),
    }

    # Add system info from psutil if available
    try:
        import psutil
        mem = psutil.virtual_memory()
        metadata["memory_total_gb"] = round(mem.total / (1024**3), 1)
    except ImportError:
        pass

    _write_json(output_dir / "run_metadata.json", metadata)
    return metadata


def generate_metrics_json(
    output_dir: str | Path,
    metrics: dict[str, Any],
) -> None:
    """Persist metrics.json."""
    _write_json(Path(output_dir) / "metrics.json", metrics)


def generate_evaluation_report_md(
    output_dir: str | Path,
    metrics: dict[str, Any],
    metadata: dict[str, Any] | None = None,
) -> str:
    """Generate evaluation_report.md and return its content."""
    sc = metrics.get("sample_counts", {})
    lat = metrics.get("latency", {})
    ws = metrics.get("web_search", {})
    ret = metrics.get("retrieval", {})
    clf = metrics.get("classification", {})
    ira = metrics.get("inter_rater_agreement", {})
    evc = metrics.get("evidence_completeness", {})
    stab = metrics.get("stability", {})

    lines: list[str] = []
    lines.append("# 新闻可信度评测报告")
    lines.append("")
    if metadata:
        lines.append(f"**运行时间**: {metadata.get('run_date', 'N/A')}")
        lines.append(f"**Commit**: `{metadata.get('commit_hash', 'N/A')}`")
        lines.append(f"**模型**: {metadata.get('model_name', 'N/A')}")
        lines.append("")

    # ── 1. 样本概况 ──
    lines.append("## 1. 样本概况")
    lines.append("")
    lines.append(f"| 指标 | 值 |")
    lines.append(f"|---|---|")
    lines.append(f"| 总样本数 | {sc.get('total_samples', 0)} |")
    lines.append(f"| 排除的 DEMO 样本 | {sc.get('demo_samples_excluded', 0)} |")
    lines.append(f"| 有效样本数 | {sc.get('valid_samples', 0)} |")
    lines.append(f"| 成功数 | {sc.get('success_count', 0)} |")
    lines.append(f"| 失败数 | {sc.get('failure_count', 0)} |")
    lines.append("")

    gold_dist = sc.get("gold_label_distribution", {})
    if gold_dist:
        lines.append("### 真实标签分布")
        lines.append("")
        lines.append(f"| 标签 | 数量 |")
        lines.append(f"|---|---|")
        for label, count in sorted(gold_dist.items()):
            lines.append(f"| {label} | {count} |")
        lines.append("")

    pred_dist = sc.get("predicted_label_distribution", {})
    if pred_dist:
        lines.append("### 预测标签分布")
        lines.append("")
        lines.append(f"| 标签 | 数量 |")
        lines.append(f"|---|---|")
        for label, count in sorted(pred_dist.items()):
            lines.append(f"| {label} | {count} |")
        lines.append("")

    # ── 2. 响应时间 ──
    lines.append("## 2. 响应时间")
    lines.append("")
    lines.append("| 阶段 | 平均(ms) | P50(ms) | P95(ms) | 最大(ms) | 样本数 |")
    lines.append("|---|---|---|---|---|---|")
    for stage_name, stage_stats in lat.items():
        label = stage_name.replace("_latency_ms", "").replace("_", " ").strip()
        lines.append(
            f"| {label} | {stage_stats.get('avg', '-')} | {stage_stats.get('p50', '-')} | "
            f"{stage_stats.get('p95', '-')} | {stage_stats.get('max', '-')} | "
            f"{stage_stats.get('count', 0)} |"
        )
    lines.append("")

    # ── 3. 联网检索触发率 ──
    lines.append("## 3. 联网检索触发率")
    lines.append("")
    lines.append(f"- 允许联网样本数: {ws.get('web_search_allowed_count', 0)}")
    lines.append(f"- 实际触发联网数: {ws.get('web_search_triggered_count', 0)}")
    lines.append(f"- 触发率: {ws.get('web_trigger_rate', 0)}")
    reasons = ws.get("web_trigger_reasons", {})
    if reasons:
        lines.append("")
        lines.append("### 触发原因分布")
        lines.append("")
        lines.append("| 原因 | 次数 |")
        lines.append("|---|---|")
        for reason, count in sorted(reasons.items()):
            lines.append(f"| {reason} | {count} |")
    lines.append("")

    # ── 4. 本地召回效果 ──
    lines.append("## 4. 本地召回效果")
    lines.append("")
    annotated_count = ret.get("annotated_sample_count", 0)
    if annotated_count == 0:
        lines.append(f"⚠️ 没有样本标注了 `relevant_knowledge_ids`，无法计算 Hit@K / Recall@K / MRR。")
        lines.append("")
    else:
        lines.append(f"标注样本数: {annotated_count}")
        lines.append("")
        lines.append("| K | Hit@K | Recall@K |")
        lines.append("|---|---|---|")
        hit = ret.get("hit_at_k", {})
        rec = ret.get("recall_at_k", {})
        for k in sorted(hit.keys()):
            lines.append(f"| {k} | {hit.get(k, '-')} | {rec.get(k, '-')} |")
        mrr = ret.get("mrr")
        if mrr is not None:
            lines.append("")
            lines.append(f"**MRR**: {mrr}")
        lines.append("")

    chunk_annotated_count = ret.get("chunk_annotated_sample_count", 0)
    if chunk_annotated_count:
        lines.append("### Chunk-level Retrieval")
        lines.append("")
        lines.append(f"标注样本数: {chunk_annotated_count}")
        lines.append("")
        lines.append("| K | Chunk Hit@K | Chunk Recall@K |")
        lines.append("|---|---|---|")
        chunk_hit = ret.get("chunk_hit_at_k", {})
        chunk_rec = ret.get("chunk_recall_at_k", {})
        for k in sorted(chunk_hit.keys()):
            lines.append(f"| {k} | {chunk_hit.get(k, '-')} | {chunk_rec.get(k, '-')} |")
        chunk_mrr = ret.get("chunk_mrr")
        if chunk_mrr is not None:
            lines.append("")
            lines.append(f"**Chunk MRR**: {chunk_mrr}")
        lines.append("")
    elif ret.get("chunk_note"):
        lines.append(f"⚠️ {ret['chunk_note']}")
        lines.append("")

    # ── 5. 分类效果 ──
    lines.append("## 5. 分类效果")
    lines.append("")
    labeled_count = clf.get("labeled_sample_count", 0)
    if labeled_count == 0:
        lines.append("⚠️ 没有样本同时具有 `gold_label` 和 `predicted_label`，无法计算分类指标。")
        lines.append("")
    else:
        lines.append(f"有标签样本数: {labeled_count}")
        lines.append("")
        lines.append(f"| 指标 | 值 |")
        lines.append(f"|---|---|")
        lines.append(f"| Accuracy | {clf.get('accuracy', '-')} |")
        lines.append(f"| Macro Precision | {clf.get('macro_precision', '-')} |")
        lines.append(f"| Macro Recall | {clf.get('macro_recall', '-')} |")
        lines.append(f"| Macro F1 | {clf.get('macro_f1', '-')} |")
        lines.append("")

        per_class = clf.get("per_class", {})
        if per_class:
            lines.append("### 各类别指标")
            lines.append("")
            lines.append("| 类别 | TP | FP | FN | Precision | Recall | F1 |")
            lines.append("|---|---|---|---|---|---|---|")
            for label, pc in sorted(per_class.items()):
                lines.append(
                    f"| {label} | {pc.get('tp', 0)} | {pc.get('fp', 0)} | {pc.get('fn', 0)} | "
                    f"{pc.get('precision', '-')} | {pc.get('recall', '-')} | {pc.get('f1', '-')} |"
                )
            lines.append("")

        cm = clf.get("confusion_matrix", {})
        if cm:
            lines.append("### 混淆矩阵 (行=真实, 列=预测)")
            lines.append("")
            labels = sorted(cm.keys())
            header = "| 真实 \\ 预测 | " + " | ".join(labels) + " |"
            lines.append(header)
            sep = "|---|" + "|".join(["---"] * len(labels)) + "|"
            lines.append(sep)
            for g_label in labels:
                row = " | ".join(str(cm[g_label].get(p_label, 0)) for p_label in labels)
                lines.append(f"| {g_label} | {row} |")
            lines.append("")

    # ── 6. 人工评审一致性 ──
    lines.append("## 6. 人工评审一致性")
    lines.append("")
    dual_count = ira.get("dual_reviewed_count", 0)
    lines.append(f"双评审样本数: {dual_count}")
    if ira.get("raw_agreement_rate") is not None:
        lines.append(f"- 原始一致率: {ira['raw_agreement_rate']}")
    if ira.get("cohens_kappa") is not None:
        lines.append(f"- Cohen's Kappa: {ira['cohens_kappa']}")
    if ira.get("note"):
        lines.append(f"⚠️ {ira['note']}")
    lines.append("")

    # ── 7. 证据引用完整率 ──
    lines.append("## 7. 证据引用完整率")
    lines.append("")
    if evc.get("note"):
        lines.append(f"⚠️ {evc['note']}")
    else:
        lines.append(f"| 指标 | 数量 | 比例 |")
        lines.append(f"|---|---|---|")
        lines.append(f"| 成功样本总数 | {evc.get('total_successful', 0)} | — |")
        lines.append(f"| 至少含一条证据 | {evc.get('at_least_one_evidence_count', 0)} | {evc.get('at_least_one_evidence_rate', 0)} |")
        lines.append(f"| 至少含一条有效证据 | {evc.get('at_least_one_valid_evidence_count', 0)} | {evc.get('at_least_one_valid_evidence_rate', 0)} |")
        lines.append(f"| 证据关键字段完整 | {evc.get('citation_fields_complete_count', 0)} | {evc.get('citation_fields_complete_rate', 0)} |")
        lines.append(f"| 证据含有效URL | {evc.get('evidence_has_valid_url_count', 0)} | {evc.get('evidence_has_valid_url_rate', 0)} |")
        lines.append(f"| 证据不足时正确提示 | {evc.get('evidence_insufficient_with_hint_count', 0)} | — |")
        lines.append(f"| 有结论但无证据 | {evc.get('conclusion_without_evidence_count', 0)} | — |")
    lines.append("")

    # ── 8. 稳定性 ──
    lines.append("## 8. 稳定性")
    lines.append("")
    if stab.get("note"):
        lines.append(f"⚠️ {stab['note']}")
    else:
        lines.append(f"| 指标 | 值 |")
        lines.append(f"|---|---|")
        lines.append(f"| 整体成功率 | {stab.get('overall_success_rate', 0)} |")
        lines.append(f"| 超时率 | {stab.get('timeout_rate', 0)} |")
        lines.append(f"| LLM 结构化解析失败率 | — |")
        lines.append(f"| 降级解析使用率 | {stab.get('llm_parse_fallback_rate', 0)} |")
        lines.append(f"| Embedding 失败率 | {stab.get('embedding_failure_rate', 0)} |")
        lines.append(f"| Chroma 失败率 | {stab.get('chroma_failure_rate', 0)} |")
        lines.append(f"| 联网检索失败率 | {stab.get('web_search_failure_rate', 0)} |")
        lines.append(f"| 数据保存失败率 | {stab.get('save_failure_rate', 0)} |")

        error_types = stab.get("error_type_breakdown", {})
        if error_types:
            lines.append("")
            lines.append("### 错误类型分布")
            lines.append("")
            lines.append("| 错误类型 | 次数 |")
            lines.append("|---|---|")
            for et, count in sorted(error_types.items()):
                lines.append(f"| {et} | {count} |")
    lines.append("")

    # ── Footer ──
    lines.append("---")
    lines.append("")
    lines.append("*本报告由 evaluation/run_evaluation.py 自动生成。*")
    lines.append("*所有指标均可追溯到 evaluation/output/per_case_results.csv 中的逐样本结果。*")
    lines.append("")

    report = "\n".join(lines)

    output_path = Path(output_dir) / "evaluation_report.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    return report
