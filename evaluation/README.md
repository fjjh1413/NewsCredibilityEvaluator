# 新闻可信度评测工具

可复现的离线评测工具，用于评估"智闻辨真"新闻可信度检测系统的真实效果。

## 设计原则

1. **不修改业务逻辑**：评测脚本直接调用 `detect_news_credibility` 服务层函数，不复制或修改任何评分公式、Prompt、检索阈值、风险分类规则或联网触发条件。
2. **可复现**：固定随机种子、记录完整运行元数据（Commit Hash、模型名、参数）、数据集文件哈希。
3. **安全**：所有输出（CSV、JSON、Markdown）中不包含 API 密钥、Token 或用户隐私数据。
4. **可追溯**：每一个汇总指标都可以追溯到 `per_case_results.csv` 中的逐样本结果。

## 目录结构

```
evaluation/
├── datasets/
│   ├── news_eval_template.csv   # 测试集字段模板和填写说明
│   └── news_eval_demo.csv       # 3-5 个 DEMO 样本（仅用于验证链路）
├── output/                      # 评测输出目录（git-ignored）
│   ├── per_case_results.csv     # 逐样本结果
│   ├── metrics.json             # 汇总指标
│   ├── evaluation_report.md     # 可读报告
│   ├── run_metadata.json        # 运行元数据
│   └── _checkpoint.json         # 断点续跑状态
├── tests/
│   ├── test_metrics.py          # 指标计算单元测试
│   └── test_runner.py           # 执行器、加载、脱敏测试
├── __init__.py
├── run_evaluation.py            # 评测入口
├── metrics.py                   # 指标计算
├── report.py                    # 报告生成
└── README.md                    # 本文件
```

## 快速开始

### 1. 准备测试数据

```bash
# 使用 DEMO 数据集验证链路（无需人工标注）
cp evaluation/datasets/news_eval_demo.csv evaluation/datasets/my_eval.csv
```

正式评测前，请按照 `news_eval_template.csv` 中的字段说明填写真实测试数据。

### 2. 运行评测

```bash
# 从项目根目录运行（推荐）
python -m evaluation.run_evaluation \
    --dataset evaluation/datasets/news_eval_demo.csv \
    --output-dir evaluation/output \
    --sample-limit 3 \
    --allow-web-search false \
    --retries 1 \
    --interval 0.5 \
    --seed 42
```

也可从 `backend/` 目录运行：

```bash
cd backend
python -m evaluation.run_evaluation \
    --dataset ../evaluation/datasets/news_eval_demo.csv \
    --output-dir ../evaluation/output \
    --sample-limit 3
```

### 3. 查看结果

```bash
# 逐样本结果
cat evaluation/output/per_case_results.csv

# 汇总指标
cat evaluation/output/metrics.json

# 可读报告
cat evaluation/output/evaluation_report.md
```

## CLI 参数

| 参数 | 说明 | 默认值 |
|---|---|---|
| `--dataset` | 测试集路径（CSV 或 JSONL） | 必填 |
| `--output-dir` | 输出目录 | `./evaluation/output` |
| `--sample-limit` | 最大评测样本数（0=全部） | 0 |
| `--allow-web-search` | 强制允许/禁止联网检索（true/false） | 按样本列 |
| `--retries` | 失败重试次数 | 1 |
| `--interval` | 样本间最小间隔（秒） | 0.5 |
| `--seed` | 固定随机种子 | 42 |
| `--resume` | 从上次中断处续跑 | false |
| `--log-level` | 日志级别 | INFO |

## 评测指标

### 1. 样本统计
总样本数、有效样本数、成功/失败数、各真实/预测标签数量。

### 2. 响应时间
平均、P50、P95、最大延迟；分阶段耗时（当前版本仅记录总延迟，分阶段延迟未单独计时）。

### 3. 联网检索触发率
`web_search_triggered_count / web_search_allowed_count`；按触发原因分组统计。

### 4. 本地召回效果
当 `relevant_knowledge_ids` 存在时计算 Hit@K、Recall@K、MRR。无标注时不会生成虚假 Recall。

### 5. 分类效果
当 `gold_label` 完整时计算 Accuracy、Macro Precision/Recall/F1、各类别指标、混淆矩阵。

### 6. 人工评审一致性
当两名评审者均完成标注时计算原始一致率和 Cohen's Kappa。仅一名评审时不输出 Kappa。

### 7. 证据引用完整率
有效证据比例、字段完整率、URL 有效性、证据不足提示比例、有结论无证据的样本数。

### 8. 稳定性
整体成功率、超时率、LLM 解析失败率、降级解析使用率等。

## 运行测试

```bash
# 运行评测模块的所有测试
python -m unittest discover -s evaluation/tests -p "test_*.py"

# 运行单个测试文件
python -m unittest evaluation.tests.test_metrics
python -m unittest evaluation.tests.test_runner
```

## 正式评测前准备清单

1. [ ] 准备真实测试数据集（人工标注 `gold_label`）；
2. [ ] 标注 `relevant_knowledge_ids`（如需要计算 Hit@K/Recall@K）；
3. [ ] 确保 `DEEPSEEK_API_KEY` 已配置且余额充足；
4. [ ] 评估 API 调用次数（每样本约 1-2 次 LLM 调用 + 可能 1 次联网检索）；
5. [ ] 评估成本（DeepSeek 约 ¥0.001/1K tokens，每样本预估 3-5K tokens）；
6. [ ] 安排至少两名评审者独立标注（如需要计算 Cohen's Kappa）；
7. [ ] 确认后端服务可访问（数据库、Chroma、DeepSeek API）。

## 已知限制

1. **分阶段延迟不可用**：当前 `detect_news_credibility` 未暴露各子阶段的独立计时，`parse_latency_ms`、`llm_latency_ms` 等字段在 `per_case_results.csv` 中为空值。
2. **联网触发原因不可用**：`should_trigger_web_search` 返回布尔值但不返回原因字符串，`web_trigger_reason` 字段为空。
3. **需要数据库连接**：评测脚本直接调用服务层，依赖 MySQL 和 Chroma 数据库。
4. **DEMO 样本不参与统计**：`sample_id` 以 `DEMO-` 开头的样本在正式统计中自动排除。
5. **未修改业务逻辑**：评测结果反映的是当前系统的真实表现，评测工具不会"美化"任何指标。
