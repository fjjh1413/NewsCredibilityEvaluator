# P0 基线固化状态

记录日期：2026-08-13

## 已完成

- Agent Trace v1 采用增量 API 契约，旧 `agent_steps` 保持兼容。
- 标准轨迹样例由后端 Pydantic 模型自动校验：`docs/agent_trace_v1_example.json`。
- 建立 20 条 Agent 路径目录，覆盖检索、联网路由、仲裁、评分和历史兼容：`evaluation/datasets/agent_trace_v1_scenarios.json`。
- 用户详情、管理员详情和历史重评共用同一 `analysis_payload` 解析入口。
- 详情字段采用显式白名单恢复；内部阶段耗时等字段不会自动暴露给客户端。
- 用户端和管理员端报告下载共用 PDF 响应及错误映射；所有权和管理员权限仍由原服务层校验。
- 市场访谈问题、记录模板和决策门槛已经固化：`docs/p0_market_interview_guide.md`。

## 质量基线

本次 P0 门禁结果：

- 后端：525 个测试通过。
- Evaluation：117 个测试通过。
- 前端：16 个测试通过。
- Vite 生产构建通过，共转换 1694 个模块。
- Python 编译检查与 `git diff --check` 通过。
- Starlette TestClient 已切换到 `httpx2==2.10.0`，测试依赖与生产依赖分离。
- HTTP 422 常量已迁移到 `HTTP_422_UNPROCESSABLE_CONTENT`，接口状态码仍为 422。
- SQLite 测试写入显式声明 `DateTime` 参数类型，不再依赖 Python 默认 datetime adapter。
- 内存 SQLite 测试 engine 均注册显式清理；Python 3.14 强制 GC 验证不再出现未关闭连接。

2026-08-13 警告清理复验：Python 3.14 下后端 525 个测试全部通过，Starlette TestClient/HTTP 422、SQLite datetime adapter 和 PDF 阶段暴露的未关闭 SQLite 连接三类目标警告均为 0。测试套件仍有少量与 `urllib.error.HTTPError` 临时对象隐式清理有关的 `ResourceWarning`，不涉及数据库连接，留待独立清理。

## 尚未完成且不能伪造

真实市场访谈尚未执行。P0 的工程基线已完成，但市场验证只有在至少完成 5 次访谈、覆盖至少 2 类角色并记录真实工作流后才能关闭。

进入 P1 前建议至少获得以下证据：

- 3 位受访者独立提到证据收集、来源比较或审计留痕耗时。
- 至少 2 位受访者提供单次耗时或每周处理量。
- 明确错误放行、错误拦截和处理过慢三者的相对成本。
- 明确哪些内容不允许发送到外部模型或搜索服务。

## 下一阶段入口条件

工程上可以开始 P1 的状态节点拆分，但不应将尚未完成的访谈包装成已验证市场。P1 应以现有 20 条路径目录作为行为清单，并保持当前 525/117/16 测试基线不下降。
