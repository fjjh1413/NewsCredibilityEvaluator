# 现有评估资产清单

## 1. 现有目录与文件

- `__init__.py`（57字节）
- `datasets\knowledge_base_eval.csv`（7698字节）
- `datasets\news_eval.csv`（149514字节）
- `datasets\news_eval_demo.csv`（1468字节）
- `datasets\news_eval_template.csv`（2737字节）
- `metrics.py`（18957字节）
- `output\.gitignore`（136字节）
- `output\_checkpoint.json`（1379字节）
- `output\error_analysis.md`（5116字节）
- `output\evaluation_report.md`（7699字节）
- `output\failure_cases.csv`（6535字节）
- `output\metrics.json`（4227字节）
- `output\per_case_results.csv`（20922字节）
- `output\run_metadata.json`（1276字节）
- `README.md`（5876字节）
- `report.py`（14267字节）
- `run_evaluation.py`（36554字节）
- `scripts\__init__.py`（34字节）
- `scripts\chapter6\__init__.py`（53字节）
- `scripts\chapter6\analyze_stability.py`（6936字节）
- `scripts\chapter6\audit_evaluation.py`（6338字节）
- `scripts\chapter6\build_word.py`（14421字节）
- `scripts\chapter6\compile_results.py`（21394字节）
- `scripts\chapter6\compose_chapter.py`（35571字节）
- `scripts\chapter6\finalize_reproduction.py`（6147字节）
- `scripts\chapter6\generate_audit_reports.py`（20231字节）
- `scripts\chapter6\generate_figures.py`（6674字节）
- `scripts\chapter6\run_performance_checks.py`（4960字节）
- `scripts\chapter6\run_reliability_security.py`（18554字节）
- `scripts\chapter6\verify_input_hashes.py`（2239字节）
- `tests\__init__.py`（40字节）
- `tests\test_chapter6_artifacts.py`（1442字节）
- `tests\test_chapter6_audit.py`（6228字节）
- `tests\test_chapter6_results.py`（3427字节）
- `tests\test_chapter6_word.py`（1893字节）
- `tests\test_metrics.py`（28305字节）
- `tests\test_runner.py`（11190字节）

## 2. 数据文件及实际用途

- `datasets/news_eval.csv`：`output/run_metadata.json`记录的正式评测输入；共80条，既有逐样本预测与汇总指标均由该文件产生。
- `datasets/knowledge_base_eval.csv`：20条评测专用知识，`admin_note`标识用于把`EVAL-KB-*`解析为MySQL知识ID。
- `datasets/news_eval_demo.csv`：仅用于验证评测链路，`DEMO-*`会被正式指标排除。
- `datasets/news_eval_template.csv`：评测输入字段模板，不是已标注正式样本。

## 3. 数据集规模、类别与划分

- 正式评测集：80条；知识条目：20条；主题：20个。
- 类别分布：可信20条、存疑20条、疑似谣言20条、高风险20条。
- 数据没有`split`、`validation`或`test`字段；既有命令把80条整体作为一次评测输入。可确认的独立验证集数量为0，不能从文件中确认训练/验证/测试划分。
- 80条样本均标注为“待两名真人复核”，评审列是兼容性预标注，不是两名真人独立标注。

## 4. 数据字段

`sample_id`、`topic_id`、`title`、`content`、`url`、`gold_label`、`gold_label_source`、`source_dataset`、`source_record_ids`、`domain`、`local_kb_expected`、`relevant_knowledge_ids`、`relevant_evidence_titles`、`allow_web_search`、`reviewer_1_label`、`reviewer_2_label`、`reviewer_1_provenance`、`reviewer_2_provenance`、`human_review_status`、`reviewer_notes`、`annotation_rule`、`content_char_count`

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
