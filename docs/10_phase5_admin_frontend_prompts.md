# 10_phase5_admin_frontend_prompts.md

> 项目：智闻辨真：基于 RAG 与大语言模型的新闻可信度评估系统
> 当前阶段：第五阶段，管理员后台与 Prompt 模板管理开发
> 角色分工：ChatGPT 负责项目规划、需求拆解、技术方案、Prompt 设计、代码审查意见；Codex 负责辅助编码、修复 Bug、补接口、补页面和生成测试。
> 使用原则：每次只让 Codex 完成一个明确任务，完成后必须说明修改文件、运行方式、测试方式和未完成风险。
> 重要原则：第五阶段必须继续复用第四阶段已经完成的设计系统、请求封装、Token 逻辑、权限逻辑和公共组件，禁止另起一套视觉体系或请求体系。

---

# 第五阶段：管理员后台与 Prompt 模板管理开发方案

## 一、阶段目标

第五阶段目标是完成管理员后台，让系统从“普通用户检测工具”升级为“可管理的新闻可信度评估平台”。

后台需要具备以下能力：

1. 管理员后台首页；
2. 用户管理；
3. 检测记录管理；
4. 知识库管理；
5. Prompt 模板管理；
6. 高风险新闻管理；
7. 数据统计；
8. 报告管理；
9. 系统日志。

本阶段重点是：

1. 后台结构完整；
2. 权限边界清晰；
3. 管理功能可用；
4. 与用户端视觉统一；
5. 继续复用已有请求封装和登录状态；
6. 不破坏第四阶段用户端功能。

本阶段不追求每个页面都极致复杂，但必须保证页面可用、接口清晰、权限安全、风格统一。

---

## 二、第五阶段强制约束

管理员后台开发时，必须遵守以下约束：

### 2.1 设计系统约束

必须继续复用：

1. `.codex/skills/ui-ux-pro-max/`
2. `design-system/MASTER.md`
3. `src/styles`
4. 第四阶段已有公共组件
5. 第四阶段已有页面视觉规范

禁止：

1. 重新设计一套后台颜色体系；
2. 重新写一套完全不同的按钮、卡片、表格风格；
3. 使用默认 Element Plus 裸样式；
4. 做成廉价后台模板风；
5. 让管理员端和用户端看起来像两个不同项目。

管理员后台应延续“科技蓝白 + 安全风控平台 + 企业级 AI 平台”的风格，但布局可以更偏后台管理系统：

1. 左侧菜单；
2. 顶部栏；
3. 面包屑；
4. 内容区卡片；
5. 表格筛选区；
6. 数据统计卡片；
7. ECharts 图表。

### 2.2 请求封装约束

必须继续复用第四阶段已有：

1. `src/utils/request.js`
2. Token 自动携带逻辑；
3. 401 处理逻辑；
4. Pinia 用户状态；
5. 统一 Axios baseURL；
6. 已有 API 模块组织方式。

禁止：

1. 重新创建第二套 Axios 实例；
2. 在页面里直接写原生 fetch；
3. 在页面里手动拼接重复 Token；
4. 在管理员页面里写死 Authorization；
5. 为后台单独维护一套登录状态。

可以新增：

1. `src/api/admin.js`
2. `src/api/adminUsers.js`
3. `src/api/adminDetections.js`
4. `src/api/adminKnowledge.js`
5. `src/api/adminPrompts.js`
6. `src/api/adminStatistics.js`
7. `src/api/adminReports.js`
8. `src/api/adminLogs.js`

但这些模块必须统一使用已有 `request.js`。

### 2.3 权限约束

所有 `/admin/*` 页面必须检查当前用户角色：

```text
role === 'admin'
```

权限要求：

1. 未登录用户访问 `/admin/*`，跳转登录页；
2. 普通用户访问 `/admin/*`，跳转无权限页或首页，并显示明确提示；
3. 管理员用户可以进入后台；
4. 刷新页面后，应基于已有 restoreSession 或 /api/auth/me 恢复用户状态；
5. 不能只依赖前端权限，后端管理员接口也应该由后端校验权限；
6. 前端不能调用管理员接口给普通用户使用。

禁止：

1. 普通用户菜单中出现管理员入口；
2. 普通用户访问管理员页面；
3. 普通用户调用 `/api/admin/*`；
4. 管理员后台破坏用户端路由守卫。

### 2.4 接口约束

开发每个页面前，必须先检查：

1. `docs/03_api_design.md`
2. 已有后端路由；
3. 已有前端 API 封装；
4. Swagger 或实际接口路径，如项目中可查看。

如果接口已经存在：

1. 按真实接口对接；
2. 不写假数据替代接口；
3. 做字段兼容和空状态。

如果接口暂未实现：

1. 不要硬造大量 mock 数据；
2. 页面保留空状态；
3. 标注“接口待接入”；
4. 在完成报告中说明后端缺口；
5. 如本阶段任务明确要求补后端接口，则先补后端、测试通过后再接前端。

---

## 三、管理员端页面规划

```text
/admin/dashboard          后台首页
/admin/users              用户管理
/admin/detections         检测记录管理
/admin/knowledge          知识库管理
/admin/prompts            Prompt 模板管理
/admin/high-risk          高风险新闻管理
/admin/statistics         数据统计页
/admin/reports            报告管理
/admin/logs               系统日志
```

建议目录：

```text
frontend/src/
├── api/
│   ├── admin.js
│   ├── adminUsers.js
│   ├── adminDetections.js
│   ├── adminKnowledge.js
│   ├── adminPrompts.js
│   ├── adminStatistics.js
│   ├── adminReports.js
│   └── adminLogs.js
├── layouts/
│   ├── UserLayout.vue
│   └── AdminLayout.vue
├── views/
│   ├── admin/
│   │   ├── AdminDashboardView.vue
│   │   ├── AdminUsersView.vue
│   │   ├── AdminDetectionsView.vue
│   │   ├── AdminKnowledgeView.vue
│   │   ├── AdminPromptsView.vue
│   │   ├── AdminHighRiskView.vue
│   │   ├── AdminStatisticsView.vue
│   │   ├── AdminReportsView.vue
│   │   └── AdminLogsView.vue
├── components/
│   ├── admin/
│   │   ├── AdminPageHeader.vue
│   │   ├── AdminStatCard.vue
│   │   ├── AdminFilterBar.vue
│   │   └── AdminTableActions.vue
```

---

# 阶段 5-0：管理员后台开发前检查与接入规范确认

```text
你现在负责开发“智闻辨真”第五阶段管理员后台。

本次任务不要写具体业务页面代码，只做开发前检查和接入规范确认。

请先读取：
1. .codex/skills/ui-ux-pro-max/
2. design-system/MASTER.md
3. docs/01_project_design.md
4. docs/03_api_design.md
5. docs/05_project_structure.md
6. src/router/index.js
7. src/utils/request.js
8. src/stores/user.js
9. src/layouts/UserLayout.vue
10. src/components
11. src/styles
12. package.json

检查目标：
1. 确认第四阶段用户端设计系统和公共样式；
2. 确认当前 Axios 请求封装；
3. 确认 Token 保存和自动携带方式；
4. 确认当前路由守卫如何判断登录态；
5. 确认当前用户信息中 role 字段如何表示管理员；
6. 确认后续管理员后台可以如何复用已有逻辑；
7. 检查 docs/03_api_design.md 中是否已有管理员接口；
8. 列出已存在接口和暂未确认接口。

重要要求：
1. 不要重新创建新的 Axios 请求体系；
2. 不要重新创建新的登录状态体系；
3. 不要重新设计一套后台视觉体系；
4. 不要修改用户端已有页面；
5. 不要破坏第四阶段功能。

完成后请输出：
1. 是否成功读取 UI UX Pro Max；
2. 是否成功读取 design-system/MASTER.md；
3. 当前请求封装位置和使用方式；
4. 当前 Token 保存位置；
5. 当前路由守卫逻辑；
6. 当前 role 字段判断方式；
7. 第五阶段建议新增哪些文件；
8. 哪些后端接口已存在；
9. 哪些后端接口暂未确认；
10. 后续开发必须遵守的复用规则。
```

---

# 阶段 5-1：搭建管理员后台布局和路由

```text
你现在继续开发“智闻辨真”第五阶段管理员后台。

本次任务只搭建管理员后台基础布局和路由，不实现具体业务 CRUD，不接复杂接口。

必须继续复用：
1. UI UX Pro Max；
2. design-system/MASTER.md；
3. src/utils/request.js；
4. src/stores/user.js；
5. 当前 Token 和登录态恢复逻辑；
6. 当前路由守卫模式；
7. 当前全局样式和设计变量。

请先读取：
1. src/router/index.js
2. src/stores/user.js
3. src/layouts/UserLayout.vue
4. src/styles
5. src/components
6. design-system/MASTER.md

本次需要完成：
1. 新增 /admin 路由组；
2. 创建 src/layouts/AdminLayout.vue；
3. 创建管理员后台基础空页面：
   - /admin/dashboard
   - /admin/users
   - /admin/detections
   - /admin/knowledge
   - /admin/prompts
   - /admin/high-risk
   - /admin/statistics
   - /admin/reports
   - /admin/logs
4. 左侧菜单包括：
   - 后台首页
   - 用户管理
   - 检测记录管理
   - 知识库管理
   - Prompt 模板管理
   - 高风险新闻管理
   - 数据统计
   - 报告管理
   - 系统日志
5. 顶部栏展示当前管理员用户名、角色和退出按钮；
6. 增加面包屑导航；
7. 内容区使用统一卡片容器；
8. /admin/* 必须检查 role === 'admin'；
9. 普通用户访问 /admin/* 时跳转首页或无权限页；
10. 未登录用户访问 /admin/* 时跳转 /login；
11. 不影响用户端页面和用户端路由；
12. 不调用不存在的接口。

UI 要求：
1. 复用当前科技蓝白设计系统；
2. 管理员端偏企业后台风；
3. 左侧菜单简洁、层级清楚；
4. 顶部栏干净，不花哨；
5. 内容区留白充足；
6. 不要默认 Element Plus 裸样式；
7. 与用户端视觉统一，但布局更适合管理后台。

完成后请说明：
1. 是否成功读取 UI UX Pro Max；
2. 修改了哪些文件；
3. 新增了哪些路由；
4. AdminLayout 如何组织；
5. /admin/* 权限判断逻辑；
6. 普通用户无法访问后台如何测试；
7. 管理员正常访问后台如何测试；
8. 是否影响用户端页面；
9. npm run build 是否通过。
```

---

# 阶段 5-2：实现后台首页 Dashboard 与统计卡片

```text
请实现管理员后台首页 /admin/dashboard。

本次任务只开发后台首页，不开发其他管理页面。

必须继续复用：
1. AdminLayout；
2. 已有 request.js；
3. 设计系统；
4. 已有 EmptyState、LoadingState 或类似组件；
5. ECharts 已有引入方式，如项目中已使用。

请先检查接口是否存在：
1. GET /api/admin/statistics/overview
2. GET /api/admin/statistics/risk-distribution
3. GET /api/admin/statistics/trend
4. GET /api/admin/statistics/category-distribution

如果接口存在：
按真实接口对接。

如果接口不存在：
1. 不要硬造大量假数据；
2. 页面显示空状态；
3. 标注“统计接口待接入”；
4. 保留图表容器和后续接入位置；
5. 在完成报告中说明后端接口缺口。

页面展示：
1. 总检测次数；
2. 今日检测次数；
3. 用户总数；
4. 知识库数量；
5. 高风险新闻数量；
6. 报告生成数量；
7. 风险等级分布图；
8. 近 7 日检测趋势图；
9. 新闻类别分布图；
10. 最近高风险检测记录，可选，如果有接口支持。

UI 要求：
1. 顶部使用后台 PageHeader；
2. 统计卡片使用统一 AdminStatCard；
3. 图表区域使用卡片承载；
4. 接口失败时显示 EmptyState；
5. loading 状态清晰；
6. 不要页面白屏；
7. 不要写死核心统计数据；
8. 不要让图表风格脱离设计系统。

完成后请说明：
1. 修改了哪些文件；
2. 新增了哪些 API 封装；
3. 每个统计卡片的数据来源；
4. 每个图表的数据来源；
5. 接口不存在时如何降级；
6. 如何测试；
7. npm run build 是否通过；
8. 当前未完成风险。
```

---

# 阶段 5-3：实现管理员检测记录管理

```text
请实现管理员检测记录管理页面 /admin/detections。

本次任务只开发检测记录管理，不开发用户管理、知识库管理和 Prompt 模板管理。

必须继续复用：
1. AdminLayout；
2. src/utils/request.js；
3. RiskLevelTag；
4. EmptyState、LoadingState；
5. design-system/MASTER.md；
6. 第四阶段关于分数空值和 is_high_risk 语义修复后的处理方式。

请先检查接口是否存在：
1. GET /api/admin/detections
2. GET /api/admin/detections/{id}
3. DELETE /api/admin/detections/{id}

功能要求：
1. 管理员可以查看全部检测记录；
2. 表格字段包括：
   - 检测标题
   - 用户
   - final_score
   - risk_level
   - is_high_risk
   - 检测时间
   - 报告状态
   - 操作
3. 支持按 risk_level 筛选；
4. 支持关键词搜索；
5. 支持按时间范围筛选；
6. 支持按 user_id 筛选，如接口支持；
7. 支持分页；
8. 支持查看详情；
9. 支持删除异常检测记录；
10. 删除前必须二次确认；
11. 删除失败要显示后端错误信息；
12. 不要在前端计算 final_score；
13. 不要在前端推导 risk_level；
14. is_high_risk 必须以后端字段为准，缺失时显示“--”或“未标记”。

详情展示要求：
1. 可复用用户端 ResultView 的展示组件；
2. 也可以使用管理员详情弹窗；
3. 必须展示证据、风险点、建议、AI 分析过程；
4. 字段缺失时不能白屏。

完成后请说明：
1. 修改了哪些文件；
2. 新增了哪些 API 封装；
3. 检测记录列表如何查询；
4. 筛选和分页如何实现；
5. 删除操作如何确认；
6. 是否复用了用户端结果组件；
7. 如何测试管理员权限；
8. npm run build 是否通过；
9. 未完成风险。
```

---

# 阶段 5-4：实现用户管理页面

```text
请实现管理员用户管理页面 /admin/users。

本次任务只开发用户管理页面，不开发其他管理员页面。

请先检查接口是否存在：
1. GET /api/admin/users
2. GET /api/admin/users/{id}
3. PUT /api/admin/users/{id}/status
4. GET /api/admin/users/{id}/detections

如果接口不存在：
1. 不要硬造复杂假数据；
2. 显示空状态或接口待接入；
3. 在报告中列出后端缺口。

功能要求：
1. 展示用户列表；
2. 字段包括：
   - 用户名
   - 邮箱
   - 角色
   - 状态
   - 注册时间
   - 最近登录时间，如有
   - 检测次数，如有
   - 操作
3. 支持按用户名或邮箱搜索；
4. 支持按角色筛选；
5. 支持按状态筛选；
6. 支持分页；
7. 支持启用/禁用用户；
8. 启用/禁用前必须二次确认；
9. 支持查看该用户检测记录，如接口支持；
10. 禁止管理员误禁用自己，如后端不允许则显示错误信息，如前端能识别也要做提示。

权限要求：
1. 只有 admin 可以访问；
2. 不要让普通用户调用管理员用户接口；
3. 401/403 要有清晰提示。

UI 要求：
1. 使用统一后台表格风格；
2. 筛选区清晰；
3. 状态标签统一；
4. 操作按钮不要拥挤；
5. 空状态和 loading 状态美观。

完成后请说明：
1. 修改了哪些文件；
2. 新增了哪些 API 封装；
3. 用户列表字段映射；
4. 启用/禁用流程；
5. 接口不存在时如何处理；
6. 如何测试；
7. npm run build 是否通过；
8. 未完成风险。
```

---

# 阶段 5-5：实现知识库管理页面

```text
请实现管理员知识库管理页面 /admin/knowledge。

本次任务只开发知识库管理页面。

请先检查并复用第二阶段已有知识库接口和 API 封装。如已有文件，请继续完善，不要重复创建冲突模块。

预期接口：
1. GET /api/admin/knowledge
2. POST /api/admin/knowledge
3. PUT /api/admin/knowledge/{id}
4. DELETE /api/admin/knowledge/{id}
5. POST /api/admin/knowledge/{id}/vectorize
6. POST /api/admin/knowledge/rebuild-index，如已有全量重建接口

功能要求：
1. 表格展示知识库数据；
2. 字段包括：
   - 新闻标题
   - 类别
   - 真实性标签
   - 来源
   - 风险等级
   - 向量同步状态
   - 向量错误信息，如有
   - 更新时间
   - 操作
3. 支持新增知识库数据；
4. 支持编辑知识库数据；
5. 支持删除知识库数据；
6. 支持手动重新向量化；
7. 如已有全量索引重建接口，可提供全量重建按钮；
8. 支持按类别、标签、风险等级、向量状态筛选；
9. 新增和编辑使用弹窗表单；
10. 正文、摘要、辟谣说明使用多行文本框；
11. 删除前必须二次确认；
12. 向量化失败时显示明确错误。

严格限制：
1. 不要在前端生成向量；
2. 不要在前端直接操作 Chroma；
3. 向量化必须调用后端接口；
4. 不要绕过后端 MySQL 与 Chroma 一致性逻辑；
5. 不要破坏第二阶段 RAG 接口；
6. 不要修改后端已有知识库同步策略，除非本任务明确要求。

UI 要求：
1. 使用后台统一表格；
2. 向量状态要有明显标签：
   - synced
   - pending
   - failed
3. failed 状态要显示错误提示入口；
4. 表单字段要清晰；
5. 大文本字段要便于编辑；
6. 操作按钮要有二次确认。

完成后请说明：
1. 修改了哪些文件；
2. 复用了哪些已有接口；
3. 新增了哪些 API 封装；
4. 新增、编辑、删除流程；
5. 单条向量化流程；
6. 全量重建是否支持；
7. 如何测试；
8. npm run build 是否通过；
9. 未完成风险。
```

---

# 阶段 5-6：实现 Prompt 模板管理

```text
请实现 Prompt 模板管理功能。

这是第五阶段重点功能之一。开发前必须先检查后端是否已经存在 Prompt 模板相关接口和数据表。

请先读取：
1. docs/03_api_design.md
2. 后端 models、schemas、crud、services、api/v1 目录中与 prompt 相关的文件
3. 前端 src/api
4. 前端 src/views/admin
5. design-system/MASTER.md

预期后端接口：
1. GET /api/admin/prompts
2. POST /api/admin/prompts
3. PUT /api/admin/prompts/{id}
4. DELETE /api/admin/prompts/{id}
5. POST /api/admin/prompts/{id}/enable
6. POST /api/admin/prompts/{id}/disable
7. POST /api/admin/prompts/{id}/set-default

预期数据表：
prompt_templates

建议字段：
1. id
2. name
3. type
4. content
5. is_default
6. status
7. created_by
8. created_at
9. updated_at

如果后端接口和数据表已存在：
1. 直接对接前端页面；
2. 不重复创建后端代码。

如果后端接口或数据表不存在：
请先实现后端 Prompt 模板管理能力，再开发前端页面。
后端实现要求：
1. 创建 prompt_templates Model；
2. 创建 Pydantic Schema；
3. 创建 CRUD；
4. 创建 Service；
5. 创建管理员 API 路由；
6. 管理员接口必须校验 admin 权限；
7. 同一 type 只能有一个默认模板；
8. 被停用模板不能设为默认；
9. 删除默认模板前需要明确提示或禁止删除；
10. 新闻检测流程后续应能读取默认的新闻可信度分析 Prompt；
11. 不要破坏当前 DeepSeek 检测主流程。

前端页面 /admin/prompts 要求：
1. 展示模板名称；
2. 展示模板类型；
3. 展示状态；
4. 展示是否默认；
5. 展示更新时间；
6. 支持新增模板；
7. 支持编辑模板；
8. 支持删除模板；
9. 支持启用/停用；
10. 支持设为默认；
11. Prompt 内容使用大文本编辑框；
12. 删除和设为默认必须二次确认；
13. 启停失败要显示后端错误；
14. 设置默认失败要显示后端错误。

业务规则：
1. 同一类型只能有一个默认模板；
2. 被停用模板不能设为默认；
3. 删除默认模板前必须提示；
4. 新闻检测时优先读取默认的新闻可信度分析 Prompt；
5. 如果没有默认模板，检测流程应使用代码中的安全兜底模板；
6. Prompt 内容不能为空；
7. Prompt 类型建议至少支持 news_credibility。

严格限制：
1. 不要把 Prompt 模板只写死在前端；
2. 不要让普通用户访问 Prompt 管理；
3. 不要破坏现有新闻检测接口；
4. 不要导致 DeepSeek 调用失败时假装成功；
5. 不要引入大量假数据。

完成后请说明：
1. 后端是否原本已有 Prompt 接口；
2. 如果新增了后端，修改了哪些文件；
3. 前端修改了哪些文件；
4. Prompt 模板如何被检测流程读取；
5. 默认模板冲突如何处理；
6. 停用模板为何不能设默认；
7. 前端如何测试新增、编辑、启停、设默认；
8. 新闻检测流程是否受影响；
9. npm run build 是否通过；
10. 后端测试是否通过；
11. 未完成风险。
```

---

# 阶段 5-7：实现高风险新闻管理、报告管理与系统日志

```text
请实现管理员后台的高风险新闻管理、报告管理和系统日志页面。

本次任务优先完成页面结构和真实接口对接。如果接口不存在，不要硬造复杂假数据，要显示空状态并说明接口待接入。

一、高风险新闻管理 /admin/high-risk

请先检查接口是否存在：
1. GET /api/admin/high-risk
2. PUT /api/admin/high-risk/{id}/review
3. PUT /api/admin/high-risk/{id}/visibility
4. PUT /api/admin/high-risk/{id}/remark

功能要求：
1. 查看高风险检测记录；
2. 支持管理员审核；
3. 支持设置是否前台展示；
4. 支持添加管理员备注；
5. 支持按类别、时间、审核状态筛选；
6. 支持分页；
7. 管理操作需要二次确认；
8. 不要根据 risk_level 自行推导公开展示状态，是否前台展示以后端字段为准。

二、报告管理 /admin/reports

请先检查接口是否存在：
1. GET /api/admin/reports
2. GET /api/admin/reports/{id}
3. DELETE /api/admin/reports/{id}
4. GET /api/admin/reports/{id}/download

功能要求：
1. 查看所有报告；
2. 按用户、时间、风险等级筛选；
3. 支持下载报告；
4. 支持删除无效报告记录；
5. 删除前必须二次确认；
6. report_url 为空时不能假装可下载；
7. 下载失败显示明确错误。

三、系统日志 /admin/logs

请先检查接口是否存在：
1. GET /api/admin/logs

功能要求：
1. 展示登录日志；
2. 展示检测日志；
3. 展示管理员操作日志；
4. 字段包括：
   - 用户
   - 模块
   - 操作
   - 描述
   - IP
   - 时间
5. 支持按模块筛选；
6. 支持按时间筛选；
7. 支持分页；
8. 接口不存在时显示“日志接口待接入”。

统一要求：
1. 页面先保证可用，不追求复杂；
2. 表格分页；
3. 管理操作需要二次确认；
4. 失败时显示后端错误；
5. 不要影响现有用户端功能；
6. 不要调用不存在接口；
7. 不要写大量假数据；
8. 保持 UI UX Pro Max 风格。

完成后请说明：
1. 修改了哪些文件；
2. 每个页面调用了哪些接口；
3. 哪些接口已真实接入；
4. 哪些接口待后端补充；
5. 高风险展示状态如何判断；
6. 报告下载如何处理；
7. 系统日志如何筛选；
8. 如何测试；
9. npm run build 是否通过；
10. 未完成风险。
```

---

# 阶段 5-8：实现数据统计页

```text
请实现管理员数据统计页 /admin/statistics。

本页面用于比后台首页更详细地展示系统运行情况。

请先检查接口是否存在：
1. GET /api/admin/statistics/overview
2. GET /api/admin/statistics/trend
3. GET /api/admin/statistics/risk-distribution
4. GET /api/admin/statistics/category-distribution
5. GET /api/admin/statistics/user-activity
6. GET /api/admin/statistics/knowledge-vector-status

功能要求：
1. 展示检测总量趋势；
2. 展示风险等级分布；
3. 展示新闻类别分布；
4. 展示用户活跃度；
5. 展示知识库向量同步状态；
6. 支持时间范围筛选；
7. 使用 ECharts；
8. 接口失败时显示空状态；
9. 没有真实接口时不要硬造图表数据；
10. 图表风格要与后台统一。

UI 要求：
1. 图表卡片布局；
2. 筛选区简洁；
3. loading 和 empty 状态清楚；
4. 图表不要过度花哨；
5. 颜色遵循 design-system/MASTER.md。

完成后请说明：
1. 修改了哪些文件；
2. 图表数据来源；
3. 字段映射；
4. 接口缺失时如何处理；
5. ECharts 是否按需引入或已有引入；
6. npm run build 是否通过；
7. 是否仍有 chunk 警告；
8. 未完成风险。
```

---

# 阶段 5-9：第五阶段统一自测与 UI 优化

```text
请作为前端 UI/UX 审查员和代码审查员，对第五阶段管理员后台进行统一自测和优化。

本次可以修复前端问题，但不要随意修改后端业务逻辑。

请先读取：
1. .codex/skills/ui-ux-pro-max/
2. design-system/MASTER.md
3. src/router/index.js
4. src/layouts/AdminLayout.vue
5. src/views/admin
6. src/api
7. src/utils/request.js
8. src/stores/user.js
9. src/styles

检查范围：
1. /admin/dashboard
2. /admin/users
3. /admin/detections
4. /admin/knowledge
5. /admin/prompts
6. /admin/high-risk
7. /admin/statistics
8. /admin/reports
9. /admin/logs

UI/UX 检查：
1. 是否复用现有设计系统；
2. 是否和用户端风格统一；
3. 是否存在默认 Element Plus 裸样式；
4. 左侧菜单是否清晰；
5. 顶部栏是否简洁；
6. 表格、筛选区、弹窗、按钮、标签是否统一；
7. 空状态和 loading 状态是否美观；
8. 图表风格是否统一；
9. 管理页面是否适合答辩展示。

权限检查：
1. 未登录访问 /admin/* 是否跳转登录；
2. 普通用户访问 /admin/* 是否被拦截；
3. 管理员是否能正常访问；
4. 刷新后管理员登录态是否恢复；
5. 管理员退出后是否无法继续访问后台；
6. 普通用户是否看不到管理员入口。

接口检查：
1. 是否统一使用 request.js；
2. 是否没有新建第二套 Axios；
3. 是否没有页面直接写 fetch；
4. 是否没有硬编码 Token；
5. 是否没有普通用户调用管理员接口；
6. 接口失败是否不会白屏；
7. 接口缺失是否显示空状态；
8. 是否没有大量假数据。

功能检查：
1. Dashboard 是否可展示或优雅空状态；
2. 检测记录管理是否可筛选、分页、查看、删除；
3. 用户管理是否可展示、筛选、启停；
4. 知识库管理是否可新增、编辑、删除、向量化；
5. Prompt 模板是否可新增、编辑、删除、启停、设默认；
6. 高风险新闻管理是否可展示和操作；
7. 报告管理是否正确处理 report_url；
8. 系统日志是否可展示或优雅空状态；
9. 数据统计图表是否可展示或优雅空状态。

构建检查：
1. 运行 npm run build；
2. 如有 lint 命令，运行 npm run lint；
3. 如有测试命令，运行测试；
4. 记录构建结果。

完成后请输出：
1. 修改了哪些文件；
2. 修复了哪些 UI 问题；
3. 修复了哪些权限问题；
4. 修复了哪些接口问题；
5. npm run build 是否通过；
6. lint 是否通过；
7. 第五阶段是否达到验收标准；
8. 是否影响第四阶段用户端功能；
9. 当前未完成风险。
```

---

# 第五阶段验收标准

```text
1. 普通用户无法访问 /admin/*；
2. 未登录用户无法访问 /admin/*；
3. 管理员可以进入后台首页；
4. 管理员后台继续复用现有设计系统；
5. 管理员后台继续复用现有 request.js 和 Token 逻辑；
6. 后台首页能显示核心统计或优雅空状态；
7. 管理员能查看所有检测记录；
8. 知识库可以在前端完成新增、编辑、删除、向量化；
9. Prompt 模板可以完成新增、编辑、删除、启停、设默认；
10. 管理员能管理高风险新闻展示；
11. 报告管理和系统日志至少具备列表展示或优雅空状态；
12. 数据统计图能正常显示或优雅空状态；
13. 删除、禁用、设默认等关键操作有二次确认；
14. 接口失败时页面不白屏；
15. 不存在大量硬编码假数据；
16. 不影响普通用户注册、登录、检测、结果页、历史记录；
17. npm run build 通过。
```

---

# 第五阶段最终代码审查提示词

```text
请作为代码审查员，检查“智闻辨真”第五阶段管理员后台和 Prompt 模板管理代码。

本次只输出审查报告，不要直接修改代码。

请先读取：
1. .codex/skills/ui-ux-pro-max/
2. design-system/MASTER.md
3. docs/03_api_design.md
4. src/router/index.js
5. src/layouts/AdminLayout.vue
6. src/views/admin
7. src/api
8. src/utils/request.js
9. src/stores/user.js
10. 后端 prompt 相关文件，如本阶段新增

重点检查：

一、设计系统
1. 管理员后台是否复用现有设计系统；
2. 是否另起一套视觉风格；
3. 是否存在默认 Element Plus 裸样式；
4. 是否与用户端风格统一；
5. 是否适合答辩展示。

二、请求封装
1. 是否统一复用 request.js；
2. 是否新建了第二套 Axios；
3. 是否页面里直接 fetch；
4. 是否硬编码 Token；
5. 401/403 是否正确处理。

三、权限
1. /admin/* 是否严格限制 admin 角色；
2. 未登录用户是否无法访问后台；
3. 普通用户是否无法访问后台；
4. 刷新后管理员权限是否仍然有效；
5. 普通用户是否看不到后台入口；
6. 是否调用了管理员接口给普通用户。

四、业务功能
1. Dashboard 是否可用；
2. 用户管理是否可用；
3. 检测记录管理是否可用；
4. 知识库管理是否可用；
5. Prompt 模板管理是否可用；
6. 高风险新闻管理是否可用；
7. 报告管理是否可用或优雅空状态；
8. 系统日志是否可用或优雅空状态；
9. 数据统计是否可用或优雅空状态。

五、Prompt 模板
1. 是否存在多个默认模板冲突；
2. 同一 type 是否只能有一个默认模板；
3. 停用模板是否禁止设为默认；
4. 删除默认模板是否有提示或限制；
5. 新闻检测流程是否能读取默认 Prompt；
6. 没有默认 Prompt 时是否有安全兜底；
7. 是否影响 DeepSeek 检测主流程。

六、知识库
1. 知识库向量化是否错误放到前端执行；
2. 是否仍然由后端处理向量化；
3. 删除、编辑、向量化是否有错误提示；
4. 是否破坏第二阶段 RAG 接口。

七、操作安全
1. 删除 Prompt 是否二次确认；
2. 删除知识库是否二次确认；
3. 删除检测记录是否二次确认；
4. 禁用用户是否二次确认；
5. 设置默认 Prompt 是否二次确认；
6. 报告删除是否二次确认。

八、稳定性
1. 接口失败时页面是否崩溃；
2. 图表接口失败时是否白屏；
3. 字段缺失时是否白屏；
4. 是否存在大量假数据；
5. npm run build 是否通过；
6. 是否影响第四阶段用户端功能。

请输出审查报告，格式如下：

1. 总体结论：是否通过第五阶段验收；
2. 阻断问题：如无请写“无”；
3. 中等问题：建议进入下一阶段前修复的问题；
4. 轻微问题：不阻断但建议优化的问题；
5. UI/UX 评价；
6. 权限与 Token 评价；
7. 接口封装评价；
8. Prompt 模板管理评价；
9. 知识库管理评价；
10. 数据统计与图表评价；
11. 对第四阶段用户端功能的影响；
12. 建议下一步工作。
```
