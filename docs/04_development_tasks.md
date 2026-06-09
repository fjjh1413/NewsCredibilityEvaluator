# 04 Codex 辅助开发任务清单

# 智闻辨真：开发任务拆解与 Codex 使用指南

> 本文档用于指导后续使用 Codex 分阶段开发项目。  
> 先阅读 `docs/01_project_design.md`、`docs/02_database_design.md` 和 `docs/03_api_design.md`，再按照本文档逐项开发。  
> 不要一次性生成完整系统，应坚持“小任务、分阶段、可运行、可测试”的开发方式。

---

## 1. Codex 使用总原则

使用 Codex 辅助开发时，你的角色是：

```text
项目负责人 / 项目审核员 / 功能验收人
```

Codex 的角色是：

```text
辅助开发工程师 / 代码实现助手 / Bug 修复助手 / 代码审查助手
```

不要让 Codex 完全接管项目。  
你需要每一步都检查它改了什么、能不能运行、是否符合设计文档。

---

## 2. 每次让 Codex 开发前必须附加的约束

每次发任务时，建议都加上下面这段：

```text
请严格按照以下要求执行：

1. 本次只完成当前任务，不要扩展无关功能；
2. 修改前先说明你准备修改哪些文件；
3. 修改后说明每个文件的作用；
4. 不要删除已有功能；
5. 不要随意更改接口路径和数据库字段；
6. 如果需要新增依赖，请说明原因和安装命令；
7. 完成后给出运行方式和测试方法；
8. 如果存在风险或未完成内容，请明确说明；
9. 优先保证代码可运行、可测试、结构清晰；
10. 所有实现必须参考 docs 目录中的设计文档。
```

---

## 3. 推荐项目目录结构

建议项目整体结构如下：

```text
zhiyun-bianzhen/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── auth.py
│   │   │   ├── detect.py
│   │   │   ├── rag.py
│   │   │   ├── report.py
│   │   │   ├── high_risk.py
│   │   │   └── admin/
│   │   │       ├── users.py
│   │   │       ├── knowledge.py
│   │   │       ├── prompts.py
│   │   │       ├── detections.py
│   │   │       ├── statistics.py
│   │   │       ├── reports.py
│   │   │       └── logs.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── security.py
│   │   │   └── response.py
│   │   ├── crud/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   │   ├── chroma_service.py
│   │   │   ├── llm_service.py
│   │   │   ├── detect_service.py
│   │   │   ├── score_service.py
│   │   │   ├── report_service.py
│   │   │   └── agent_service.py
│   │   ├── utils/
│   │   ├── main.py
│   │   └── database.py
│   ├── requirements.txt
│   ├── .env.example
│   └── README.md
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── router/
│   │   ├── stores/
│   │   ├── views/
│   │   │   ├── user/
│   │   │   └── admin/
│   │   ├── components/
│   │   ├── utils/
│   │   ├── App.vue
│   │   └── main.js
│   ├── package.json
│   └── README.md
├── docs/
│   ├── 01_project_design.md
│   ├── 02_database_design.md
│   ├── 03_api_design.md
│   └── 04_development_tasks.md
└── README.md
```

---

## 4. 开发阶段总览

建议按照以下阶段开发：

| 阶段 | 目标 | 结果 |
|---|---|---|
| 第 1 阶段 | 搭建后端基础框架 | FastAPI 能启动，Swagger 可访问 |
| 第 2 阶段 | 实现用户认证 | 注册、登录、JWT、角色区分 |
| 第 3 阶段 | 实现数据库模型 | MySQL 表结构和 SQLAlchemy Model |
| 第 4 阶段 | 实现知识库管理 | 管理员可维护知识库 |
| 第 5 阶段 | 接入 Chroma | 支持向量化和 Top10 检索 |
| 第 6 阶段 | 接入 DeepSeek | 支持大模型分析 |
| 第 7 阶段 | 实现新闻检测主流程 | RAG + 评分 + 结果保存 |
| 第 8 阶段 | 实现报告生成 | HTML / PDF 报告下载 |
| 第 9 阶段 | 实现用户端前端 | 检测、结果、历史、高风险展示 |
| 第 10 阶段 | 实现管理员后台 | 知识库、Prompt、统计、用户管理 |
| 第 11 阶段 | 优化演示效果 | 图表、美化、示例数据、答辩流程 |

---

## 5. 第 1 阶段：搭建后端基础框架

### 5.1 目标

建立 FastAPI 后端基础结构，确保项目可以正常启动。

### 5.2 Codex 任务提示词

```text
请基于 FastAPI 搭建后端基础项目结构。

要求：
1. 使用分层结构：api、core、models、schemas、services、crud、utils；
2. 配置 MySQL 数据库连接；
3. 配置 SQLAlchemy；
4. 配置 JWT 基础认证文件，但本阶段不实现登录注册；
5. 提供 FastAPI Swagger 文档；
6. 创建健康检查接口 GET /api/health；
7. 不要实现业务功能，只搭建基础框架；
8. 提供 requirements.txt 和 .env.example。

完成后请说明：
- 项目目录结构；
- 启动命令；
- 环境变量配置；
- 如何访问 Swagger 文档；
- 如何测试 /api/health。
```

### 5.3 验收标准

- 后端可以正常启动；
- 浏览器访问 `/docs` 正常；
- `/api/health` 返回服务正常；
- 数据库配置集中在 `.env` 或配置文件中；
- 无硬编码数据库密码。

---

## 6. 第 2 阶段：实现用户注册登录与 JWT

### 6.1 目标

完成用户注册、登录、JWT 认证和角色区分。

### 6.2 Codex 任务提示词

```text
请实现用户注册、登录和 JWT 认证功能。

要求：
1. 参考 docs/02_database_design.md 中 users 表设计；
2. 创建 User SQLAlchemy Model；
3. 创建用户相关 Pydantic Schema；
4. 实现用户注册接口 POST /api/auth/register；
5. 实现用户登录接口 POST /api/auth/login；
6. 实现获取当前用户接口 GET /api/auth/me；
7. 密码必须加密存储；
8. 支持 user 和 admin 两种角色；
9. 支持 active 和 disabled 状态；
10. 不要实现新闻检测功能。

完成后请给出：
- 修改了哪些文件；
- 接口说明；
- 请求示例；
- 返回示例；
- Swagger 测试方法。
```

### 6.3 验收标准

- 可以注册普通用户；
- 可以登录并获得 Token；
- 使用 Token 可以访问 `/api/auth/me`；
- 密码不是明文保存；
- 用户角色字段存在。

---

## 7. 第 3 阶段：实现数据库模型

### 7.1 目标

根据数据库设计文档创建所有核心 SQLAlchemy Model。

### 7.2 Codex 任务提示词

```text
请根据 docs/02_database_design.md 实现核心 SQLAlchemy Models。

需要实现的模型：
1. User
2. KnowledgeItem
3. DetectionRecord
4. EvidenceMatch
5. PromptTemplate
6. HighRiskNews
7. Report
8. SystemLog

要求：
- 字段名、含义和数据库设计文档保持一致；
- 合理设置外键关系；
- 暂时可以不使用 Alembic，但需要提供创建表的方法；
- 不要实现业务接口；
- 不要修改已有认证功能。
```

### 7.3 验收标准

- 所有 Model 可以正常导入；
- 启动项目无循环导入错误；
- 可以成功创建数据库表；
- 表字段与设计文档基本一致。

---

## 8. 第 4 阶段：实现知识库管理

### 8.1 目标

管理员可以新增、编辑、删除、查询知识库数据。

### 8.2 Codex 任务提示词

```text
请实现管理员端新闻知识库管理功能。

要求：
1. 参考 docs/02_database_design.md 的 knowledge_items 表；
2. 参考 docs/03_api_design.md 的知识库接口；
3. 实现 GET /api/admin/knowledge；
4. 实现 POST /api/admin/knowledge；
5. 实现 PUT /api/admin/knowledge/{id}；
6. 实现 DELETE /api/admin/knowledge/{id}；
7. 只有 admin 角色可以访问；
8. 本阶段先不接入 Chroma；
9. 业务逻辑放在 service 或 crud 层，不要全部写在路由中。

完成后请说明：
- 修改了哪些文件；
- 每个接口如何测试；
- 管理员权限如何控制。
```

### 8.3 验收标准

- 管理员可以新增知识库；
- 管理员可以查询知识库列表；
- 管理员可以修改知识库；
- 管理员可以删除知识库；
- 普通用户无法访问管理员接口。

---

## 9. 第 5 阶段：接入 Chroma 向量数据库

### 9.1 目标

知识库数据可以写入 Chroma，并支持 Top10 相似检索。

### 9.2 Codex 任务提示词

```text
请在知识库管理基础上接入 Chroma 向量数据库。

要求：
1. 新建 services/chroma_service.py；
2. 新增知识库数据后，可以生成文本向量并写入 Chroma；
3. 支持根据新闻标题和正文进行相似内容检索；
4. 检索接口为 POST /api/rag/search；
5. 默认返回 Top10 相似证据；
6. MySQL 保存原始知识库数据，Chroma 保存向量数据；
7. knowledge_items 表中的 vector_id 用于关联 Chroma 记录；
8. 不要把 Chroma 逻辑写在路由函数中。

完成后请说明：
- Chroma 数据保存位置；
- 向量化流程；
- 检索流程；
- 如何测试 Top10 检索结果。
```

### 9.3 验收标准

- 新增知识库后可以生成 vector_id；
- `/api/rag/search` 可以返回相似证据；
- 返回结果包含 title、summary、source_name、similarity_score、rank_order；
- 检索失败时有清晰错误信息。

---

## 10. 第 6 阶段：接入 DeepSeek API

### 10.1 目标

实现大模型可信度分析服务。

### 10.2 Codex 任务提示词

```text
请接入 DeepSeek API，实现新闻可信度分析服务。

要求：
1. 新建 services/llm_service.py；
2. 从环境变量读取 DeepSeek API Key；
3. 不要把 API Key 写死在代码里；
4. 输入新闻标题、正文和 Top5 检索证据；
5. 输出结构化 JSON；
6. JSON 字段包括 llm_score、risk_level、judgement_result、reason、risk_points、keywords、suggestion；
7. 如果 DeepSeek 调用失败，需要返回可理解的错误信息；
8. 如果模型返回不是合法 JSON，需要做容错处理；
9. 不要修改已有认证逻辑；
10. 不要修改知识库接口。

完成后请说明：
- 环境变量如何配置；
- 调用 DeepSeek 的代码在哪里；
- 如何模拟测试；
- 失败时如何处理。
```

### 10.3 验收标准

- API Key 从环境变量读取；
- 模型返回结构化结果；
- 失败时不会导致系统崩溃；
- 没有把密钥写进代码。

---

## 11. 第 7 阶段：实现新闻检测主流程

### 11.1 目标

完成系统最核心的检测接口。

### 11.2 Codex 任务提示词

```text
请实现新闻检测接口 POST /api/detect/news。

检测流程：
1. 接收新闻标题和正文；
2. 提取关键词；
3. 调用 Chroma 检索 Top10 证据；
4. 取 Top5 证据构造 Prompt；
5. 调用 DeepSeek 分析；
6. 执行规则评分；
7. 计算最终可信度评分；
8. 保存检测记录；
9. 保存证据匹配结果；
10. 如果是高风险谣言，生成待审核高风险新闻记录；
11. 返回完整检测结果。

评分公式：
最终可信度 = 检索证据相关度评分 × 40% + 大模型判断评分 × 40% + 来源/风险规则评分 × 20%

风险等级：
80-100：可信新闻
60-79：存疑信息
40-59：疑似谣言
0-39：高风险谣言

返回结果需要包括：
- detection_id
- final_score
- evidence_score
- llm_score
- rule_score
- risk_level
- judgement_result
- reason
- risk_points
- keywords
- evidence_list
- similar_news
- suggestion
- agent_steps
- report_url

请把检测主流程封装到 detect_service.py，不要把所有逻辑写在路由函数中。
```

### 11.3 验收标准

- 输入标题和正文可以得到完整检测结果；
- 检测记录写入 MySQL；
- 证据匹配结果写入 MySQL；
- 高风险结果会生成 high_risk_news 待审核记录；
- 返回字段满足前端展示需要。

---

## 12. 第 8 阶段：实现报告生成

### 12.1 目标

实现 HTML 和 PDF 报告生成与下载。

### 12.2 Codex 任务提示词

```text
请实现检测报告生成和下载功能。

要求：
1. 新建 services/report_service.py；
2. 根据 detection_records 和 evidence_matches 生成 HTML 报告；
3. 将 HTML 报告导出为 PDF；
4. 实现 POST /api/report/generate/{detection_id}；
5. 实现 GET /api/report/download/{report_id}；
6. 报告内容包括：新闻标题、检测时间、可信度评分、风险等级、判断理由、风险点、关键词、证据材料、相似新闻、辟谣建议、免责声明；
7. 报告路径保存到 reports 表；
8. 普通用户只能下载自己的报告，管理员可以下载所有报告。

完成后请说明：
- 使用了什么 PDF 生成库；
- 报告文件保存在哪里；
- 如何测试下载；
- 如果 PDF 生成失败如何处理。
```

### 12.3 验收标准

- 能生成 HTML 报告；
- 能生成 PDF 报告；
- 能下载 PDF；
- reports 表有记录；
- 报告内容完整。

---

## 13. 第 9 阶段：实现用户端前端

### 13.1 目标

完成普通用户使用系统的主要页面。

### 13.2 Codex 任务提示词

```text
请基于 Vue3 + Element Plus 实现用户端页面。

页面包括：
1. 首页 /
2. 登录页 /login
3. 注册页 /register
4. 新闻检测页 /detect
5. 检测结果页 /result/:id
6. 历史记录页 /history
7. 高风险新闻展示页 /high-risk
8. 个人中心 /profile

要求：
- 使用 Vue Router；
- 使用 Axios 调用后端接口；
- 登录后保存 Token；
- 请求后端时自动携带 Token；
- 检测结果页要重点美化；
- 展示可信度评分、风险等级、风险点、关键词、证据、相似新闻、辟谣建议、AI 分析过程；
- 提供 PDF 报告下载按钮；
- 不要实现管理员后台页面。
```

### 13.3 验收标准

- 可以注册登录；
- 可以提交新闻检测；
- 可以查看检测结果；
- 可以查看历史记录；
- 可以下载报告；
- 页面风格统一。

---

## 14. 第 10 阶段：实现管理员后台

### 14.1 目标

完成管理员端主要管理页面。

### 14.2 Codex 任务提示词

```text
请基于 Vue3 + Element Plus 实现管理员后台页面。

页面包括：
1. 后台首页 /admin/dashboard
2. 用户管理 /admin/users
3. 检测记录管理 /admin/detections
4. 知识库管理 /admin/knowledge
5. Prompt 模板管理 /admin/prompts
6. 高风险新闻管理 /admin/high-risk
7. 数据统计页 /admin/statistics
8. 报告管理 /admin/reports
9. 系统日志 /admin/logs

要求：
- 后台整体风格为科技蓝白风；
- 使用侧边栏布局；
- 使用 ECharts 展示统计图；
- 知识库管理支持新增、编辑、删除；
- Prompt 模板管理支持新增、编辑、删除、启用、停用、设为默认；
- 高风险新闻管理支持审核和设置前台展示；
- 不要影响用户端页面。
```

### 14.3 验收标准

- 管理员可以进入后台；
- 普通用户不能访问后台；
- 后台首页有统计数据；
- 知识库可以管理；
- Prompt 可以管理；
- 数据统计图可以显示。

---

## 15. 第 11 阶段：示例数据和演示优化

### 15.1 目标

为课程答辩和截图准备演示数据。

### 15.2 Codex 任务提示词

```text
请为项目生成一批演示数据初始化脚本。

要求：
1. 生成 30 条知识库演示数据；
2. 包括 10 条可信新闻、10 条存疑信息、10 条谣言样例；
3. 每条数据包含 title、content、category、truth_label、source_name、summary、keywords、debunking_explanation、risk_level；
4. 生成 1 个管理员账号；
5. 生成 2 个普通用户账号；
6. 不要使用真实敏感个人信息；
7. 数据内容用于课程演示，不追求真实新闻事实；
8. 提供运行初始化脚本的方法。
```

### 15.3 验收标准

- 系统有可演示数据；
- RAG 检索能返回结果；
- 后台统计图不为空；
- 高风险新闻页有内容。

---

## 16. 代码审查任务模板

当 Codex 写完某个模块后，可以让它自查：

```text
请你对刚刚实现的代码进行自查，重点检查：

1. 是否符合 docs 目录中的设计文档；
2. 是否存在未实现功能；
3. 是否存在接口路径不一致；
4. 是否存在数据库字段不一致；
5. 是否存在硬编码密钥；
6. 是否存在权限校验缺失；
7. 是否存在异常处理缺失；
8. 是否存在重复代码；
9. 是否存在前后端字段不一致；
10. 是否有可以优化但暂时不影响运行的地方。

请输出：
- 已完成内容；
- 发现的问题；
- 建议修改方案；
- 是否需要我确认后再修改。
```

---

## 17. Bug 修复任务模板

当运行报错时，不要只把错误截图发给 Codex。  
应该给它完整上下文。

```text
项目运行时出现以下错误，请帮我定位并修复。

错误发生位置：
后端 / 前端 / 数据库 / 接口调用 / 页面渲染

我执行的命令：
xxx

报错信息：
xxx

相关文件：
xxx

请你：
1. 先分析可能原因；
2. 再说明需要查看或修改哪些文件；
3. 修复时不要影响其他功能；
4. 修改后说明如何重新运行和验证；
5. 如果无法确定原因，请列出需要我补充的信息。
```

---

## 18. 前后端联调检查清单

每完成一个前后端联调功能，需要检查：

```text
1. 前端请求路径是否和后端一致；
2. 请求方法 GET / POST / PUT / DELETE 是否一致；
3. 请求字段是否一致；
4. 返回字段是否一致；
5. Token 是否正确携带；
6. 后端是否允许跨域；
7. 后端 Swagger 是否可测试；
8. 前端是否正确处理 loading；
9. 前端是否正确处理错误提示；
10. 页面刷新后登录状态是否保持。
```

---

## 19. 最小可运行版本范围

如果时间紧，必须优先完成最小可运行版本：

```text
1. 后端 FastAPI 可启动
2. MySQL 可连接
3. 用户登录注册
4. 管理员知识库管理
5. Chroma 检索
6. DeepSeek 调用
7. 新闻检测接口
8. 检测结果页
9. 历史记录页
10. PDF 报告下载
11. 后台首页统计
```

以下功能可以后续增强：

```text
1. 系统日志
2. 高风险排行榜
3. 词云
4. 多模型切换
5. Top-K 后台配置
6. 联网搜索
7. 多模态检测
```

---

## 20. 最终答辩演示流程

最终答辩建议按照以下顺序：

```text
1. 登录系统
2. 进入新闻检测页
3. 输入新闻标题和正文
4. 提交检测
5. 展示 AI 分析过程
6. 展示可信度评分和风险等级
7. 展示风险点、关键词、证据和相似新闻
8. 下载 PDF 检测报告
9. 查看个人历史记录
10. 切换管理员账号
11. 查看后台统计数据
12. 管理知识库
13. 修改 Prompt 模板
14. 再次检测对比效果
15. 展示高风险新闻管理
```

---

## 21. 最终提交前检查清单

课程设计提交前检查：

```text
1. 项目能正常启动；
2. 前端页面能正常访问；
3. 后端 Swagger 能正常访问；
4. MySQL 有初始化数据；
5. Chroma 能正常检索；
6. DeepSeek API Key 已正确配置；
7. 登录注册正常；
8. 新闻检测主流程正常；
9. 检测结果页展示完整；
10. PDF 报告可以下载；
11. 后台统计图不为空；
12. 知识库管理可用；
13. Prompt 模板管理可用；
14. 高风险新闻页面可展示；
15. README 写清楚运行步骤；
16. 课程报告截图齐全；
17. 答辩演示路径提前练习。
```
