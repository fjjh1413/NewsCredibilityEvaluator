from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Any


def _csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _cell(value: Any) -> str:
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(_cell(item) for item in row) + " |" for row in rows)
    return "\n".join(lines)


def _pct(value: Any, digits: int = 2) -> str:
    try:
        return f"{float(value) * 100:.{digits}f}%"
    except (TypeError, ValueError):
        return "不可用"


def _f(value: Any, digits: int = 4) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "不可用"


def build_chapter(project_root: Path, run_dir: Path) -> str:
    results = run_dir / "results"
    figures = run_dir / "figures"
    env = _json(results / "environment.json")
    original = _json(project_root / "evaluation" / "output" / "metrics.json")
    data_quality = _csv(results / "data_quality_report.csv")
    test_summary = _csv(results / "test_summary.csv")
    requirements = _csv(results / "requirements_traceability.csv")
    retrieval = _csv(results / "retrieval_metrics.csv")
    web_metrics = _csv(results / "web_augmentation_metrics.csv")
    arbitration = _csv(results / "arbitration_metrics.csv")
    classification = _csv(results / "classification_metrics.csv")
    sensitivity = _csv(results / "sensitivity_analysis.csv")
    faults = _csv(results / "fault_injection_results.csv")
    security = _csv(results / "security_test_results.csv")
    performance = _csv(results / "performance_results.csv")
    cases = _csv(results / "case_analysis.csv")
    reproduction = _csv(results / "existing_experiment_reproduction.csv")
    stability = _csv(results / "stability_metrics.csv")
    backend_test_count = next((row["passed"] for row in test_summary if row["test_group"] == "后端自动化测试"), "未记录")
    evaluation_test_count = next((row["passed"] for row in test_summary if row["test_group"] == "评测模块测试"), "未记录")
    frontend_test_count = next((row["passed"] for row in test_summary if row["test_group"] == "前端测试"), "未记录")

    issue_counts = Counter(row["issue_type"] for row in data_quality)
    req_counts = Counter(row["conclusion"] for row in requirements)
    req_groups: dict[str, Counter[str]] = {
        "FR-U": Counter(), "FR-A": Counter(), "FR-S": Counter(), "NFR": Counter()
    }
    for row in requirements:
        rid = row["requirement_id"]
        group = "FR-U" if rid.startswith("FR-U") else "FR-A" if rid.startswith("FR-A") else "FR-S" if rid.startswith("FR-S") else "NFR"
        req_groups[group][row["conclusion"]] += 1

    current = env.get("current_configuration", {})
    experiment = env.get("experiment_configuration", {})
    classification_overall = next((row for row in classification if row["scope"] == "overall"), {})
    class_rows = [row for row in classification if row["scope"] == "class"]
    arb = arbitration[0] if arbitration else {}
    web = web_metrics[0] if web_metrics else {}
    reproduction_by_metric = {row["metric"]: row for row in reproduction}
    stability_by_metric = {row["metric"]: row["value"] for row in stability}
    stability_table_rows = [
        [f"stability:{row['metric']}", "三次重复", row["value"], row["note"]]
        for row in stability
    ]
    if reproduction:
        repro_table = _table(
            ["指标", "原运行", "本次复现", "差异/说明"],
            [[row["metric"], row["original"], row["reproduction"], row["difference_or_note"]] for row in reproduction]
            + stability_table_rows,
        )
    else:
        repro_table = _table(["状态", "结果"], [["复现", "后台执行中；最终稿生成前将据实更新，当前不作成功结论"]])
    reproduction_text = (
        f"本次复现成功处理{reproduction_by_metric.get('success_count', {}).get('reproduction')}条、失败"
        f"{reproduction_by_metric.get('failure_count', {}).get('reproduction')}条，Accuracy为"
        f"{_f(reproduction_by_metric.get('accuracy', {}).get('reproduction'))}，Macro-F1为"
        f"{_f(reproduction_by_metric.get('macro_f1', {}).get('reproduction'))}，平均响应时间为"
        f"{_f(reproduction_by_metric.get('mean_latency_ms', {}).get('reproduction'), 2)}ms。与原运行相比，逐样本风险标签一致率为"
        f"{_pct(reproduction_by_metric.get('risk_label_consistency_rate', {}).get('reproduction'))}，候选知识ID集合平均Jaccard为"
        f"{_f(reproduction_by_metric.get('retrieved_candidate_jaccard', {}).get('reproduction'))}。"
        "差异反映外部模型输出与服务状态的实际波动，不作逐字复现假设。"
        if reproduction else
        "本次复现尚未生成最终指标，正文不作完成结论。"
    )
    stability_text = (
        f"为描述外部模型波动，另对三次运行共同的{stability_by_metric.get('shared_sample_count')}条样本进行稳定性复测。"
        f"三次预测标签完全一致率为{_pct(stability_by_metric.get('prediction_all_same_rate'))}，逐样本最终分总体标准差均值为"
        f"{_f(stability_by_metric.get('mean_final_score_stddev'), 2)}；全部重复观测的响应时间均值、P50、P95和总体标准差分别为"
        f"{_f(stability_by_metric.get('latency_avg_ms'), 2)}ms、{_f(stability_by_metric.get('latency_p50_ms'), 2)}ms、"
        f"{_f(stability_by_metric.get('latency_p95_ms'), 2)}ms和{_f(stability_by_metric.get('latency_stddev_ms'), 2)}ms。"
        "该子集仅用于重复性描述，不替代80条完整评测。"
        if stability else
        "第三次稳定性子集运行尚未生成最终统计，正文不据此填写稳定性结论。"
    )

    environment_table = _table(
        ["项目", "配置或实测值"],
        [
            ["操作系统", env.get("operating_system")],
            ["处理器/内存", f"{env.get('cpu')}；{(env.get('memory_bytes') or 0) / 1024**3:.2f}GB；{env.get('logical_cpu_count')}逻辑核心"],
            ["Python/Node.js/npm", f"{env.get('python_version')} / {env.get('node_version')} / {env.get('npm_version')}"],
            ["MySQL/Chroma", f"{env.get('mysql_version')} / {env.get('chroma_version')}"],
            ["大语言模型", current.get("deepseek_model")],
            ["Embedding", f"{current.get('embedding_provider')}/{current.get('embedding_model')}，{current.get('embedding_dimension')}维"],
            ["联网服务", f"{current.get('search_service')}，超时{current.get('web_search_timeout_seconds')}s，最多{current.get('web_search_result_limit')}条"],
            ["本地检索", f"Top-K={experiment.get('top_k')}，触发阈值0.45/0.60，有效候选相似度下限0.30"],
            ["模型超时/契约", f"{current.get('deepseek_timeout_seconds')}s / v{current.get('analysis_contract_version')}"],
            ["风险阈值", "可信≥80；存疑[60,80)；疑似谣言[40,60)；高风险<40"],
        ],
    )
    dataset_table = _table(
        ["数据资产", "数量", "组成/用途", "划分状态"],
        [
            ["news_eval.csv", 80, "20个主题；可信、存疑、疑似谣言、高风险各20条", "无split字段；既有实验整体作为测试输入"],
            ["knowledge_base_eval.csv", 20, "每个主题1条评测专用知识", "不属于训练/验证划分"],
            ["news_eval_demo.csv", "DEMO", "仅验证评测链路，指标自动排除", "非正式评测"],
            ["独立验证集", 0, "现有资产未提供", "不得自行拆分测试集"],
        ],
    )
    metric_table = _table(
        ["指标", "定义与使用边界"],
        [
            ["Accuracy、Macro-Precision/Recall/F1", "四类风险标签整体分类效果；当前金标来自CFEVER共识标签与固定映射，仍待真人复核"],
            ["各类Precision/Recall/F1、混淆矩阵", "观察类别偏差与误判方向"],
            ["Hit@K、Recall@K、MRR", "仅基于relevant_knowledge_ids；评测知识与主题强对应，不能外推开放检索"],
            ["契约通过率、重试率、修复率", "反映结构契约执行情况，不表示证据事实正确率"],
            ["平均值、P50、P95、最小/最大值", "响应时间描述性统计；不同路径样本量不同"],
        ],
    )
    req_table = _table(
        ["需求组", "通过", "部分通过", "未通过", "主要边界"],
        [
            [group, counts["通过"], counts["部分通过"], counts["未通过"],
             "完整逐项证据见requirements_traceability.csv"]
            for group, counts in req_groups.items()
        ],
    )
    tests_table = _table(
        ["测试组", "通过", "失败", "结果"],
        [[row["test_group"], row["passed"], row["failed"], row["status"]] for row in test_summary],
    )
    retrieval_table = _table(
        ["K", "Hit@K", "Recall@K", "MRR", "平均检索耗时"],
        [[row["k"], _f(row["hit_at_k"]), _f(row["recall_at_k"]), _f(row["mrr"]), row["mean_retrieval_ms"]] for row in retrieval],
    )
    web_table = _table(
        ["策略", "允许联网", "实际触发", "触发率", "Accuracy", "Macro-F1", "解释"],
        [[web.get("policy"), web.get("web_allowed"), web.get("web_triggered"), _pct(web.get("trigger_rate")), _f(web.get("accuracy")), _f(web.get("macro_f1")), web.get("interpretation")]],
    )
    arbitration_table = _table(
        ["方案", "样本", "契约通过", "重试触发", "重试修复", "重试耗尽", "模型服务失败"],
        [[arb.get("variant"), arb.get("samples"), f"{arb.get('contract_ok')}（{_pct(arb.get('contract_pass_rate'))}）", f"{arb.get('retry_triggered')}（{_pct(arb.get('retry_trigger_rate'))}）", f"{arb.get('retry_fixed')}（{_pct(arb.get('retry_fix_rate'))}）", arb.get("retry_exhausted"), arb.get("provider_error")]],
    )
    classification_table = _table(
        ["范围/类别", "Precision", "Recall", "F1", "TP", "FP", "FN"],
        [["宏平均", row.get("precision"), row.get("recall"), row.get("f1"), "—", "—", "—"] if row["scope"] == "overall" else [row["label"], row["precision"], row["recall"], row["f1"], row["tp"], row["fp"], row["fn"]] for row in classification],
    )
    sensitivity_table = _table(
        ["参数", "取值", "指标", "结果", "数据范围"],
        [[row["parameter"], row["value"], row["metric"], row["metric_value"], row["data_scope"]] for row in sensitivity],
    )
    fault_table = _table(
        ["故障", "观测行为", "结论"],
        [[row["fault_case"], row["observed_behavior"], row["conclusion"]] for row in faults],
    )
    selected_security = [
        row for row in security
        if row["security_case"] in {"游客访问个人历史", "普通用户访问他人检测详情", "普通用户访问管理员接口", "过期JWT", "私网IP", "公网URL重定向到私网", "超长正文", "SQL特殊字符", "新闻文本含提示注入指令"}
    ]
    security_table = _table(
        ["场景", "状态/观测", "数据库变化", "结论"],
        [[row["security_case"], f"{row['http_status']}；{row['response_summary']}", row["database_changed"], row["conclusion"]] for row in selected_security],
    )
    performance_table = _table(
        ["运行路径", "样本", "平均/ms", "P50/ms", "P95/ms", "最小/ms", "最大/ms", "成功率"],
        [[row["path"], row["sample_count"], row["mean_ms"], row["p50_ms"], row["p95_ms"], row["min_ms"], row["max_ms"], _pct(row["success_rate"])] for row in performance],
    )
    case_table = _table(
        ["案例", "sample_id", "人工/系统标签", "候选/有效/排除", "S_L/S_E/S_R", "最终分", "契约"],
        [[row["case_type"], row["sample_id"], f"{row['gold_label']}/{row['predicted_label']}", f"{row['local_candidate_count']}/{row['valid_evidence_count']}/{row['excluded_evidence_count']}", f"{row['S_L']}/{row['S_E']}/{row['S_R']}", row["final_score"], row["contract_status"]] for row in cases],
    )

    return f"""# 第6章系统测试与实验分析

## 6.1测试目标与实验问题

### 6.1.1测试目标

本章依据第2章FR-U01至FR-U06、FR-A01至FR-A05、FR-S01至FR-S06及全部NFR编号，对“输入—检索—联网补充—证据仲裁—分支评分—持久化—报告与管理”链路进行验收。测试先复核现有`evaluation`资产及2026年6月24日的一次80样本运行，再在不改写数据集、标签、划分和生产评分逻辑的前提下补充自动化回归、数据质量、故障注入、安全与性能验证。实验结论仅覆盖当前软硬件、数据与外部服务状态。

### 6.1.2实验问题与验证内容

本章设置RQ1至RQ8。RQ1考察需求实现；RQ2考察本地语义召回；RQ3考察按需联网的证据覆盖与调用控制；RQ4考察仲裁、契约校验和聚焦重试；RQ5考察完整系统相对规则、裸模型与简单RAG基线；RQ6考察正常、无有效证据和模型失败三类评分分支；RQ7考察故障、越权和恶意输入；RQ8考察不同路径的时间开销。凡现有数据或结果不足以回答的问题，本章明确标为未完成，不以代码设计或假设数值代替实验结果。

## 6.2测试环境与实验数据

### 6.2.1软硬件及外部服务环境

表6-1给出本次环境快照。密钥字段未写入结果、日志和论文。

表6-1 测试与实验环境

{environment_table}

### 6.2.2现有实验数据集说明

表6-2显示，正式评测输入含80条中文样本，20个主题各构造四类风险样本，类别数量均衡；另有20条评测知识。数据没有独立验证集或显式测试划分字段，因此本章不自行拆分数据，也不在同一80条上选择“最优”参数。`gold_label`来自CFEVER公开共识标签与本项目固定四级映射，80条记录均标记为待两名真人复核，不能把预填的两个评审列解释为真人独立双标。

表6-2 现有数据集组成

{dataset_table}

![评测数据集类别分布]({figures / 'dataset_class_distribution.png'})

图6-1 评测数据集类别分布

### 6.2.3数据质量与实验控制

只读审计发现：URL完全重复记录{issue_counts['duplicate_url']}条，对应每个主题四类样本共用同一来源；标题和正文完全重复均为0；正文相似度不低于0.80的样本对为{issue_counts['near_duplicate_content']}对；80条样本均逐字包含对应评测知识正文。该结构有利于验证链路是否能找到指定知识，但也会使检索任务近似“主题对齐”，并让模型接触到显式核验依据。因此后续Recall@K只能解释为受控条件下的召回上限，不能代表真实开放新闻场景。

标签缺失、非法标签、空正文和过短正文均为0。20个唯一URL在审计时均可达，但可达性是时间快照。由于没有划分字段，无法验证同一事件是否跨验证集与测试集；本章没有删除、改写、重新标注或重新划分任何样本。建议未来按`topic_id`分组建立独立验证/测试集，并在移除正文中显式知识答案后重新进行真人风险标注。

### 6.2.4评价指标

表6-3列出实际使用的指标及边界。契约通过率只说明结构合格，不说明证据事实正确；检索相似度和Recall@K也不等于证据可信度。

表6-3 评价指标

{metric_table}

## 6.3系统功能与需求验收测试

### 6.3.1用户端功能测试

用户端重点覆盖手工输入、URL预览、检测结果、个人历史、重新评估和报告。后端对短标题、短正文、非法URL、抓取失败和SSRF直连地址返回明确错误；合法检测可返回评分、等级、理由与证据状态。登录用户只能读取本人历史和报告，重新评估生成新记录。前端14项Node测试通过，生产构建完成，但构建日志提示ECharts包体超过500kB，该警告属于性能优化事项，不影响本次构建成功结论。

### 6.3.2管理员端功能测试

管理员相关测试覆盖用户、检测、知识、Prompt、高风险、报告、统计和系统日志。普通用户访问管理接口被拒绝；无效Prompt不能设为默认；未审核高风险记录不能公开；知识向量失败状态、单条恢复和全量重建入口均有自动化用例。当前数据库Alembic修订号为`0007_analysis_payload(head)`，但`alembic check`检测到实际库与ORM仍有字段、默认值和注释差异，因此数据库版本“到达head”不等于模式完全一致。

### 6.3.3智能评估支撑功能测试

智能链路测试覆盖Top-10候选、按阈值联网、候选去重与唯一ID、来源中立排序、有效/排除证据划分、契约校验、聚焦重试和三类评分分支。搜索服务注入失败后仍使用1条本地有效证据；模型失败时只使用规则分；仲裁重试仍失败时有效证据列表为空。另一方面，检测记录`commit()`失败注入显示异常会向上传播，但CRUD函数未显式调用`rollback()`，与前文设计描述不一致，故FR-S06只能判为部分通过。

### 6.3.4需求追踪与验收结果汇总

本次后端{backend_test_count}项测试与71个子测试、评测模块{evaluation_test_count}项测试、前端{frontend_test_count}项测试均通过。30项需求中，通过{req_counts['通过']}项、部分通过{req_counts['部分通过']}项、未通过{req_counts['未通过']}项；完整逐项矩阵见`requirements_traceability.csv`。

表6-4 需求—测试追踪矩阵汇总

{req_table}

表6-5 自动化与功能测试结果

{tests_table}

## 6.4新闻可信度评估方法实验

### 6.4.1已有实验复现与结果核验

既有实验于2026年6月24日使用`news_eval.csv`、`deepseek-v4-pro`、DashScope`text-embedding-v4`、Top-K=10和按需联网开关完成一次80样本运行。数据哈希、命令、逐样本预测和汇总指标均已保存，但Prompt内容哈希、MySQL与Chroma快照没有冻结，因此只能验证操作可复现性，不能要求外部模型逐字一致。原运行80/80成功，Accuracy为{_f(original.get('classification', {}).get('accuracy'))}，Macro-F1为{_f(original.get('classification', {}).get('macro_f1'))}，平均响应时间{_f(original.get('latency', {}).get('total_latency_ms', {}).get('avg'), 2)}ms。

{reproduction_text}

表6-6 已有实验复现结果

{repro_table}

{stability_text}

### 6.4.2本地语义检索效果

现有输出仅保存Top-10候选，因而可计算K=1、3、5、10，不能补写K=15。表6-7显示各K的Hit与Recall均为1，MRR为1。该结果与80条新闻逐字包含对应知识正文、20个主题与20条知识强对应的结构一致，反映的是受控链路召回能力，而不是一般中文新闻检索性能。原评测未保存独立检索阶段耗时，故该列如实标为未记录。

表6-7 本地检索结果

{retrieval_table}

![本地检索Recall曲线]({figures / 'retrieval_recall_at_k.png'})

图6-2 本地检索Recall@K曲线

### 6.4.3按需联网补充效果

80条样本均允许联网，但本地Top-1相似度为0.7411～0.9215，高于触发阈值，实际触发0次。因此表6-8只能说明按需规则避免了80次不必要的搜索调用，不能回答联网是否改善证据覆盖，也不能把该运行当成Local与Local+Web的有效对照。Always-Web未执行，原因是没有与现有样本公平对齐的原始网络候选快照，且不允许虚构外部搜索结果。

表6-8 按需联网补充观测结果

{web_table}

### 6.4.4证据仲裁与契约校验效果

从原运行数据库快照恢复的80条分析载荷显示，67条契约状态为`ok`，5条触发第二次仲裁，其中4条修复、1条耗尽；另有12条为模型服务失败。候选总数800，排除证据600。重试修复率80%只针对5个已触发样本，样本量很小。由于没有E1至E3同样本结果，本章不能把Full方案与“无校验”方案作因果比较，也不能把83.75%的结构通过率解释为事实准确率。

表6-9 证据仲裁结果

{arbitration_table}

![证据仲裁状态分布]({figures / 'arbitration_status_distribution.png'})

图6-3 既有运行证据仲裁状态分布

### 6.4.5总体风险分类效果

原运行Accuracy={classification_overall.get('accuracy')}，Macro-Precision={classification_overall.get('precision')}，Macro-Recall={classification_overall.get('recall')}，Macro-F1={classification_overall.get('f1')}。可信新闻召回率为1.0，但高风险谣言召回率仅0.2；系统明显偏向预测可信新闻和疑似谣言。混淆矩阵中，14条存疑信息被判为疑似谣言，12条疑似谣言被判为可信新闻，9条高风险谣言被判为疑似谣言。结果显示当前四级风险边界仍不稳定，不能宣称已经准确识别各类谣言。

表6-10 总体风险分类结果

{classification_table}

![四分类混淆矩阵]({figures / 'classification_confusion_matrix.png'})

图6-4 四分类混淆矩阵

![各风险类别F1]({figures / 'classification_per_class_f1.png'})

图6-5 各风险类别F1

## 6.5消融实验与参数敏感性分析

### 6.5.1多源证据获取机制消融

现有运行未触发联网，因而“完整系统”和“去掉联网补充”在实际执行路径上完全相同；仅网络候选与去掉候选去重也没有原始预测。为避免把相同路径重复包装为消融，本章不生成多源证据消融表。该实验需在包含本地低覆盖主题、且网络候选快照可复用的数据上重新设计。

### 6.5.2证据仲裁机制消融

当前可确认Full方案的契约状态和重试修复情况，但没有直接Top-K、无完整覆盖校验和无聚焦重试三组同样本预测。表6-9属于机制运行统计，不是E1—E4对照。现有故障注入证明未知ID、缺失仲裁和重试耗尽会被结构校验阻断，但不能量化仲裁对分类F1的净影响。

### 6.5.3分支式评分机制消融

自动化测试分别执行了有有效证据、无有效证据和模型失败路径，确认公式分支与风险枚举按代码工作；模型失败样本不使用未经仲裁的候选。由于未保存固定评分、去掉证据质量、去掉规则分等同样本结果，本章不报告虚构的消融提升，也不进行B1—B4与Full的总体方法优劣比较，RQ5因此保持未回答。

### 6.5.4关键参数敏感性分析

没有独立验证集，故本章只把已有K值视为探索性描述。K=1时已达到Recall=1，增加K没有改善，这是强对应数据结构造成的天花板现象，而不是K=1在生产环境最优。联网阈值与评分权重没有在最终80条上反复调节，Top-K=15也因既有输出只保留10条而未计算。

表6-11 Top-K探索性敏感性结果

{sensitivity_table}

## 6.6可靠性、安全性与性能测试

### 6.6.1外部服务故障与降级测试

故障注入共11项，其中10项符合预期，检测记录数据库提交失败1项未通过。URL抓取、Embedding、Chroma、搜索、模型非JSON、未知ID、聚焦重试耗尽、向量同步和PDF失败均有真实执行日志或本次注入结果。表6-12列出观测值；“通过”仅表示系统行为符合该用例预期，不代表真实生产故障的全部表现。

表6-12 故障注入结果

{fault_table}

### 6.6.2跨存储一致性与恢复测试

知识新增、修改和删除的Chroma失败用例验证了`failed`、`delete_failed`、数据库回滚与向量恢复路径。Chroma查询失败会清理缓存并重试一次。当前Alembic修订号到达head，但模式漂移检查未通过，实际库仍含ORM未声明的`evidence_matches.origin`和`url`等差异。因此可以确认应用层补偿路径存在，不能宣称MySQL与Chroma或ORM与实际库始终一致。

### 6.6.3权限与URL安全测试

18项安全场景中，游客、越权用户、空/过期/伪造JWT、直接私网地址、非HTTP协议和SQL特殊字符均被拒绝或安全处理。公网URL自动重定向到私网的模拟揭示`urllib.request.urlopen`会默认跟随重定向，而当前实现未检查`response.geturl()`，与前文“逐跳复核”不一致；该项未通过。12001字符正文可通过Schema并在服务层被截为12000字符，故接口边界限长为部分通过。Prompt注入文本被放入`news_content`边界，说明已有结构隔离，但不能据此宣称彻底抵御Prompt注入。

表6-13 关键安全测试结果

{security_table}

### 6.6.4响应时间与资源开销测试

端到端80样本平均24.27s、P95为37.06s，主要包含Embedding、检索与模型调用，但既有脚本未拆分阶段耗时。MySQL历史分页与统计概览各重复20次；PDF使用既有检测内容生成5次，首轮字体/渲染初始化造成最大值较高；URL提取对既有样本URL运行3次。样本量和路径不同，表6-14用于描述当前环境，不用于推导并发容量。1、5、10并发及外部联网模型路径没有执行，以避免在额度与限流未知时给出不稳定结论。

表6-14 性能测试结果

{performance_table}

![不同运行路径响应时间]({figures / 'response_time_summary.png'})

图6-6 不同运行路径平均响应时间

## 6.7典型案例与错误分析

### 6.7.1正确评估案例

NEWS-EVAL-001的真实与预测标签均为可信新闻，S_L=95、S_E=87.71、S_R=80，最终分91.7，契约状态为`ok`。NEWS-EVAL-004的真实与预测标签均为高风险谣言，S_L=20、S_E=82.24、S_R=100，最终分34.8。后者说明高风险结果主要由较低模型语义分拉低，而规则分仍为100；这也提示当前规则特征未必覆盖事实矛盾。

### 6.7.2证据不足与冲突案例

NEWS-EVAL-003在原运行中模型服务失败，S_L和S_E均为0，系统按规则分S_R=80输出可信新闻，真实标签为疑似谣言。该样本说明降级分支在工程上可返回结果，但仅靠表达规则无法完成事实判别。现有逐样本文件没有保存可验证的“支持与反驳证据同时有效”金标，故本章不编造冲突案例；未来需增加人工立场标注。

### 6.7.3误判案例及原因分析

NEWS-EVAL-002真实标签为存疑信息，系统预测疑似谣言，S_L=45、S_E=85.58、S_R=100，最终分56。证据质量较高并未抵消较低语义分，结果落入40～60区间。总体误差还集中于疑似谣言被判为可信新闻和高风险被判为疑似谣言，可能与四级标签映射、模板化正文、语义分尺度及规则对事实矛盾不敏感有关。由于没有独立真人风险复核，不能把全部差异简单归因于模型。

表6-15 典型案例

{case_table}

## 6.8实验结果讨论与有效性威胁

### 6.8.1主要实验结论

对RQ1，30项需求中23项通过、6项部分通过、1项未通过，系统主要功能已落地，但数据库回滚、重定向复核、Schema长文本限制和迁移一致性仍有缺口。对RQ2，受控评测集Recall@1即为1，证明指定知识可被召回，但不能外推开放新闻。对RQ3，本地证据过强导致联网触发为0，只能确认调用被避免，不能确认覆盖改善。对RQ4，5次聚焦重试修复4次，说明机制实际运行；缺少E1—E4对照，不能量化净收益。对RQ5，没有同数据基线，未回答。对RQ6，三类评分分支的自动化与故障用例符合当前公式，但模型失败的规则降级可能产生事实误判。对RQ7，多数故障和越权被安全处理，但两项实现缺口使其不能整体判为通过。对RQ8，端到端模型路径显著慢于数据库查询，当前环境平均约24.27s，其他路径见表6-14。

### 6.8.2结果适用范围

结果适用于当前Windows 10、MySQL 8.0.26、Chroma 1.5.9、DeepSeek模型别名和DashScope Embedding配置，以及80条模板化中文评测样本。数据主要验证事实核查映射后的四级风险流程，不覆盖所有新闻平台、语言、文体、实时突发事件和对抗样本。知识规模仅20条评测专用条目，不能代表生产知识库的长尾检索。

### 6.8.3实验局限性与有效性威胁

内部有效性方面，完整80样本仅有原运行与本次复现两次，第三次重复只覆盖共同子集，外部模型版本和服务波动仍可能影响分数；Mock故障与真实网络、磁盘或数据库故障也有差异。数据标签由固定映射得到且待真人复核，模板化正文和显式知识文本可能引入捷径。外部有效性方面，样本规模、来源、中文场景和知识覆盖均有限。构念有效性方面，系统分数不是概率，篇章级结论不保证每条主张正确，规则分反映表达与来源风险，契约通过不等于事实正确，相似度不等于可信度。可复现性方面，网页、搜索结果、外部模型和API响应会随时间变化；本章通过数据哈希、配置快照和原始逐样本文件降低但不能消除这些变化。

## 6.9本章小结

本章在保护现有数据和旧结果的前提下完成评测资产审计、自动化回归、需求追踪、数据质量、故障注入、安全和性能测试，并复核既有80样本实验。原运行与本次复现均完成80条处理，四分类Accuracy分别为0.4000和{_f(reproduction_by_metric.get('accuracy', {}).get('reproduction'))}，Macro-F1分别为0.3458和{_f(reproduction_by_metric.get('macro_f1', {}).get('reproduction'))}；三次运行共同4条样本的预测完全一致率仅{_pct(stability_by_metric.get('prediction_all_same_rate'))}，说明外部模型与降级路径波动不可忽略。本地检索达到满召回，但数据强对应结构限制了外推。证据契约与聚焦重试能够阻断部分不规范输出，分支评分在模型失败时保持可用，但规则降级不保证事实判断正确。数据库提交回滚与重定向目标复核是本次发现的关键未通过项。未完成的联网收益、总体基线、完整消融和验证集参数分析均已明确记录，后续应先改进数据标注与划分，再进行公平方法比较。
"""


def build_notes(project_root: Path, run_dir: Path, paper_source: Path, output_docx: Path) -> str:
    results = run_dir / "results"
    test_summary = _csv(results / "test_summary.csv")
    requirements = _csv(results / "requirements_traceability.csv")
    backend_test_count = next((row["passed"] for row in test_summary if row["test_group"] == "后端自动化测试"), "未记录")
    evaluation_test_count = next((row["passed"] for row in test_summary if row["test_group"] == "评测模块测试"), "未记录")
    frontend_test_count = next((row["passed"] for row in test_summary if row["test_group"] == "前端测试"), "未记录")
    return f"""# 第六章撰写说明

## 1. 使用的论文源文件

`{paper_source}`。该文件包含完整第1章至第5章；第6章插入第5章之后、参考文献之前。输出为`{output_docx}`，源文件未覆盖。

## 2. 现有数据集文件和字段

- `evaluation/datasets/news_eval.csv`：80条；字段含sample_id、topic_id、title、content、url、gold_label、标签来源、CFEVER记录ID、domain、relevant_knowledge_ids、评审预标注和字符数等。
- `evaluation/datasets/knowledge_base_eval.csv`：20条；字段含knowledge_id、title、content、source_url、来源数据、domain、label_scope和is_eval_only。
- DEMO与模板文件未作为正式指标样本。

## 3. 未修改数据集声明

未删除、改写、重标、重新划分或复制任何数据集样本；最终使用`audit/input_hashes_before.json`与结束哈希复核。

## 4. 已有实验内容

2026年6月24日完成80条端到端评测，使用deepseek-v4-pro、text-embedding-v4、Top-K=10、按需联网和分支式评分；旧结果保留在`evaluation/output`。

## 5. 已有实验复现结果

本次按相同命令向新目录执行；最终比较见`results/existing_experiment_reproduction.csv`。另以三次运行共同样本生成`results/stability_metrics.csv`与`results/stability_per_sample.csv`，报告预测、分数、候选集合和时延波动。外部模型版本、Prompt内容哈希、MySQL/Chroma快照未完全冻结，逐样本差异按事实保留。

## 6. 新补充实验

按实验组统计，本次新增8组：数据质量审计、自动化回归与需求验收、80样本完整复现、三次运行稳定性子集、证据仲裁运行分析、故障注入、安全测试和补充性能测试。共执行{backend_test_count}项后端测试与71个子测试、{evaluation_test_count}项评测测试、{frontend_test_count}项前端测试，并完成生产构建、Alembic检查、11项故障注入、18项安全场景、4条补充性能路径和6幅自动图件。

## 7. 未完成实验及原因

共6组：Local/Local+Web/Always-Web覆盖收益、E1—E4仲裁对照、B1—B4总体方法对照、多源证据消融、评分机制同数据消融、联网阈值/权重及Top-K=15验证集敏感性。原因是现有运行未触发联网、没有同样本基线原始预测、输出只保存Top-10且没有独立验证集；未虚构结果。

## 8. 数据质量检查结果

80条样本均嵌入对应知识正文，202对正文相似度不低于0.80，80条URL重复记录对应20个主题，标签和正文完整；无划分字段，事件跨集泄漏无法确认。

## 9. 模型和参数配置

详见`configs/experiment_environment.json`。密钥已脱敏；temperature在旧元数据中未记录。

## 10. 自动化测试结果

{'; '.join(f"{row['test_group']}={row['status']}" for row in test_summary)}。

## 11. 需求追踪结果

30项中通过{sum(row['conclusion']=='通过' for row in requirements)}项、部分通过{sum(row['conclusion']=='部分通过' for row in requirements)}项、未通过{sum(row['conclusion']=='未通过' for row in requirements)}项。完整矩阵见`results/requirements_traceability.csv`。

## 12. 基线和消融方案

现有资产未保存B1—B4和E1—E3同样本结果；正文只报告Full运行统计和缺失原因，不将单元测试结果包装为分类消融指标。

## 13. 原始结果文件

旧结果位于`evaluation/output`；本次结果位于`{run_dir / 'results'}`，复现原始目录为`results/reproduction_raw`。

## 14. 图表生成脚本

`evaluation/scripts/chapter6/generate_figures.py`从CSV自动生成6幅图，未手工填写图中数值。

## 15. 与前五章一致性检查

评分公式、风险阈值、Top-K、Embedding、模型别名和契约版本与当前代码一致；Word生成后比较前5章段落、表格、原媒体哈希和域代码数量。

## 16. 发现的前文问题

第4、5章称URL重定向逐跳校验，但默认`urlopen`自动跟随后未读取`response.geturl()`；称检测数据库写入失败会回滚，但`save_detection_record`在`commit()`异常时未显式`rollback()`；称输入有限长，实际正文Schema无最大长度，仅服务层截到12000字符。未修改前五章正文。

## 17. Word格式检查

正文五号，中文宋体，西文与数字Times New Roman；未新增分页符或分节符；表题在表上、图题在图下；原图表和目录域保留。请在Microsoft Word中右键目录，选择更新域—更新整个目录。

## 18. 仍需作者人工确认的内容

需由两名真人独立复核80条四级风险标签；需确认学校模板对表格字号、图宽和续表的具体要求；建议修复两项未通过安全/可靠性问题后重新验收，并在独立验证集上补充公平基线与消融。
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--paper-source", type=Path, required=True)
    parser.add_argument("--paper-output-dir", type=Path, required=True)
    args = parser.parse_args()
    project_root = args.project_root.resolve()
    run_dir = args.run_dir.resolve()
    output_dir = args.paper_output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    chapter = build_chapter(project_root, run_dir)
    chapter_run = run_dir / "reports" / "第六章系统测试与实验分析.md"
    chapter_run.write_text(chapter, encoding="utf-8")
    shutil.copy2(chapter_run, output_dir / chapter_run.name)
    output_docx = output_dir / "智闻辨真_第六章系统测试与实验分析完成版.docx"
    notes = build_notes(project_root, run_dir, args.paper_source.resolve(), output_docx)
    notes_run = run_dir / "reports" / "第六章撰写说明.md"
    notes_run.write_text(notes, encoding="utf-8")
    shutil.copy2(notes_run, output_dir / notes_run.name)
    print(chapter_run)
    print(notes_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
