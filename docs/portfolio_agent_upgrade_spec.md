# 求职项目最后工程把关与 Agent 升级规格

## 1. Objective

把“智闻辨真”从功能完整的 RAG 新闻可信度系统，收敛为一个面试官能在 5–10 分钟内理解并验证的“可审计证据调查 Agent”。第一阶段不更换现有 DeepSeek、DashScope、Chroma、FastAPI 或 Vue 技术栈，不引入新的 Agent 框架，而是把现有的检索、联网补证、LLM 仲裁、重试、降级、规则评分和持久化显式建模为可追踪的 Agent 执行轨迹。

目标用户：

- 个人用户：快速判断待核查新闻，并理解“系统为何这样判断”。
- 内容审核或风控团队：获得可追溯的证据候选、排除理由和降级状态。
- 招聘方：验证候选人掌握工具编排、结构化输出、RAG、可观测性、容错和评测，而不只是调用一次模型。

成功不是宣称“自动鉴定真假”，而是提供有证据边界的辅助核查结论。

## 2. Market judgement

### 2.1 结论

问题有市场，但“面向所有人的通用 AI 辟谣网站”缺少清晰付费动机，也会直接与媒体、平台和官方核查渠道竞争。更可行的切入点是 B2B/B2G 的内容风险预筛：面向内容平台、品牌公关、校园媒体或企业舆情团队，把人工核查前的证据收集、候选排序和审计报告自动化。

当前产品的优势是证据链、混合检索、联网补证和离线评测；弱点是结论责任边界、真实数据证明、来源权威度建模以及用户工作流集成不足。因此求职展示应强调“调查 Agent 工程能力”，不应包装成已经验证商业化的事实核查平台。

### 2.2 可验证的市场信号

- 世界经济论坛《Global Risks Report 2025》仍把错误与虚假信息列为主要短期风险之一。
- Reuters Institute《Digital News Report 2025》显示，用户核验信息时仍优先依赖可信新闻品牌和官方来源；这意味着来源质量和可解释证据比单一模型分数更重要。
- C2PA Content Credentials 已形成数字内容来源与历史的开放技术标准，说明“内容来源证明 + 事实证据核查”会是互补能力。

### 2.3 推荐产品定位

一句话：**为内容风控团队提供可审计、可降级、可人工复核的新闻证据调查 Agent。**

首个可售卖场景：批量输入文章或链接，Agent 自动拆解主张、检索本地与联网证据、标记矛盾和证据缺口，输出待人工复核队列与报告。衡量价值的指标应是人工核查耗时下降、Top-K 证据召回、错误放行率和需要升级人工的比例，而不是页面访问量。

## 3. Current stack and commands

- Backend: Python, FastAPI 0.139.0, SQLAlchemy 2.0.31, Pydantic, Celery 5.6.3.
- Frontend: Vue 3.5, Vite 6, Element Plus, Pinia, ECharts.
- Retrieval: Chroma 1.x, DashScope embedding, dense + lexical + RRF + MMR + rerank.
- Model and search: DeepSeek structured analysis, Bocha web search.
- Operations: MySQL, Redis, OpenTelemetry, Prometheus, Pyroscope, Docker Compose.

Commands from repository root:

```powershell
python -m unittest discover -s backend/tests -t backend -p "test_*.py"
python -m unittest discover -s evaluation/tests -p "test_*.py"
npm --prefix frontend test
npm --prefix frontend run build
git diff --check
```

## 4. Redundancy and complexity audit

### 4.1 Confirmed hotspots

- `backend/app/services/detection_service.py::detect_news_credibility` has about 337 lines, cyclomatic complexity 22 and cognitive complexity 42. It owns input cleaning, claim extraction, RAG, web routing, model calls, arbitration retry, scoring, persistence and telemetry. This is the primary maintainability risk.
- `validate_and_apply_llm_ranking` and `merge_evidence` are also high-complexity boundaries. They should be refactored only with characterization tests because they protect evidence correctness.
- `WebContentFetcher` contains several high-complexity extraction methods. This complexity is partly inherent to hostile HTML and SSRF-safe redirects; it is not dead code.

### 4.2 Confirmed duplication

- User and admin report-download route handlers have effectively identical file-response and exception-mapping logic. A shared private response helper can remove duplication without merging authorization policies.
- Statistics trend and user-activity functions duplicate date-range expansion and zero filling. This is small, readable duplication and lower priority than the detection orchestration.
- Multiple thesis/document generation scripts repeat Word styling helpers (`set_cell_margins`, `set_run_font`, borders, metadata). They should be moved to a separate documentation-tooling package or archived after graduation delivery; they are not runtime product code.
- Detection analysis-payload parsing and field restoration are separately implemented in user and admin detail APIs, and their restored field lists have already drifted. This is a real correctness/maintenance duplication and should be consolidated in a later refactor slice.

### 4.3 Not safe to delete

- RAG v1/v2/hybrid paths are rollback and migration mechanisms. Delete only after v2 metrics pass and stored indexes are migrated.
- snake_case/camelCase/legacy aliases in the frontend are compatibility readers for cached and historical records.
- Celery, Redis and observability code is optional at runtime but demonstrates production engineering and is exercised by tests.
- Evaluation and thesis material is not part of the runtime, but it supplies reproducibility evidence. Move or archive it; do not silently delete it.

No tracked `dist`, `node_modules`, `evaluation/results`, `evaluation/runs` or backup directories were found. The untracked `.claude/` directory belongs to the user and is untouched.

## 5. First implementation slice: Agent run trace v1

### Contract

Add an optional, additive `agent_trace` object while preserving `agent_steps: list[str]`.

```json
{
  "version": "1.0",
  "agent_name": "evidence-investigation-agent",
  "status": "completed | degraded | failed",
  "total_latency_ms": 1234.5,
  "stages": [
    {
      "id": "retrieve_local_evidence",
      "title": "检索本地证据",
      "kind": "tool",
      "tool": "chroma_hybrid_search",
      "status": "completed | skipped | degraded | failed",
      "latency_ms": 42.1,
      "decision": "始终先搜索本地知识库，建立可复用证据基线。",
      "summary": "召回 10 条候选证据，使用 3 个查询。",
      "metrics": {"candidate_count": 10, "query_count": 3}
    }
  ]
}
```

边界：轨迹只保存低敏摘要、计数、状态和耗时，不保存完整 prompt、正文、密钥、工具原始参数或模型隐藏推理。

### Acceptance criteria

- 旧客户端继续读取 `agent_steps`；新客户端优先读取 `agent_trace.stages`。
- 联网未触发时显示 `skipped` 及路由理由；触发时显示工具和来源数量。
- 仲裁重试、模型降级和无证据状态均显式可见。
- 每个已执行阶段显示耗时；轨迹总耗时为已记录阶段耗时之和。
- 同步检测返回轨迹，历史详情能够从 `analysis_payload` 恢复轨迹。
- 后端单元测试、API 测试、前端归一化测试和生产构建通过。

## 6. Roadmap after v1

1. **显式状态图与耐久执行**：把 337 行主函数拆为声明提取、检索路由、证据仲裁、评分和持久化节点；先抽取纯节点，再评估 LangGraph、Dapr/Temporal/DBOS 等耐久运行时。不要为了简历关键词先引框架。
2. **Human-in-the-loop**：在高风险、低证据覆盖、来源冲突或仲裁重试耗尽时进入人工复核队列，支持批准、修订证据和恢复执行。
3. **来源与内容溯源**：建立来源权威度、时效性、独立性特征；对图片或视频输入增加 C2PA Content Credentials 验证，明确“来源真实性”和“事实真实性”的区别。
4. **Agent/RAG 评测闭环**：新增轨迹级指标（工具路由准确率、重试恢复率、人工升级精确率、成本/延迟预算）和逐主张 evidence precision/recall；把回归门禁放入 CI。
5. **流式进度与回放**：用 SSE 输出阶段事件，结果页支持一次运行的轨迹回放；OpenTelemetry 采用 GenAI 语义字段，但默认不记录敏感内容。
6. **开放工具协议**：把知识库搜索、网页核验和报告生成封装为稳定工具契约；在确有外部 Agent 消费方时再提供 MCP server，而不是仅为“用了 MCP”增加空壳。

P1 的已接受实施规格见 `docs/p1_explicit_agent_state_graph_spec.md`，架构取舍见 `docs/decisions/ADR-001-explicit-agent-state-graph.md`。

## 7. Boundaries

- Always: 对外部搜索和模型输出做结构校验；保留证据来源；测试兼容与降级路径；不记录敏感 prompt 内容。
- Ask first: 新增付费服务、替换模型提供商、数据库迁移、删除 RAG v1 或 thesis/evaluation 资产。
- Never: 把模型分数描述为事实真相；提交 API key；让未仲裁证据参与最终评分；为了多 Agent 标签把确定性步骤拆成多个模型调用。

## 8. Official references

- OpenAI Agents SDK: tracing, tools, guardrails and human approval patterns: https://openai.github.io/openai-agents-python/
- LangGraph: durable execution, interrupts and stateful workflows: https://docs.langchain.com/oss/python/langgraph/overview
- OpenTelemetry GenAI semantic attributes: https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/
- C2PA specifications: https://spec.c2pa.org/specifications/specifications/2.2/index.html
- Reuters Institute Digital News Report 2025: https://reutersinstitute.politics.ox.ac.uk/digital-news-report/2025
- World Economic Forum Global Risks Report 2025: https://www.weforum.org/publications/global-risks-report-2025/
