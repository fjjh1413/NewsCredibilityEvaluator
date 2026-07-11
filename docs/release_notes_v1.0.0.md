# Release Notes: v1.0.0

发布日期：2026-07-11

## 概览

v1.0.0 是“智闻辨真”从课程展示型系统走向可复现、可观测、可维护工程版本的首个稳定发布。该版本保留新闻可信度检测、RAG 检索、LLM 分析、规则评分、报告生成和管理员后台，同时补齐了 AI 工程化、工程化 RAG、证据仲裁质量控制、知识索引任务化和发布仓库清理。

## 主要能力

- 完整新闻可信度检测链路：标题/正文输入、知识库检索、必要时联网补证、LLM 分析、规则评分、风险分级、检测历史和 PDF 报告。
- 工程化 RAG：v2 chunk 索引、dense + lexical 混合召回、RRF 融合、父文档聚合、MMR 去重、rerank、索引一致性审计和 query-aware evidence compression。
- 证据仲裁优化：候选证据中立随机排序、`candidate_id` 引用约束、后端仲裁结果校验、质量指标和异常仲裁识别。
- 知识索引 outbox/job 模式：`knowledge_index_jobs` 统一承接自动抓取、管理员导入和重建索引任务，避免运行路径绕过 v2 chunk 索引。
- AI 工程化后台：检测链路指标、阶段耗时、策略治理、系统日志和工程化评估入口。
- 管理后台：知识库、Prompt、报告、高风险新闻、用户、系统日志和运营策略管理。
- 评估体系：AI 工程化指标、RAG 评估、证据仲裁质量、页面识别和索引审计测试覆盖。

## 仓库清理

- 从 Git 跟踪中移除 `.codex_work/`、`backend/tmp*/`、`evaluation/results/` 等可再生产物。
- `.gitignore` 覆盖本地 Chroma、报告、临时向量库、评估输出和工作缓存。
- 本地 ignored artifacts 已物理删除；发布包只保留源码、迁移、测试、评估脚本和文档。

## 数据库与迁移

- Alembic head 包含 `knowledge_index_jobs` 和系统日志审计上下文字段扩展。
- 发布前应执行：

```powershell
cd E:\nan\NewsCredibilityEvaluator\backend
alembic upgrade head
```

## 快速验证

```powershell
cd E:\nan\NewsCredibilityEvaluator\backend
python -m unittest discover -s tests -p "test_*.py"

cd E:\nan\NewsCredibilityEvaluator
python -m unittest discover -s evaluation/tests -p "test_*.py"

cd E:\nan\NewsCredibilityEvaluator\frontend
npm run build
```

## 不包含内容

v1.0.0 不包含本地运行时数据和生成产物：

- `.codex_work/`
- `backend/tmp*/`
- `backend/chroma_db/`
- `data/chroma/`
- `data/reports/`
- `evaluation/results/`

这些目录均可由 seed、检测、报告生成或评估命令重新生成。
