from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any


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


def summarize_latencies(values: list[float]) -> dict[str, float | int]:
    cleaned = [float(value) for value in values]
    if not cleaned:
        return {"sample_count": 0, "mean_ms": 0.0, "p50_ms": 0.0, "p95_ms": 0.0, "min_ms": 0.0, "max_ms": 0.0}
    return {
        "sample_count": len(cleaned),
        "mean_ms": round(statistics.fmean(cleaned), 2),
        "p50_ms": round(_percentile(cleaned, 0.50), 2),
        "p95_ms": round(_percentile(cleaned, 0.95), 2),
        "min_ms": round(min(cleaned), 2),
        "max_ms": round(max(cleaned), 2),
    }


def classification_rows(metrics: dict[str, Any], *, run_name: str) -> list[dict[str, Any]]:
    rows = [
        {
            "run": run_name,
            "scope": "overall",
            "label": "all",
            "sample_count": metrics.get("labeled_sample_count"),
            "accuracy": metrics.get("accuracy"),
            "precision": metrics.get("macro_precision"),
            "recall": metrics.get("macro_recall"),
            "f1": metrics.get("macro_f1"),
            "tp": "",
            "fp": "",
            "fn": "",
        }
    ]
    for label, values in metrics.get("per_class", {}).items():
        rows.append(
            {
                "run": run_name,
                "scope": "class",
                "label": label,
                "sample_count": "",
                "accuracy": "",
                "precision": values.get("precision"),
                "recall": values.get("recall"),
                "f1": values.get("f1"),
                "tp": values.get("tp"),
                "fp": values.get("fp"),
                "fn": values.get("fn"),
            }
        )
    return rows


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _requirements_rows() -> list[dict[str, str]]:
    evidence = "evaluation/runs/chapter6_20260628_010246/logs/backend_pytest.log"
    front = "evaluation/runs/chapter6_20260628_010246/logs/frontend_tests.log"
    build = "evaluation/runs/chapter6_20260628_010246/logs/frontend_build.log"
    rows = [
        ("FR-U01", "test_detect_news_rejects_short_title/content；前端表单测试", "新闻输入接口与前端可用", "空值/短文本拒绝，合法输入规范化", "短标题和短正文返回422；前端14项测试通过", f"{evidence}; {front}", "通过"),
        ("FR-U02", "test_extract_preview_*", "URL为HTTP/HTTPS", "提取预览或返回明确失败", "正常提取、SSRF、抓取失败和空内容分支通过", evidence, "通过"),
        ("FR-U03", "test_detect_news_endpoint_returns_success/degraded", "检测依赖可用或可降级", "输出评分、等级、理由和状态", "正常与模型降级接口用例通过", evidence, "通过"),
        ("FR-U04", "test_user_detail_returns_evidence_matches；结果视图构建", "已有检测记录", "展示结果、有效/排除证据与状态", "详情序列化与前端生产构建通过", f"{evidence}; {build}", "通过"),
        ("FR-U05", "test_user_can_read_own_history；test_user_can_re_evaluate_owned_detection_without_overwriting_source", "登录用户有本人记录", "分页、归属隔离、重评新建记录", "对应历史、详情、重评用例通过", evidence, "通过"),
        ("FR-U06", "test_user_can_generate_owned_report；test_real_html_to_pdf_converter_creates_pdf", "登录且记录归本人", "生成PDF，失败不改检测记录", "归属校验与真实PDF转换用例通过", evidence, "通过"),
        ("FR-A01", "test_knowledge_sync.py", "管理员知识操作", "同步状态、重试和恢复可观察", "写入/删除失败、回滚和恢复用例通过", evidence, "通过"),
        ("FR-A02", "test_admin_prompts_api.py；test_prompt_service.py", "管理员身份", "模板校验、启停和默认设置受约束", "无效模板不能启用或设默认", evidence, "通过"),
        ("FR-A03", "test_high_risk_api.py；test_high_risk_service.py", "管理员身份和高风险记录", "复核与公开规则生效", "未批准记录不能公开，权限用例通过", evidence, "通过"),
        ("FR-A04", "test_admin_users_api.py；test_detection_history_api.py；test_admin_reports_api.py", "管理员身份", "全局列表、详情和管理操作", "用户、检测、报告管理用例通过", evidence, "通过"),
        ("FR-A05", "test_admin_statistics_api.py；test_system_logs_api.py", "管理员身份", "聚合统计和分页日志", "统计筛选、权限和日志查询用例通过", evidence, "通过"),
        ("FR-S01", "test_web_search_service.py；搜索服务故障注入", "本地索引与联网开关", "按阈值补充；联网失败保留本地", "触发规则测试通过，注入搜索失败后保留1条本地证据", "backend_pytest.log; reliability_security.log", "通过"),
        ("FR-S02", "test_candidates_have_no_rank_order/present_and_unique；去重测试", "多源候选", "标准化、去重、稳定标识", "候选ID唯一，多种同源重复规则通过", evidence, "通过"),
        ("FR-S03", "test_llm_excludes_irrelevant_kb_evidence", "候选池与模型仲裁返回", "完整划分有效与排除证据", "不相关本地证据被排除，未参与最终证据", evidence, "通过"),
        ("FR-S04", "test_missing_arbitration_retries_and_uses_retry_result；未知ID注入", "首次契约不合格", "聚焦重试一次，仍失败则隔离候选", "成功修复与retry_exhausted分支均通过", "backend_pytest.log; reliability_security.log", "通过"),
        ("FR-S05", "test_detect_news_degrades_and_saves_when_deepseek_fails；无证据分支", "正常/无证据/模型失败", "选择对应评分分支和标准风险等级", "三类路径用例通过", evidence, "通过"),
        ("FR-S06", "test_save_detection_record_persists_analysis_payload；提交失败注入", "评估完成后持久化", "过程可追溯；失败回滚", "过程字段可持久化，但检测记录commit失败未显式rollback", "backend_pytest.log; reliability_security.log", "部分通过"),
        ("NFR-S01", "游客/普通用户/管理员权限测试", "不同角色", "越权请求拒绝且资源归属隔离", "游客401、普通用户403/404、本人资源可访问", "security_test_results.csv", "通过"),
        ("NFR-S02", "短文本、超长正文、非法角色测试", "接口边界", "空值、超长和非法枚举被限制", "短文本及非法角色拒绝；12001字符正文仍通过Schema后由服务层截断", "security_test_results.csv", "部分通过"),
        ("NFR-S03", "私网/协议/重定向安全测试", "URL预览", "每一跳阻断私有/保留地址", "直接地址均阻断；自动重定向后的response.geturl未复核", "security_test_results.csv", "未通过"),
        ("NFR-S04", "test_secret_key_startup_validation；评测脱敏测试", "配置与日志", "密钥不进入源码、普通日志和结果", "弱密钥启动阻断，Bearer/API key脱敏测试通过", "backend_pytest.log; evaluation_tests.log", "通过"),
        ("NFR-R01", "外部服务异常与降级测试", "注入抓取/搜索/模型超时", "失败不被解释为风险升高", "抓取明确失败；搜索保留本地；模型规则降级", "fault_injection_results.csv", "通过"),
        ("NFR-R02", "非JSON、未知ID、缺失字段、重试耗尽", "模型输出异常", "字段/范围/枚举/完整性校验", "结构解析和契约校验用例通过", "fault_injection_results.csv", "通过"),
        ("NFR-D01", "test_knowledge_sync.py", "MySQL与Chroma操作", "同步状态、补偿、重试和重建", "失败状态与恢复用例通过；Alembic仍有模型漂移", "backend_pytest.log; alembic_check.log", "部分通过"),
        ("NFR-E01", "正常、无证据、模型失败详情测试", "检测结果", "给出分量、原因、证据取舍与降级说明", "详情字段与前端状态测试通过", f"{evidence}; {front}", "通过"),
        ("NFR-M01", "模块级测试与配置快照", "项目源码", "职责与外部配置边界清晰", "服务模块和配置集中化可验证；未做长期维护性量化", "environment.json; backend_pytest.log", "部分通过"),
        ("NFR-X01", "Embedding/Search适配器替换测试", "替换供应商/来源", "稳定入口和需求编号", "供应商配置可替换；未执行新增新闻类别的端到端扩展", "backend_pytest.log", "部分通过"),
        ("NFR-P01", "历史分页、管理员统计测试", "存在记录", "分页有界、统计聚合", "page_size上限和聚合接口测试通过", evidence, "通过"),
        ("NFR-P02", "响应体/候选/超时/正文限制测试", "外部调用", "输入和候选有上限且超时退出", "抓取、搜索、模型和候选有限制；正文仅服务层截断", "environment.json; security_test_results.csv", "部分通过"),
        ("NFR-A01", "test_system_log_events_api.py；test_system_logs_api.py", "关键管理操作", "记录操作者、动作、模块和时间", "用户启停等操作产生可查询审计事件", evidence, "通过"),
    ]
    return [
        {"requirement_id": item[0], "test_case": item[1], "precondition": item[2], "expected_result": item[3], "actual_result": item[4], "evidence_file": item[5], "conclusion": item[6]}
        for item in rows
    ]


def _original_record_map(project_root: Path, news_rows: list[dict[str, str]]) -> dict[str, Any]:
    backend = project_root / "backend"
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))
    try:
        from app.db.session import SessionLocal
        from app.models.detection_record import DetectionRecord

        titles = [row["title"] for row in news_rows]
        start = datetime(2026, 6, 24, 20, 50, 0)
        end = datetime(2026, 6, 24, 21, 30, 0)
        with SessionLocal() as db:
            records = (
                db.query(DetectionRecord)
                .filter(DetectionRecord.input_title.in_(titles))
                .filter(DetectionRecord.created_at >= start, DetectionRecord.created_at <= end)
                .all()
            )
            result: dict[str, Any] = {}
            for record in records:
                if record.input_title not in result:
                    _ = list(record.evidence_matches)
                    result[record.input_title] = record
            return result
    except Exception:
        return {}


def generate(project_root: Path, run_dir: Path) -> None:
    original_dir = project_root / "evaluation" / "output"
    results_dir = run_dir / "results"
    metrics = _read_json(original_dir / "metrics.json")
    per_case = _read_csv(original_dir / "per_case_results.csv")
    news = _read_csv(project_root / "evaluation" / "datasets" / "news_eval.csv")

    class_rows = classification_rows(metrics["classification"], run_name="original_20260624")
    _write_csv(results_dir / "classification_metrics.csv", class_rows, ["run", "scope", "label", "sample_count", "accuracy", "precision", "recall", "f1", "tp", "fp", "fn"])

    matrix_rows = []
    for gold, predicted_counts in metrics["classification"]["confusion_matrix"].items():
        matrix_rows.append({"gold_label": gold, **predicted_counts})
    labels = list(metrics["classification"]["confusion_matrix"])
    _write_csv(results_dir / "confusion_matrix.csv", matrix_rows, ["gold_label", *labels])

    retrieval = metrics["retrieval"]
    retrieval_rows = [
        {
            "run": "original_20260624",
            "k": k,
            "annotated_samples": retrieval["annotated_sample_count"],
            "hit_at_k": retrieval["hit_at_k"].get(str(k)),
            "recall_at_k": retrieval["recall_at_k"].get(str(k)),
            "mrr": retrieval["mrr"],
            "mean_retrieval_ms": "未记录",
            "note": "知识条目与主题强对应；K=15未保存候选",
        }
        for k in retrieval["k_values"]
    ]
    _write_csv(results_dir / "retrieval_metrics.csv", retrieval_rows, ["run", "k", "annotated_samples", "hit_at_k", "recall_at_k", "mrr", "mean_retrieval_ms", "note"])
    _write_csv(
        results_dir / "sensitivity_analysis.csv",
        [{"parameter": "Top-K", "value": row["k"], "metric": "Recall@K", "metric_value": row["recall_at_k"], "data_scope": "既有80条整体评测（探索性，非验证集调参）"} for row in retrieval_rows],
        ["parameter", "value", "metric", "metric_value", "data_scope"],
    )

    latency_values = [float(row["total_latency_ms"]) for row in per_case if row.get("total_latency_ms")]
    latency = summarize_latencies(latency_values)
    performance = [{
        "path": "本地检索+模型（联网允许但实际未触发）",
        **latency,
        "success_rate": metrics["stability"]["overall_success_rate"],
        "external_api_ms": "未分阶段记录",
        "total_time_ms": round(sum(latency_values), 2),
        "source": "evaluation/output/per_case_results.csv",
    }]
    _write_csv(results_dir / "performance_results.csv", performance, ["path", "sample_count", "mean_ms", "p50_ms", "p95_ms", "min_ms", "max_ms", "success_rate", "external_api_ms", "total_time_ms", "source"])

    _write_csv(
        results_dir / "web_augmentation_metrics.csv",
        [{
            "policy": "Local+Web按需策略",
            "samples": 80,
            "web_allowed": metrics["web_search"]["web_search_allowed_count"],
            "web_triggered": metrics["web_search"]["web_search_triggered_count"],
            "trigger_rate": metrics["web_search"]["web_trigger_rate"],
            "accuracy": metrics["classification"]["accuracy"],
            "macro_f1": metrics["classification"]["macro_f1"],
            "mean_latency_ms": latency["mean_ms"],
            "interpretation": "全部样本走本地路径，不能据此估计联网增益",
        }],
        ["policy", "samples", "web_allowed", "web_triggered", "trigger_rate", "accuracy", "macro_f1", "mean_latency_ms", "interpretation"],
    )

    test_summary = [
        {"test_group": "后端自动化测试", "command": "python -m pytest tests -q", "passed": 392, "failed": 0, "subtests_passed": 71, "status": "通过", "evidence": "logs/backend_pytest.log"},
        {"test_group": "评测模块测试", "command": "python -m pytest evaluation/tests -q", "passed": 97, "failed": 0, "subtests_passed": 0, "status": "通过", "evidence": "logs/evaluation_tests.log"},
        {"test_group": "前端测试", "command": "npm test", "passed": 14, "failed": 0, "subtests_passed": 0, "status": "通过", "evidence": "logs/frontend_tests.log"},
        {"test_group": "前端生产构建", "command": "npm run build", "passed": 1, "failed": 0, "subtests_passed": 0, "status": "通过（有chunk警告）", "evidence": "logs/frontend_build.log"},
        {"test_group": "Alembic当前版本", "command": "python -m alembic current", "passed": 1, "failed": 0, "subtests_passed": 0, "status": "0007=head", "evidence": "logs/alembic_current.log"},
        {"test_group": "Alembic模型漂移", "command": "python -m alembic check", "passed": 0, "failed": 1, "subtests_passed": 0, "status": "未通过", "evidence": "logs/alembic_check.log"},
    ]
    _write_csv(results_dir / "test_summary.csv", test_summary, ["test_group", "command", "passed", "failed", "subtests_passed", "status", "evidence"])
    _write_csv(results_dir / "requirements_traceability.csv", _requirements_rows(), ["requirement_id", "test_case", "precondition", "expected_result", "actual_result", "evidence_file", "conclusion"])

    records = _original_record_map(project_root, news)
    arbitration_counts: Counter[str] = Counter()
    retry_triggered = retry_fixed = candidate_total = excluded_total = 0
    for record in records.values():
        try:
            payload = json.loads(record.analysis_payload or "{}")
        except json.JSONDecodeError:
            payload = {}
        status = payload.get("arbitration_status", "unavailable")
        arbitration_counts[status] += 1
        attempts = int(payload.get("arbitration_attempts") or 0)
        if attempts >= 2:
            retry_triggered += 1
            if status == "ok":
                retry_fixed += 1
        candidate_total += len(payload.get("candidate_evidence_list") or [])
        excluded_total += len(payload.get("excluded_evidence") or [])
    if records:
        arbitration_rows = [{
            "variant": "Full（既有实现）",
            "samples": len(records),
            "contract_ok": arbitration_counts["ok"],
            "contract_pass_rate": round(arbitration_counts["ok"] / len(records), 4),
            "retry_triggered": retry_triggered,
            "retry_trigger_rate": round(retry_triggered / len(records), 4),
            "retry_fixed": retry_fixed,
            "retry_fix_rate": round(retry_fixed / retry_triggered, 4) if retry_triggered else 0.0,
            "retry_exhausted": arbitration_counts["retry_exhausted"],
            "provider_error": arbitration_counts["provider_error"],
            "candidate_total": candidate_total,
            "excluded_total": excluded_total,
            "note": "数据库2026-06-24 20:50-21:30原始运行记录；无E1-E3对照",
        }]
        _write_csv(results_dir / "arbitration_metrics.csv", arbitration_rows, list(arbitration_rows[0]))

    news_by_id = {row["sample_id"]: row for row in news}
    joined = [{**news_by_id.get(row["sample_id"], {}), **row} for row in per_case]
    selected: list[tuple[str, dict[str, str] | None]] = [
        ("正确评估的可信新闻", next((row for row in joined if row["gold_label"] == row["predicted_label"] == "可信新闻"), None)),
        ("正确识别的高风险新闻", next((row for row in joined if row["gold_label"] == row["predicted_label"] == "高风险谣言"), None)),
        ("证据不足案例", next((row for row in joined if str(row.get("evidence_count")) == "0"), None)),
        ("误判案例", next((row for row in joined if row["gold_label"] != row["predicted_label"]), None)),
    ]
    case_rows: list[dict[str, Any]] = []
    for case_type, row in selected:
        if row is None:
            continue
        record = records.get(row.get("title", ""))
        payload: dict[str, Any] = {}
        if record is not None:
            try:
                payload = json.loads(record.analysis_payload or "{}")
            except json.JSONDecodeError:
                pass
        case_rows.append({
            "case_type": case_type,
            "sample_id": row["sample_id"],
            "title": row.get("title", ""),
            "gold_label": row["gold_label"],
            "predicted_label": row["predicted_label"],
            "local_candidate_count": row.get("local_candidate_count", ""),
            "web_triggered": row.get("web_search_triggered", ""),
            "valid_evidence_count": row.get("valid_evidence_count", ""),
            "excluded_evidence_count": len(payload.get("excluded_evidence") or []),
            "S_L": float(record.llm_score) if record is not None else "未记录",
            "S_E": float(record.evidence_score) if record is not None else "未记录",
            "S_R": float(record.rule_score) if record is not None else "未记录",
            "final_score": row.get("final_score", ""),
            "contract_status": payload.get("arbitration_status", "未记录"),
            "analysis": "分类正确" if row["gold_label"] == row["predicted_label"] else f"真实{row['gold_label']}，预测{row['predicted_label']}；需结合模板化数据与评分阈值分析",
        })
    _write_csv(results_dir / "case_analysis.csv", case_rows, ["case_type", "sample_id", "title", "gold_label", "predicted_label", "local_candidate_count", "web_triggered", "valid_evidence_count", "excluded_evidence_count", "S_L", "S_E", "S_R", "final_score", "contract_status", "analysis"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    generate(args.project_root.resolve(), args.run_dir.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
