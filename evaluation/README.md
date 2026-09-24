# 可复现评测与数据发布门禁

当前有两种不同的评测对象，结果不能混用：

1. **官方 CFEVER 原始主张与页标题检索基线**：有上游人工标签/证据页标注，可复现运行；它验证封闭语料的标题词项检索，不代表本项目端到端新闻分析效果。
2. **本项目四级风险评测**：调用真实服务链路，记录检索、模型仲裁、降级和数据库阶段；四级人工标注尚待完成，默认禁止运行未合格数据。不能从 CFEVER 的三分类自动推导四级风险，更不能把模型预标注当真人复核。

## 数据与来源

- datasets/news_eval.csv：120条未改写的官方 CFEVER dev claims，supports/refutes/NOT ENOUGH INFO各40条。gold_label与本项目reviewer字段留空；upstream_label单独保留。
- datasets/sources/cfever/dev.jsonl：官方3000条dev原始文件；固定commit 01395ed4a7ab125c3e131c97d33d188159d9a1da，附官方Apache-2.0许可证。
- datasets/frozen_manifest.json：源文件、工作集与标题语料的SHA-256、选择/切分规则及局限。
- datasets/cfever_page_titles.jsonl：474个在上游dev证据中出现的页面标题，没有百科全文。
- datasets/human_review_pending.csv：没有预填答案的人工评审表；各评审者应在互不可见的副本中独立填写，再由仲裁者合并。
- datasets/quarantine/news_eval_synthetic_leaky.csv：旧80条构造样本，正文含目标标签与证据提示，保留仅用于泄漏检测回归，禁止发布分类指标。
- datasets/knowledge_base_eval.csv：旧合成场景配套知识，不能当新CFEVER子集的原始百科证据。

来源：[CFEVER官方数据仓库](https://github.com/IKMLab/CFEVER-data)、[原始dev固定版本](https://raw.githubusercontent.com/IKMLab/CFEVER-data/01395ed4a7ab125c3e131c97d33d188159d9a1da/data/dev.jsonl)、[论文](https://doi.org/10.1609/aaai.v38i17.29825)。这些是人工编写的百科事实核验主张，不是自然分布的真实新闻文章。

以共享证据页或相同主张构造连通分组；无证据页的NEI按领域保守分组，再固定哈希划分train/dev/test（当前82/22/16）。不会强行为每个split凑齐标签数。所有来源均为Wikipedia，没有实现来源域外泛化验证。不得把这里的test子集冒充官方CFEVER test/排行榜。

## 无需密钥的真实检索基线

运行：python -m evaluation.run_title_retrieval_baseline

算法固定为标题完整包含加字符bigram覆盖率，没有模型、hash embedding或黄金标签参与打分。默认先校验冻结文件哈希，再针对474个标题排序。结果在 baselines/cfever-title-v1/：

- per_case_results.jsonl：每个原始主张、官方相关页、实际Top-10与耗时；
- summary.json：按split计算Hit@K、Recall@K、MRR及可发布范围；
- failure_analysis.md：test全部未命中样本，供后续逐项分析。

首轮test共16条，其中15条有官方页证据、1条NEI不计算召回。Hit@10和Recall@10均为0.9333、MRR为0.8。样本小、只检索标题且不包含全量Wikipedia干扰文档；这些数字不能写成生产RAG召回率或LLM准确率。基线可用来检查数据/排名指标链路并发现别名问题，不是最终简历质量指标。

重新生成数据只用于维护冻结版本：python -m evaluation.scripts.build_cfever_benchmark

脚本从已固定源文件生成，不联网、不改写主张、不生成四级答案。修改选择规则或人工标注后，应保存新版本与清晰的变更记录，不能悄悄覆盖已发表实验输入。

## 四级风险评测与发布门禁

运行：python -m evaluation.run_evaluation --dataset evaluation/datasets/news_eval.csv --output-dir evaluation/output/run-001

当前工作集会在加载数据库或provider前以退出码2拒绝，并输出 dataset_quality.json。门禁要求每行有合法四级gold、两名不同的人类reviewer身份/标签、human_review_status=adjudicated、仲裁理由和原始来源ID。自动化只能检查这些字段，不能证明填表人身份或消除全部语义泄漏。

真实服务诊断可显式加 --research-only，但仍不能运行被发现输入泄漏的数据，且未合格四级gold不参加分类质量统计。服务调用需要配置数据库、Embedding和LLM供应商，可能产生调用费用；本次冻结数据和标题基线没有使用付费provider。

人工评审流程：分别向两名评审者提供原始主张、来源定位与检索到的原始证据，隐藏上游/模型建议标签；各自填写身份、标签、理由和来源；仲裁分歧并冻结新的数据版本。候选知识/片段的相关性需要单独标注，不能将页面ID直接伪装成应用内knowledge_id。

常用参数：--sample-limit、--allow-web-search true/false、--retries、--interval、--seed、--resume、--manifest、--research-only。续跑要求数据和配置指纹一致；已有结果目录不能直接复用，避免混入旧结果。

## 状态与指标

- success只表示服务调用是否返回，不代表仲裁成功。原样保存assessment_status、arbitration_status、quality_status。
- completed才表示给出完整评估；insufficient_evidence与degraded是“无法判断”，最终分为null。数量和占比单列。
- 已标注分类准确率将明确弃权计入分母，同时给出判定覆盖率和已判定样本的选择性准确率，防止通过弃权隐藏错误。
- db_save_latency_ms是数据库保存时间；report_latency_ms仅取真实报告生成计时，检测不生成报告时为空。
- AI gate CSV适配器不再把success=true写成accepted/ok，不再把候选列表前N条当成有效证据。
- 静态 ai_engineering/sample_cases.jsonl是合约回归fixtures；门禁通过不能证明模型质量。
- 历史 scripts/chapter6/保留用于旧实验材料复现；旧四级映射/合成数据结果不得绕过当前发布门禁。

## 测试

运行：python -m pytest evaluation/tests -q

同时存在unittest类与pytest函数，不能只用unittest discover报告全部测试通过。数据测试覆盖原始主张/证据逐条对应、冻结哈希、跨split证据页互斥、泄漏识别、假review拒绝、非gold发布拒绝、弃权分母、状态保真及续跑隔离。
