from __future__ import annotations

import argparse
import csv
import ctypes
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from evaluation.scripts.chapter6.audit_evaluation import (
    analyze_news_dataset,
    find_near_duplicate_pairs,
    sha256_file,
)


SECRET_KEY_PARTS = ("api_key", "password", "secret", "token")


def _compact_text(value: str) -> str:
    return "".join(str(value).split()).casefold()


def detect_embedded_knowledge(
    news_rows: list[dict[str, str]], knowledge_rows: list[dict[str, str]]
) -> list[dict[str, str]]:
    """Locate knowledge-base texts copied verbatim into evaluation articles."""
    matches: list[dict[str, str]] = []
    normalized_knowledge = [
        (row.get("knowledge_id", ""), _compact_text(row.get("content", "")))
        for row in knowledge_rows
        if row.get("content", "")
    ]
    for news in news_rows:
        news_text = _compact_text(news.get("content", ""))
        for knowledge_id, knowledge_text in normalized_knowledge:
            if knowledge_text and knowledge_text in news_text:
                matches.append(
                    {"sample_id": news.get("sample_id", ""), "knowledge_id": knowledge_id}
                )
    return matches


def redact_secrets(value: Any) -> Any:
    """Return a recursively redacted copy suitable for experiment artifacts."""
    if isinstance(value, dict):
        return {
            key: (
                "[REDACTED]"
                if any(part in str(key).casefold() for part in SECRET_KEY_PARTS)
                else redact_secrets(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    return value


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(redact_secrets(value), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _command_version(command: list[str]) -> str:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
        )
        return (completed.stdout or completed.stderr).strip().splitlines()[0]
    except (OSError, subprocess.SubprocessError, IndexError):
        return "未检测"


def _memory_bytes() -> int | None:
    if os.name != "nt":
        return None

    class MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("length", ctypes.c_ulong),
            ("memory_load", ctypes.c_ulong),
            ("total_physical", ctypes.c_ulonglong),
            ("available_physical", ctypes.c_ulonglong),
            ("total_page_file", ctypes.c_ulonglong),
            ("available_page_file", ctypes.c_ulonglong),
            ("total_virtual", ctypes.c_ulonglong),
            ("available_virtual", ctypes.c_ulonglong),
            ("available_extended_virtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatus()
    status.length = ctypes.sizeof(status)
    return status.total_physical if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)) else None


def build_environment_snapshot(project_root: Path, existing_metadata: dict[str, Any]) -> dict[str, Any]:
    backend_root = project_root / "backend"
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))

    current: dict[str, Any] = {}
    try:
        from app.core.config import get_settings
        from app.services.llm_service import ANALYSIS_CONTRACT_VERSION, _load_deepseek_config

        settings = get_settings()
        llm = _load_deepseek_config()
        current = {
            "deepseek_model": llm.get("model"),
            "deepseek_timeout_seconds": llm.get("timeout_seconds"),
            "embedding_provider": settings.embedding_provider,
            "embedding_model": (
                settings.dashscope_embedding_model
                if settings.embedding_provider == "dashscope"
                else settings.deepseek_embedding_model
            ),
            "embedding_dimension": settings.embedding_dimension,
            "search_service": "Bocha AI",
            "web_search_enabled": settings.web_search_enabled,
            "web_search_timeout_seconds": settings.web_search_timeout_seconds,
            "web_search_result_limit": settings.web_search_count,
            "analysis_contract_version": ANALYSIS_CONTRACT_VERSION,
        }
    except Exception as exc:  # configuration snapshot must not block the audit
        current = {"configuration_probe_error": type(exc).__name__}

    mysql_version = "未检测"
    try:
        from sqlalchemy import text
        from app.db.session import SessionLocal

        with SessionLocal() as session:
            mysql_version = str(session.execute(text("SELECT VERSION()" )).scalar_one())
    except Exception as exc:
        mysql_version = f"未检测（{type(exc).__name__}）"

    try:
        chroma_version = importlib.metadata.version("chromadb")
    except importlib.metadata.PackageNotFoundError:
        chroma_version = "未安装"

    return redact_secrets(
        {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "operating_system": platform.platform(),
            "cpu": platform.processor() or "未检测",
            "logical_cpu_count": os.cpu_count(),
            "memory_bytes": _memory_bytes(),
            "python_version": platform.python_version(),
            "node_version": _command_version(["node", "--version"]),
            "npm_version": _command_version(["npm.cmd" if os.name == "nt" else "npm", "--version"]),
            "git_version": _command_version(["git", "--version"]),
            "mysql_version": mysql_version,
            "chroma_version": chroma_version,
            "current_configuration": current,
            "experiment_configuration": {
                "deepseek_model": existing_metadata.get("model_name"),
                "embedding_provider": existing_metadata.get("embedding_provider"),
                "embedding_model": existing_metadata.get("embedding_model"),
                "top_k": existing_metadata.get("top_k_rag"),
                "web_trigger_rules": existing_metadata.get("web_trigger_rules"),
                "scoring_formula": existing_metadata.get("scoring_formula"),
                "temperature": "未记录",
                "risk_thresholds": {"可信新闻": ">=80", "存疑信息": "60-79.99", "疑似谣言": "40-59.99", "高风险谣言": "<40"},
                "candidate_limit": 10,
                "prompt_or_contract_version": current.get("analysis_contract_version", "2.0"),
            },
        }
    )


def _url_status(url: str) -> tuple[str, str]:
    request = Request(url, headers={"User-Agent": "Chapter6Audit/1.0"})
    try:
        with urlopen(request, timeout=10) as response:
            return str(getattr(response, "status", 200)), str(response.geturl())
    except HTTPError as exc:
        return str(exc.code), str(exc.geturl())
    except (URLError, TimeoutError, OSError) as exc:
        return "unreachable", type(exc).__name__


def _build_inventory(root: Path, audit: dict[str, Any], knowledge_rows: list[dict[str, str]]) -> str:
    evaluation_root = root / "evaluation"
    existing_files = [
        path for path in evaluation_root.rglob("*")
        if path.is_file() and "runs" not in path.parts and "__pycache__" not in path.parts
    ]
    summary = audit["summary"]
    labels = "、".join(f"{key}{value}条" for key, value in summary["label_counts"].items())
    tree = "\n".join(f"- `{path.relative_to(evaluation_root)}`（{path.stat().st_size}字节）" for path in sorted(existing_files))
    fields = "、".join(f"`{name}`" for name in summary["field_names"])
    return f"""# 现有评估资产清单

## 1. 现有目录与文件

{tree}

## 2. 数据文件及实际用途

- `datasets/news_eval.csv`：`output/run_metadata.json`记录的正式评测输入；共{summary['sample_count']}条，既有逐样本预测与汇总指标均由该文件产生。
- `datasets/knowledge_base_eval.csv`：20条评测专用知识，`admin_note`标识用于把`EVAL-KB-*`解析为MySQL知识ID。
- `datasets/news_eval_demo.csv`：仅用于验证评测链路，`DEMO-*`会被正式指标排除。
- `datasets/news_eval_template.csv`：评测输入字段模板，不是已标注正式样本。

## 3. 数据集规模、类别与划分

- 正式评测集：{summary['sample_count']}条；知识条目：{len(knowledge_rows)}条；主题：{summary['topic_count']}个。
- 类别分布：{labels}。
- 数据没有`split`、`validation`或`test`字段；既有命令把80条整体作为一次评测输入。可确认的独立验证集数量为0，不能从文件中确认训练/验证/测试划分。
- 80条样本均标注为“待两名真人复核”，评审列是兼容性预标注，不是两名真人独立标注。

## 4. 数据字段

{fields}

## 5. 已有实验脚本与结果

- 脚本：`run_evaluation.py`、`metrics.py`、`report.py`及评测模块自动化测试（本次数量见`results/test_summary.csv`）。
- 结果：`per_case_results.csv`、`metrics.json`、`evaluation_report.md`、`error_analysis.md`、`failure_cases.csv`、`run_metadata.json`和断点文件。
- 已完成实验：80条端到端评测、分类指标、Top-K检索命中/召回、响应时间、证据完整性与失败类型统计。

## 6. 当前缺失或无法确认的实验

- 没有独立验证集，不能合规完成参数选择型敏感性分析。
- 既有结果没有分阶段耗时、联网触发原因、候选仲裁逐条契约状态和网络候选快照。
- 既有80条运行未触发联网，不能由该结果估计联网补充收益；Always-Web对照也没有真实结果。
- 没有B1/B2/B3/B4/Full同样本基线文件，也没有E1-E4完整仲裁消融的原始预测。
- 不能确认两名真人独立复核结果，Cohen's Kappa=1.0不作为真人一致性结论。

## 7. 数据质量风险

- 每个主题四条样本共用URL，存在预期的URL重复；正文使用统一模板，近重复会放大表述模式信号。
- 评测知识文本被逐字嵌入新闻正文，且每个主题对应知识条目，导致检索指标明显高估开放场景表现。
- CFEVER事实核查标签到四级新闻风险的映射属于项目适配，不等同于原始新闻风险人工标注。
- 缺少数据划分字段，无法验证同一事件是否跨验证集与测试集泄漏。
- 本清单只报告问题，不删除、改写或重新划分任何样本。
"""


def _existing_experiment_review(metadata: dict[str, Any], metrics: dict[str, Any]) -> str:
    return f"""# 已有实验复核

## 实验输入与配置

- 数据文件：`evaluation/datasets/news_eval.csv`，SHA-256为`{metadata.get('dataset_file_hash')}`。
- 样本：NEWS-EVAL-001至NEWS-EVAL-080，共80条，四类各20条。
- 模型：`{metadata.get('model_name')}`；Embedding：`{metadata.get('embedding_provider')}/{metadata.get('embedding_model')}`。
- Prompt/契约：既有元数据未记录Prompt内容哈希；当前代码契约版本为2.0，因此不能反推原运行的Prompt文本版本。
- Top-K：{metadata.get('top_k_rag')}；联网允许：{metadata.get('web_search_enabled_global')}，实际触发0次。
- 触发规则：{json.dumps(metadata.get('web_trigger_rules'), ensure_ascii=False)}。
- 评分：{metadata.get('scoring_formula')}。
- 命令：`{metadata.get('command')}`。

## 运行与输出

- 既有结果属于一次完整运行，不是多次重复实验；80/80成功，保存了逐样本原始预测。
- Accuracy={metrics.get('classification', {}).get('accuracy')}，Macro-F1={metrics.get('classification', {}).get('macro_f1')}。
- 平均延迟={metrics.get('latency', {}).get('total_latency_ms', {}).get('avg')}ms，P95={metrics.get('latency', {}).get('total_latency_ms', {}).get('p95')}ms。
- Recall@1={metrics.get('retrieval', {}).get('recall_at_k', {}).get('1')}，MRR={metrics.get('retrieval', {}).get('mrr')}；该值受评测知识与主题强对应影响。
- 失败样本：端到端失败0条；报告另记约15次模型超时后降级，但逐样本`is_timeout`字段没有保存这些次数，二者存在记录口径不一致。

## 可复现性判断

输入、命令、模型别名、数据哈希和逐样本结果齐全，具备重新执行条件；但外部模型服务版本、Prompt内容哈希、MySQL/Chroma快照未冻结，因此只能检验操作可复现性，不能保证逐样本完全一致。本次复现结果见`results/existing_experiment_reproduction.csv`；如外部服务或额度阻断，将如实记录而不伪造。
"""


def generate(project_root: Path, run_dir: Path, *, check_urls: bool) -> None:
    data_dir = project_root / "evaluation" / "datasets"
    output_dir = project_root / "evaluation" / "output"
    news_path = data_dir / "news_eval.csv"
    knowledge_path = data_dir / "knowledge_base_eval.csv"
    audit = analyze_news_dataset(news_path, check_urls=check_urls)
    knowledge_rows = _read_csv(knowledge_path)
    metadata = _read_json(output_dir / "run_metadata.json")
    metrics = _read_json(output_dir / "metrics.json")

    issues = list(audit["issues"])
    near_pairs = find_near_duplicate_pairs(audit["rows"], field="content", threshold=0.80)
    for pair in near_pairs:
        issues.append({
            "issue_type": "near_duplicate_content",
            "sample_id": pair["sample_id_a"],
            "related_ids": pair["sample_id_b"],
            "field": "content",
            "details": f"正文相似度={pair['similarity']:.4f}; same_topic={pair['same_topic']}",
            "severity": "warning",
            "check_scope": "offline",
        })

    embedded = detect_embedded_knowledge(audit["rows"], knowledge_rows)
    for match in embedded:
        issues.append({
            "issue_type": "knowledge_text_embedded",
            "sample_id": match["sample_id"],
            "related_ids": match["knowledge_id"],
            "field": "content",
            "details": "知识库正文被逐字包含在评测新闻正文中",
            "severity": "high",
            "check_scope": "offline",
        })

    if audit["summary"]["split_field"] == "未提供":
        issues.append({
            "issue_type": "split_leakage_unverifiable",
            "sample_id": "",
            "related_ids": "",
            "field": "split/topic_id",
            "details": "数据无划分字段，无法验证同事件是否跨验证集和测试集",
            "severity": "high",
            "check_scope": "offline",
        })

    url_statuses: dict[str, tuple[str, str]] = {}
    if check_urls:
        for url in sorted({row.get("url", "") for row in audit["rows"] if row.get("url", "")}):
            url_statuses[url] = _url_status(url)
        for row in audit["rows"]:
            status, detail = url_statuses.get(row.get("url", ""), ("not_checked", ""))
            if status == "unreachable" or (status.isdigit() and int(status) >= 400):
                issues.append({
                    "issue_type": "url_unavailable_at_audit_time",
                    "sample_id": row.get("sample_id", ""),
                    "related_ids": "",
                    "field": "url",
                    "details": f"status={status}; detail={detail}",
                    "severity": "warning",
                    "check_scope": "network_snapshot",
                })

    results_dir = run_dir / "results"
    audit_dir = run_dir / "audit"
    configs_dir = run_dir / "configs"
    _write_csv(
        results_dir / "data_quality_report.csv",
        issues,
        ["issue_type", "sample_id", "related_ids", "field", "details", "severity", "check_scope"],
    )
    summary_rows = [
        {"dataset": "news_eval.csv", "role": "既有正式评测输入", "group": "all", "count": len(audit["rows"]), "sha256": sha256_file(news_path)},
        {"dataset": "knowledge_base_eval.csv", "role": "评测专用知识库", "group": "all", "count": len(knowledge_rows), "sha256": sha256_file(knowledge_path)},
    ]
    summary_rows.extend(
        {"dataset": "news_eval.csv", "role": "标签分布", "group": label, "count": count, "sha256": sha256_file(news_path)}
        for label, count in audit["summary"]["label_counts"].items()
    )
    _write_csv(results_dir / "dataset_summary.csv", summary_rows, ["dataset", "role", "group", "count", "sha256"])

    issue_counts = Counter(row["issue_type"] for row in issues)
    (audit_dir / "data_quality_summary.md").write_text(
        "# 数据质量检查摘要\n\n"
        f"- 检查样本：{len(audit['rows'])}条；知识条目：{len(knowledge_rows)}条。\n"
        f"- URL完全重复样本记录：{issue_counts['duplicate_url']}条；标题完全重复：{issue_counts['duplicate_title']}条；正文完全重复：{issue_counts['duplicate_content']}条。\n"
        f"- 正文近重复对：{issue_counts['near_duplicate_content']}对（SequenceMatcher>=0.80）。\n"
        f"- 嵌入知识库原文：{issue_counts['knowledge_text_embedded']}条。\n"
        f"- 标签缺失/非法：{issue_counts['missing_label'] + issue_counts['invalid_label']}条；正文为空/过短：{issue_counts['empty_content'] + issue_counts['short_content']}条。\n"
        f"- URL网络不可用记录：{issue_counts['url_unavailable_at_audit_time']}条（仅代表审计时快照）。\n"
        "- 无数据划分字段，事件跨验证/测试泄漏无法确认；未对原始数据作删除、改写或重新划分。\n"
        "- 建议排除清单不直接生效：若后续建立独立验证/测试集，应按topic_id分组划分，并移除正文中逐字嵌入的知识答案后重新人工标注。\n",
        encoding="utf-8",
    )
    (audit_dir / "evaluation_inventory.md").write_text(
        _build_inventory(project_root, audit, knowledge_rows), encoding="utf-8"
    )
    (audit_dir / "existing_experiment_review.md").write_text(
        _existing_experiment_review(metadata, metrics), encoding="utf-8"
    )

    environment = build_environment_snapshot(project_root, metadata)
    _write_json(configs_dir / "experiment_environment.json", environment)
    _write_json(results_dir / "environment.json", environment)
    _write_json(
        audit_dir / "input_hashes_before.json",
        {
            str(path.relative_to(project_root)): sha256_file(path)
            for path in sorted([*data_dir.glob("*.csv"), *output_dir.glob("*")])
            if path.is_file()
        },
    )
    _write_json(audit_dir / "url_check_snapshot.json", url_statuses)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate read-only Chapter 6 audit artifacts.")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--check-urls", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generate(args.project_root.resolve(), args.run_dir.resolve(), check_urls=args.check_urls)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
