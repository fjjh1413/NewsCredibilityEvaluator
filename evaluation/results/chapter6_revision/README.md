# 第六章修订实验复现说明

## 数据与边界

- 正式输入：`evaluation/datasets/news_eval.csv`，80条、20个主题、四类各20条。
- 评测知识：`evaluation/datasets/knowledge_base_eval.csv`，20条。
- 数据无独立训练/验证/测试划分；80条均待两名真人独立复核。
- 新闻正文逐字包含对应知识，主题与知识强对应，Recall@K不得外推到开放新闻流。

## 本次新增命令

```powershell
python -m evaluation.scripts.chapter6.run_revision_experiments --project-root . --output-dir evaluation/results/chapter6_revision
python -m evaluation.scripts.chapter6.run_revision_experiments --project-root . --output-dir evaluation/results/chapter6_revision --run-web --append-web --web-sample-ids NEWS-EVAL-015,NEWS-EVAL-017
python -m evaluation.scripts.chapter6.run_revision_experiments --project-root . --output-dir evaluation/results/chapter6_revision --run-retry-ablation --append-retry --retry-sample-ids NEWS-EVAL-001,NEWS-EVAL-002
python -m evaluation.scripts.chapter6.generate_revision_figures --results-dir evaluation/results/chapter6_revision
python -m pytest evaluation/tests -q
cd backend; python -m pytest tests -q
cd frontend; npm test; npm run build
```

## 评分消融

读取2026年6月24日原运行数据库中的S_L、`evidence_quality.score`、S_R和契约状态。12条`provider_error`样本在No-Rule下无剩余分量，三个方案统一使用其余68条共同子集。

- Full：沿用生产分支公式。
- No-Evidence-Quality：有证据分支按5:2重归一化；无证据与模型失败分支不变。
- No-Rule：有证据分支按5:3重归一化；无证据分支只用S_L；模型失败样本不可计算。
- Use-All-Candidates：跳过仲裁，将全部候选作为有效证据，复用同次LLM分和证据质量分并重新计算规则分。

`ablation_predictions.csv`保存逐样本重算，`ablation_metrics.csv`保存总体与各类指标，`ablation_paired_statistics.csv`保存5000次配对Bootstrap区间和McNemar精确检验。Full重算与数据库保存分的最大绝对差为0。

## 前瞻式无聚焦重试对照

对全80条样本（20个主题各4条、四类各20条）执行真实本地检索和模型分析，同时捕获首次输出与可能的聚焦重试输出，数据库写入替换为内存对象。68条首次契约有效，9条为提供方异常，3条因候选ID未完整覆盖触发聚焦重试并全部修复。Full与No-Focused-Retry的Accuracy均为0.3000，Macro-F1均为0.2426；三条最终分发生变化，但风险标签均未变。

## 参数敏感性

- Top-1联网阈值：对0.45、0.60、0.75、0.80、0.85、0.90仅根据80条已保存相似度统计反事实触发数，不调用联网服务。
- 证据质量权重：在68条共同子集将权重设为0至0.50，剩余权重保持LLM:规则=5:2，离线重算Accuracy与Macro-F1。
- 风险分界点：对40/60/80同向平移-5、0、+5分，并统计分界点±2/±5分内的样本数。

这些结果仅用于识别高敏感参数，没有独立验证集，不用于选择“最优”配置。

## 隔离低覆盖联网实验

样本共12条，四类风险各3条，覆盖T01—T12多个主题。进程内将本地检索替换为空列表，使相同样本分别执行Local-only与Local+Web；数据库保存替换为内存对象，正式MySQL和Chroma未修改。搜索和模型调用使用当前真实配置。

原始结果位于`web_low_coverage_raw/`，汇总位于`web_low_coverage_summary.csv`。12次Local+Web均触发联网并返回60条候选；10条网络证据通过仲裁，4次模型分析超时并走`provider_error`降级。配对统计见`web_low_coverage_paired_statistics.csv`。

## 文件说明

- `ablation_predictions.csv`、`ablation_metrics.csv`：评分消融原始与汇总。
- `ablation_paired_statistics.csv`：消融配对Bootstrap区间与McNemar精确检验。
- `web_low_coverage_raw/`、`web_low_coverage_summary.csv`：低覆盖联网逐样本原始输出与汇总。
- `web_low_coverage_metrics.csv`、`web_low_coverage_paired_statistics.csv`：联网策略汇总与配对不确定性。
- `retry_ablation_raw/`、`retry_ablation_summary.csv`：重试对照原始载荷与逐样本汇总。
- `retry_ablation_metrics.csv`、`retry_ablation_paired_statistics.csv`：Full/No-Focused-Retry指标与配对统计。
- `web_trigger_threshold_sensitivity.csv`：Top-1阈值反事实触发计数。
- `evidence_quality_weight_sensitivity_*.csv`：证据质量权重逐样本结果与汇总。
- `risk_threshold_sensitivity_*.csv`、`risk_threshold_proximity.csv`：风险分界点平移与邻域样本统计。
- `performance_stage_summary.csv`：隔离实验阶段耗时。
- `classification_metrics.csv`、`confusion_matrix.csv`：正式80条分类结果。
- `retrieval_metrics.csv`：Recall@1/3/5/10与MRR。
- `arbitration_metrics.csv`：契约、重试和修复统计。
- `fault_injection_results.csv`、`security_test_results.csv`：故障与安全结果。
- `configs/`、`audit/`、`logs/`：配置、审计与执行日志。
- `figures/`：12幅300dpi以上PNG及清单。
- `human_review_sheet.csv`、`human_review_protocol.md`：双人独立复核空白表与操作协议；评审列未代填。

## 不可复现因素

外部搜索结果、网页、模型别名背后的服务版本和API响应会变化；旧运行未冻结Prompt内容哈希、MySQL与Chroma完整快照。所有差异应如实保留，不要求逐字一致。
