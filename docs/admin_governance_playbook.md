# 后台治理与 AI 工程化说明

## 目标

“智闻辨真”不是只做一个新闻可信度 Demo，而是一个可放进简历的 AI 应用工程项目。后台治理的目标是证明系统具备以下能力：

- 管理员可以闭环处理用户、检测记录、报告、知识库、Prompt 和高风险新闻。
- 关键操作有结构化审计，能够按请求、目标对象和结果状态追踪。
- AI 链路有离线质量门禁，能够用指标证明模型输出、RAG 召回和降级行为。
- 高风险后台动作有明确策略清单和演进路线，而不是散落在代码里的隐性规则。

## 四个优先级落地情况

| 优先级 | 落地内容 | 价值 |
| --- | --- | --- |
| P1 报告和角色闭环 | 增加后台报告删除 API、服务清理逻辑、前端删除确认；补齐用户角色调整前端入口 | 后台管理不再只有查看，具备治理动作闭环 |
| P2 结构化审计 | 扩展系统日志字段：`request_id`、`target_type`、`target_id`、`result_status`、`metadata_json`；关键后台动作写入目标对象和结果 | 操作可以按“谁在什么时候对哪个对象做了什么，结果如何”追踪 |
| P3 AI 工程质量 | 增加 `/api/admin/ai-engineering/summary` 和后台 “AI 工程质量” 页面，展示离线评测门禁、RAG 指标、降级率、P95 延迟和 case 明细 | 把 AI 能力从“能调用模型”升级为“可评估、可回归、可上线” |
| P4 高风险操作策略 | 增加 `/api/admin/operation-policies` 和后台 “操作策略” 页面，列出风险等级、审计字段、当前强制项、下一步控制和回滚提示 | 把后台治理显性化，形成可展示的工程管理面 |

## 高风险操作分级

| 操作 | 风险等级 | 当前强制项 | 下一步演进 |
| --- | --- | --- | --- |
| 知识库重建向量索引 | Critical | 管理员权限、结构化审计、结果元数据 | 双人复核、索引快照、回滚到上一版本索引 |
| 切换默认 Prompt | Critical | 管理员权限、Prompt 校验、结构化审计 | 评测证据审批、AI 质量门禁、恢复上一默认模板 |
| 用户角色调整 | Critical | 管理员权限、最后管理员保护、自我降权保护、结构化审计 | 权限提升双人复核、会话重认证、角色变更通知 |
| 删除报告 | High | 管理员权限、前端确认、结构化审计、检测记录链接清理 | 软删除留存、删除原因、文件隔离后清理 |
| 删除检测记录 | High | 管理员权限、结构化审计 | 前端确认、软删除留存、删除原因 |
| 删除知识库条目 | High | 管理员权限、向量同步保护、结构化审计 | 软删除恢复、知识差异预览、RAG 回归 case |
| 删除 Prompt 模板 | High | 管理员权限、默认模板删除保护、结构化审计 | 模板归档、删除原因、按版本恢复 |
| 禁用用户 | High | 管理员权限、最后管理员保护、自我操作保护、结构化审计 | 禁用原因、会话吊销、用户通知 |
| 高风险结果审核 | Medium | 管理员权限、结构化审计 | 审核备注质量检查、审核工作量指标 |
| 高风险结果公开状态调整 | High | 管理员权限、结构化审计 | 前端确认、原因记录、公开变更通知 |

## 审计字段标准

关键操作应至少写入：

- `request_id`：关联一次请求链路。
- `user_id`：操作者。
- `module` / `action`：业务模块和动作。
- `target_type` / `target_id`：被操作对象。
- `result_status`：`success`、`failure`、`blocked` 等结果。
- `metadata_json`：必要上下文，必须脱敏并限制大小。
- `ip_address` / `created_at`：来源和时间。

当前系统已在注册、登录、检测、报告删除、用户启停/角色调整、检测删除、高风险审核、知识库、Prompt 管理等入口写入结构化上下文。

## AI 工程质量门禁

离线评测入口：

```bash
python -m unittest evaluation.tests.test_ai_engineering_metrics evaluation.tests.test_ai_engineering_runner
```

默认 smoke gate：

```bash
python -m evaluation.ai_engineering.runner \
  --cases evaluation/ai_engineering/sample_cases.jsonl \
  --output .artifacts/ai_eval/summary.json
```

后台展示入口：

- `GET /api/admin/ai-engineering/summary`
- 前端路由：`/admin/ai-engineering`

核心指标：

- 契约有效率：模型输出字段和取值范围是否稳定。
- 风险等级准确率：预测风险是否匹配期望。
- RAG Recall / Precision / MRR：检索是否召回关键证据，且排序靠前。
- 降级率：解析失败、供应商错误、超时、显式降级等异常占比。
- P95 延迟：离线捕获输出的端到端耗时。

## 后台治理 API

| 能力 | Endpoint |
| --- | --- |
| AI 工程质量摘要 | `GET /api/admin/ai-engineering/summary` |
| 高风险操作策略 | `GET /api/admin/operation-policies` |
| 按风险等级筛选策略 | `GET /api/admin/operation-policies?risk_level=critical` |
| 报告删除 | `DELETE /api/admin/reports/{report_id}` |
| 用户角色调整 | `POST /api/admin/users/{user_id}/role` |
| 结构化审计筛选 | `GET /api/admin/logs?request_id=&target_type=&target_id=&result_status=` |

## 简历表达建议

可写成：

> 智闻辨真：面向新闻可信度判断的 AI 应用工程项目。负责后台治理与 AI 工程化建设，补齐报告删除、角色调整、结构化审计、高风险操作策略和离线质量门禁；设计 RAG/模型输出评测指标，提供后台可视化页面展示风险准确率、RAG 召回、降级率和 P95 延迟，使系统从模型调用 Demo 升级为可治理、可回归、可观测的 AI 应用。

可拆成面试讲点：

- 后台治理：围绕高风险操作建立权限、确认、审计、回滚提示和演进策略。
- 审计可观测：用 `request_id + target_type + target_id + result_status` 支撑问题追踪。
- AI 质量工程：离线评测不调用模型服务，适合 CI 和合并前回归。
- RAG 工程化：用 Recall、Precision、MRR、命中率和延迟而不是主观感受评价检索质量。
- 风险意识：明确当前仍是管理员二元权限，细粒度 RBAC、双人复核、会话吊销和防篡改留存是下一阶段。

## 后续演进路线

1. 细粒度 RBAC：把 `admin/user` 扩展为角色、权限点和资源范围。
2. 双人复核：Critical 操作先创建 approval request，再由另一名管理员批准执行。
3. 软删除与留存：报告、检测、知识库、Prompt 默认进入可恢复状态，再按策略清理。
4. 会话安全：角色变更、禁用用户、密码重置后吊销活跃会话。
5. 审计防篡改：日志追加哈希链、定期归档、导出校验。
6. 发布门禁：把 AI 工程质量 gate 接入 CI，阻断风险准确率或 RAG 召回退化的变更。
