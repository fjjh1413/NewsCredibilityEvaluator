# 已有实验复核

## 实验输入与配置

- 数据文件：`evaluation/datasets/news_eval.csv`，SHA-256为`1023663fdf1070283547799fbccd54aa215281b17407baa4c886803275732b30`。
- 样本：NEWS-EVAL-001至NEWS-EVAL-080，共80条，四类各20条。
- 模型：`deepseek-v4-pro`；Embedding：`dashscope/text-embedding-v4`。
- Prompt/契约：既有元数据未记录Prompt内容哈希；当前代码契约版本为2.0，因此不能反推原运行的Prompt文本版本。
- Top-K：10；联网允许：True，实际触发0次。
- 触发规则：{"top1_below_trigger": 0.45, "moderate_top1_below": 0.6, "min_meaningful_results": 3}。
- 评分：正常: llm_score×0.5 + evidence_quality_score×0.3 + rule_score×0.2; 无证据: llm_score×0.6 + rule_score×0.4; LLM降级: rule_score。
- 命令：`E:\nan\NewsCredibilityEvaluator\evaluation\run_evaluation.py --dataset evaluation/datasets/news_eval.csv --output-dir evaluation/output --sample-limit 0 --allow-web-search true --retries 1 --interval 1.0 --seed 42 --log-level INFO`。

## 运行与输出

- 既有结果属于一次完整运行，不是多次重复实验；80/80成功，保存了逐样本原始预测。
- Accuracy=0.4，Macro-F1=0.3458。
- 平均延迟=24271.59ms，P95=37063.3ms。
- Recall@1=1.0，MRR=1.0；该值受评测知识与主题强对应影响。
- 失败样本：端到端失败0条；报告另记约15次模型超时后降级，但逐样本`is_timeout`字段没有保存这些次数，二者存在记录口径不一致。

## 可复现性判断

输入、命令、模型别名、数据哈希和逐样本结果齐全，具备重新执行条件；但外部模型服务版本、Prompt内容哈希、MySQL/Chroma快照未冻结，因此只能检验操作可复现性，不能保证逐样本完全一致。本次复现结果见`results/existing_experiment_reproduction.csv`；如外部服务或额度阻断，将如实记录而不伪造。
