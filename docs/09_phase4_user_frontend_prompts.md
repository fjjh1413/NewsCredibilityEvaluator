# 09_phase4_user_frontend_prompts.md

> 项目：智闻辨真：基于 RAG 与大语言模型的新闻可信度评估系统  
> 角色分工：ChatGPT 负责项目规划、需求拆解、技术方案、Prompt 设计、代码审查意见；Codex 负责辅助编码、修复 Bug、补接口、补页面和生成测试。  
> 使用原则：每次只让 Codex 完成一个明确任务，完成后必须说明修改文件、运行方式、测试方式和未完成风险。


# 第四阶段：用户端 Vue 前端开发方案

## 一、阶段目标

第四阶段目标是完成普通用户可以使用的前端主流程。用户应能够完成注册、登录、提交新闻检测、查看检测结果、下载报告入口、查看历史记录、浏览高风险新闻和个人中心。

本阶段的关键不是页面数量堆叠，而是把“新闻检测结果页”做成系统演示核心页面。

## 二、技术方案

### 2.1 前端技术栈

```text
Vue 3
Vue Router
Pinia
Axios
Element Plus
ECharts
```

### 2.2 用户端页面

```text
/                 首页
/login            登录页
/register         注册页
/detect           新闻检测页
/result/:id       检测结果页
/history          历史记录页
/high-risk        高风险新闻展示页
/profile          个人中心
```

### 2.3 前端目录建议

```text
frontend/src/
├── api/
│   ├── auth.js
│   ├── detect.js
│   ├── highRisk.js
│   └── report.js
├── assets/
├── components/
│   ├── RiskLevelTag.vue
│   ├── ScoreCard.vue
│   ├── EvidenceList.vue
│   ├── AgentSteps.vue
│   └── PageHeader.vue
├── router/
│   └── index.js
├── stores/
│   └── user.js
├── utils/
│   ├── request.js
│   └── auth.js
├── views/
│   ├── HomeView.vue
│   ├── LoginView.vue
│   ├── RegisterView.vue
│   ├── DetectView.vue
│   ├── ResultView.vue
│   ├── HistoryView.vue
│   ├── HighRiskView.vue
│   └── ProfileView.vue
└── App.vue
```

### 2.4 UI 风格

采用“科技蓝白 + 安全风控平台 + 企业级 AI 平台”风格：

- 主色：蓝色、青色、白色；
- 页面留白充足；
- 检测结果用卡片分区；
- 风险等级用标签色区分；
- 证据列表清晰展示；
- 不做花哨动画，强调专业和可信。

# 阶段0提示词：读取 UI UX Pro Max 并建立用户端设计规范

你现在负责开发“智闻辨真：基于 RAG 与大语言模型的新闻可信度评估系统”的第四阶段用户端 Vue 前端。

本阶段不要开发业务页面代码，只做设计规范读取、整理和确认。

项目背景：
本系统是一个基于 RAG、DeepSeek、MySQL、Chroma 的新闻可信度评估系统。用户可以输入新闻标题和正文，系统会进行证据检索、大模型分析、规则评分、综合评分，并生成风险等级。

第四阶段目标：
完成普通用户端 Vue 页面，包括首页、登录注册、新闻检测、检测结果、历史记录、高风险新闻展示、个人中心。其中“检测结果页”是系统演示和答辩展示的核心页面。

技术栈：
Vue3 + Vue Router + Pinia + Axios + Element Plus + ECharts

重要要求：
我的电脑中已经安装 UI UX Pro Max，你必须严格遵照 UI UX Pro Max 的设计规范开发页面。不要做默认 Element Plus 裸样式页面，不要做普通后台模板风页面。

开始前必须先检查并读取：

1. .codex/skills/ui-ux-pro-max/
2. design-system/MASTER.md
3. docs/01_project_design.md
4. docs/03_api_design.md
5. docs/05_project_structure.md
6. package.json
7. src/styles
8. src/components
9. src/views
10. src/router

如果没有读取到 UI UX Pro Max 或 design-system/MASTER.md，请先停止实现并说明原因，不要凭空生成普通 UI。

本项目 UI 风格定位：
采用“科技蓝白 + 安全风控平台 + 企业级 AI 平台”风格。

视觉要求：

1. 专业、现代、可信、清爽；
2. 适合课程设计答辩、毕业设计展示和项目截图；
3. 不要廉价模板风；
4. 不要默认 Element Plus 裸样式；
5. 不要大面积纯白空洞页面；
6. 不要过度渐变；
7. 不要过度动画；
8. 页面留白充足；
9. 卡片层次清晰；
10. 风险等级颜色区分明显；
11. 表格简洁、行距舒适；
12. PC端展示效果优先，兼顾响应式。

颜色建议：

1. 主色：科技蓝、深蓝、青色；
2. 背景色：极浅蓝灰或浅冷色背景；
3. 卡片色：白色或半透明白色；
4. 可信新闻：绿色；
5. 存疑信息：黄色或琥珀色；
6. 疑似谣言：橙色；
7. 高风险谣言：红色；
8. 普通文字：深灰；
9. 辅助文字：中性灰；
10. 边框：浅灰蓝。

请完成：

1. 检查当前项目是否已有设计系统；
2. 如果已有 design-system/MASTER.md，请基于它继续完善，不要推翻重写；
3. 如果没有 design-system/MASTER.md，请根据 UI UX Pro Max 规范生成一份适合本项目的设计系统文档；
4. 明确本项目用户端的视觉风格；
5. 明确颜色、字体、字号、间距、圆角、阴影、按钮、表格、表单、标签、卡片、空状态、加载状态规范；
6. 明确风险等级视觉规范；
7. 明确检测结果页的展示层级；
8. 明确后续页面开发必须遵守的规则。

检测结果页设计重点：

1. 第一屏必须突出 final_score 和 risk_level；
2. 三项分数 evidence_score、llm_score、rule_score 要并列展示；
3. 风险点、关键词、证据、建议、AI 分析过程要分区展示；
4. 不要把字段从上到下平铺成普通文字；
5. 页面要适合答辩截图展示。

完成后请输出：

1. 是否成功读取 UI UX Pro Max；
2. 读取了哪些文件；
3. 修改或新增了哪些文件；
4. 当前项目最终采用的设计风格；
5. 后续页面开发必须遵守的 UI 规则；
6. 是否存在未完成风险。

特别注意：
如果你没有成功读取 UI UX Pro Max 或 design-system/MASTER.md，请不要继续写页面代码，必须先说明原因。

# 阶段1提示词：搭建用户端基础结构、路由、布局和公共组件

你现在继续开发“智闻辨真”第四阶段用户端 Vue 前端。

本阶段目标：
基于 UI UX Pro Max 和 design-system/MASTER.md，搭建用户端基础结构、路由、布局、Axios 请求封装、Token 拦截器、Pinia 用户状态和公共组件。

本阶段只做基础结构，不开发具体业务页面，不开发管理员后台，不修改后端接口。

开始前必须先读取：

1. .codex/skills/ui-ux-pro-max/
2. design-system/MASTER.md
3. package.json
4. src/router
5. src/views
6. src/components
7. src/styles
8. src/api
9. src/stores

如果没有读取到 UI UX Pro Max 或 design-system/MASTER.md，请先停止实现并说明原因，不要凭空生成普通 UI。

技术栈：
Vue3 + Vue Router + Pinia + Axios + Element Plus + ECharts

需要建立的页面路由：
/                 首页
/login            登录页
/register         注册页
/detect           新闻检测页
/result/:id       检测结果页
/history          历史记录页
/high-risk        高风险新闻展示页
/profile          个人中心

请完成：

1. 创建或整理 router/index.js；
2. 创建用户端布局 UserLayout.vue；
3. 创建首页、登录页、注册页、新闻检测页、检测结果页、历史记录页、高风险新闻页、个人中心页的基础空页面；
4. 配置路由守卫；
5. 游客可以访问 /、/login、/register、/detect；
6. /history 和 /profile 需要登录；
7. /result/:id 需要支持游客查看刚刚检测的结果；
8. 创建或整理 Axios 请求实例；
9. 配置 Token 自动携带；
10. 配置 401 统一处理；
11. 配置 Pinia 用户状态；
12. 刷新页面后尝试从本地 Token 恢复登录状态；
13. 提取用户端公共组件；
14. 不要调用不存在的接口；
15. 不要写死假数据。

建议目录结构：
frontend/src/
├── api/
│   ├── auth.js
│   ├── detect.js
│   ├── highRisk.js
│   └── report.js
├── components/
│   ├── RiskLevelTag.vue
│   ├── ScoreCard.vue
│   ├── EvidenceList.vue
│   ├── AgentSteps.vue
│   ├── PageHeader.vue
│   ├── EmptyState.vue
│   ├── LoadingState.vue
│   └── ResultSection.vue
├── layouts/
│   └── UserLayout.vue
├── router/
│   └── index.js
├── stores/
│   └── user.js
├── styles/
│   ├── theme.css
│   └── common.css
├── utils/
│   ├── request.js
│   ├── auth.js
│   └── format.js
├── views/
│   ├── HomeView.vue
│   ├── LoginView.vue
│   ├── RegisterView.vue
│   ├── DetectView.vue
│   ├── ResultView.vue
│   ├── HistoryView.vue
│   ├── HighRiskView.vue
│   └── ProfileView.vue
└── App.vue

建议公共组件：

1. RiskLevelTag.vue：风险等级标签；
2. ScoreCard.vue：评分卡片；
3. EvidenceList.vue：证据列表；
4. AgentSteps.vue：AI 分析步骤；
5. PageHeader.vue：页面标题；
6. EmptyState.vue：空状态；
7. LoadingState.vue：加载状态；
8. ResultSection.vue：结果页分区组件。

布局要求：

1. 顶部导航栏展示系统名称“智闻辨真”；
2. 导航包含：首页、新闻检测、历史记录、高风险新闻、个人中心；
3. 右侧展示登录/注册或用户信息/退出；
4. 页面主体使用统一容器；
5. 背景、卡片、按钮、标签、表单样式统一；
6. 不要使用默认 Element Plus 裸样式；
7. PC端展示效果优先，兼顾响应式。

开发原则：

1. 不修改后端业务逻辑；
2. 不修改后端接口路径；
3. 不开发管理员后台；
4. 不调用不存在接口；
5. 不写复杂假数据；
6. 不影响第一、第二、第三阶段已有功能。

完成后请说明：

1. 是否成功读取 UI UX Pro Max；
2. 修改了哪些文件；
3. 新增了哪些组件；
4. 路由配置是什么；
5. Token 保存在哪里；
6. 请求拦截器如何工作；
7. 路由守卫如何工作；
8. 如何启动前端；
9. 如何测试页面跳转；
10. 是否存在未完成风险。

# 阶段2提示词：实现登录注册页面与用户状态管理

你现在继续开发“智闻辨真”第四阶段用户端 Vue 前端。

本阶段目标：
实现登录页、注册页、用户状态管理、Token 保存、Token 自动携带、刷新后登录态恢复和退出登录。

本阶段只开发：

1. 登录页 /login；
2. 注册页 /register；
3. 用户状态管理；
4. 退出登录逻辑；
5. 登录后导航栏状态展示。

不要开发新闻检测页。
不要开发检测结果页。
不要开发管理员后台。
不要修改后端接口。

开始前必须先读取：

1. .codex/skills/ui-ux-pro-max/
2. design-system/MASTER.md
3. src/api
4. src/stores
5. src/router
6. src/views/LoginView.vue
7. src/views/RegisterView.vue
8. src/utils/request.js
9. src/layouts/UserLayout.vue

接口：
POST /api/auth/register
POST /api/auth/login
GET /api/auth/me

登录页要求：

1. 使用 Element Plus 表单，但必须应用项目统一设计风格；
2. 包含账号/用户名、密码输入；
3. 表单基础校验；
4. 登录按钮 loading 状态；
5. 登录失败显示后端错误信息；
6. 登录成功保存 JWT Token；
7. 登录成功后调用 GET /api/auth/me 获取当前用户信息；
8. 普通用户登录后跳转 /detect；
9. 如果返回用户 role 为 admin，可以提示“管理员账号请进入后台管理”，但本阶段不开发后台；
10. 不要把 Token 写死；
11. 不要保存明文密码。

注册页要求：

1. 使用统一风格的注册表单；
2. 包含用户名、密码、确认密码等必要字段；
3. 表单基础校验；
4. 密码和确认密码一致性校验；
5. 注册成功后提示用户去登录；
6. 注册失败显示后端错误信息；
7. 不要写死成功结果。

用户状态要求：

1. 使用 Pinia 管理 token、userInfo、isLoggedIn；
2. 刷新页面后从 localStorage 或现有存储中恢复 token；
3. 有 token 时尝试调用 /api/auth/me 恢复用户信息；
4. 退出登录时清除 token 和用户信息；
5. 请求拦截器自动携带 Authorization: Bearer token；
6. 401 时清除登录态并引导用户重新登录。

UI 要求：

1. 登录注册页不要做成普通表单页；
2. 可以使用左右分栏或居中卡片；
3. 页面要体现“可信新闻检测、RAG 证据检索、AI 辅助分析”的产品定位；
4. 不要过度花哨；
5. 移动端要能正常显示；
6. 不要出现默认 Element Plus 裸样式。

完成后请说明：

1. 是否成功读取 UI UX Pro Max；
2. 修改了哪些文件；
3. 登录流程是什么；
4. 注册流程是什么；
5. Token 是否会自动带到请求头；
6. 刷新页面后登录态如何恢复；
7. 如何测试注册；
8. 如何测试登录；
9. 是否存在未完成风险。

# 阶段3提示词：实现新闻检测页和检测结果页

你现在继续开发“智闻辨真”第四阶段用户端 Vue 前端。

本阶段是第四阶段最核心任务。

目标：
实现新闻检测页 /detect 和检测结果页 /result/:id。检测结果页必须做成系统答辩展示的核心页面。

本阶段只开发：

1. 新闻检测页 /detect；
2. 检测结果页 /result/:id；
3. 两个页面需要用到的公共组件。

不要开发管理员后台。
不要修改后端接口。
不要在前端计算评分。
不要调用 DeepSeek。
不要写死复杂假数据。

开始开发前，必须先读取：

1. .codex/skills/ui-ux-pro-max/
2. design-system/MASTER.md
3. src/api
4. src/router
5. src/stores
6. src/components
7. src/styles
8. src/views/DetectView.vue
9. src/views/ResultView.vue

如果没有读取到 UI UX Pro Max 或 design-system/MASTER.md，请停止开发并说明原因。

一、新闻检测页 /detect

接口：
POST /api/detect/news

功能要求：

1. 输入新闻标题；
2. 输入新闻正文；
3. 可选新闻类别；
4. 提交按钮调用 POST /api/detect/news；
5. 提交时显示 loading；
6. 检测成功后跳转 /result/:id；
7. 检测失败时显示后端错误信息；
8. 支持游客检测；
9. 支持登录用户检测；
10. 提供“填充示例新闻”按钮，用于演示；
11. 页面展示免责声明；
12. 不要在前端自己计算可信度评分；
13. 所有评分和风险等级以后端返回为准。

免责声明文案：
本系统为新闻可信度辅助评估工具，检测结果仅供参考，不能替代人工事实核查、官方通报或权威媒体结论。

新闻检测页布局要求：

1. 顶部有页面标题和简短说明；
2. 输入表单使用卡片承载；
3. 可以在右侧或下方展示检测流程说明；
4. 检测流程可展示为：

   * 文本输入
   * 证据检索
   * DeepSeek 分析
   * 规则评分
   * 综合评估
5. 检测按钮要突出；
6. loading 状态要明显；
7. 错误提示要清晰；
8. 页面整体体现“AI 风控检测平台”的专业感；
9. 不要把页面做成普通 textarea + button。

游客检测结果处理要求：
检测成功后，将后端返回的完整检测结果保存到 sessionStorage。
key 使用：
detection_result_${detection_id}

进入 /result/:id 后：

1. 优先从 sessionStorage 读取 detection_result_${id}；
2. 如果 sessionStorage 有数据，直接展示；
3. 如果 sessionStorage 没有数据，再调用 GET /api/detect/{id}；
4. 这样可以保证游客检测成功后也能正常看到结果页。

二、检测结果页 /result/:id

接口：
GET /api/detect/{id}

页面必须展示：

1. 新闻标题；
2. 检测时间；
3. final_score 可信度评分；
4. evidence_score 检索证据相关度评分；
5. llm_score 大模型判断评分；
6. rule_score 来源/规则评分；
7. risk_level 风险等级；
8. judgement_result 判断结论；
9. reason 判断理由；
10. risk_points 风险点；
11. keywords 关键词；
12. evidence_list 检索证据 Top10；
13. similar_news 相似新闻；
14. suggestion 辟谣建议；
15. agent_steps AI 分析过程；
16. disclaimer 免责声明；
17. PDF 报告下载入口。

检测结果页核心布局要求：

1. 顶部区域展示新闻标题、检测时间、报告按钮；
2. 第一屏核心展示 final_score 和 risk_level；
3. 使用大号分数卡片展示 final_score；
4. 使用明显颜色区分风险等级；
5. 三项分数 evidence_score、llm_score、rule_score 用并列 ScoreCard 展示；
6. judgement_result、reason、suggestion 分区展示；
7. risk_points 和 keywords 使用标签或列表展示；
8. evidence_list 使用 EvidenceList 组件展示；
9. similar_news 与 evidence_list 做清晰区分；
10. agent_steps 使用步骤条展示；
11. disclaimer 放在页面底部；
12. 不要把所有字段平铺成一长串纯文字；
13. 页面要适合答辩截图展示。

PDF 报告按钮要求：

1. 如果后端返回 report_url，则显示“下载报告”按钮；
2. 如果没有 report_url，不要调用不存在的接口；
3. 可以显示“报告功能待开放”或“报告生成中”；
4. 不要假装 PDF 已经生成。

字段兼容要求：

1. 如果后端字段为空，页面不能报错；
2. risk_points、keywords、evidence_list、similar_news、agent_steps 为空时显示空状态；
3. 时间字段要格式化；
4. 分数字段要保留合理小数；
5. evidence_list 如果字段名与后端略有差异，要做安全兼容；
6. 不要因为字段缺失导致白屏。

建议复用或新增组件：

1. ScoreCard.vue
2. RiskLevelTag.vue
3. EvidenceList.vue
4. AgentSteps.vue
5. PageHeader.vue
6. EmptyState.vue
7. LoadingState.vue
8. ResultSection.vue

完成后请说明：

1. 是否成功读取 UI UX Pro Max；
2. 修改了哪些文件；
3. 新增了哪些组件；
4. /detect 如何调用接口；
5. /result/:id 如何读取检测详情；
6. 游客检测结果如何展示；
7. PDF 报告按钮如何处理；
8. 如何运行前端；
9. 如何测试这两个页面；
10. 是否存在未完成风险。

# 阶段4提示词：实现历史记录页面

你现在继续开发“智闻辨真”第四阶段用户端 Vue 前端。

本阶段目标：
实现普通用户历史记录页 /history。

本阶段只开发普通用户历史记录页。
不要调用管理员接口。
不要开发管理员后台。
不要修改后端接口。

开始前必须先读取：

1. .codex/skills/ui-ux-pro-max/
2. design-system/MASTER.md
3. src/api
4. src/router
5. src/stores
6. src/components
7. src/views/HistoryView.vue
8. src/styles

接口：
GET /api/detect/history

功能要求：

1. 登录用户可以查看自己的检测历史；
2. 未登录用户访问 /history 时，引导到登录页；
3. 使用 Element Plus 表格，但必须应用统一设计风格；
4. 字段包括：

   * 新闻标题
   * 检测时间
   * final_score 可信度评分
   * risk_level 风险等级
   * 是否高风险
   * 报告下载状态
   * 查看详情
5. 支持按风险等级筛选；
6. 支持关键词搜索；
7. 支持分页；
8. 点击查看详情跳转 /result/:id；
9. 普通用户只展示自己的记录；
10. 不要调用 /api/admin/detections；
11. 不要在前端私自计算评分；
12. 不要写大量假数据。

页面 UI 要求：

1. 页面顶部使用 PageHeader；
2. 筛选区使用卡片承载；
3. 表格区域要清晰；
4. 风险等级使用 RiskLevelTag；
5. 分数可以使用简洁的进度条或数字展示；
6. 空状态使用 EmptyState；
7. 加载状态使用 LoadingState；
8. 表格不要拥挤；
9. 操作按钮要统一；
10. 不要出现默认 Element Plus 裸样式。

字段兼容要求：

1. 如果接口分页字段与预期不一致，要做安全兼容；
2. 如果列表为空，显示空状态；
3. 如果 report_url 为空，显示“暂未生成”；
4. 如果 title 过长，需要省略显示，详情页展示完整内容；
5. 时间字段需要格式化。

完成后请说明：

1. 是否成功读取 UI UX Pro Max；
2. 修改了哪些文件；
3. 表格字段有哪些；
4. 筛选逻辑如何实现；
5. 分页逻辑如何实现；
6. 如何跳转详情页；
7. 如何测试历史记录；
8. 是否存在未完成风险。

# 阶段5提示词：实现高风险新闻展示页和个人中心

你现在继续开发“智闻辨真”第四阶段用户端 Vue 前端。

本阶段目标：
实现高风险新闻展示页 /high-risk 和个人中心 /profile。

本阶段只开发：

1. 高风险新闻展示页；
2. 个人中心页。

不要开发管理员后台。
不要修改后端接口。
不要编造大量假数据。

开始前必须先读取：

1. .codex/skills/ui-ux-pro-max/
2. design-system/MASTER.md
3. src/api
4. src/router
5. src/stores
6. src/components
7. src/views/HighRiskView.vue
8. src/views/ProfileView.vue
9. src/styles

一、高风险新闻展示页 /high-risk

优先使用接口：
GET /api/high-risk

如果后端尚未实现该接口：

1. 不要硬造大量假数据；
2. 页面显示优雅空状态；
3. 标注“高风险新闻统计接口待接入”；
4. 保留后续接口接入位置。

页面功能要求：

1. 展示最新高风险新闻；
2. 展示高风险新闻排行榜；
3. 展示高频风险关键词；
4. 展示高风险类别分布；
5. 敏感内容只展示摘要，不展示过长正文；
6. 点击可查看详情，如果存在 detection_id，则跳转 /result/:id；
7. 页面底部加免责声明，避免误导。

ECharts 使用要求：

1. 如果有真实统计数据，可以使用 ECharts 展示类别分布或关键词统计；
2. 如果没有真实数据，不要硬造图表；
3. 没有数据时显示 EmptyState；
4. 图表风格要和整体 UI 统一。

二、个人中心 /profile

功能要求：

1. 展示当前用户基本信息；
2. 展示用户名、角色、注册时间或创建时间；
3. 展示检测次数；
4. 展示高风险检测数量；
5. 展示报告数量；
6. 提供退出登录按钮；
7. 可以提供快捷入口：

   * 去检测新闻
   * 查看历史记录
   * 查看高风险新闻
8. 如果统计接口没有实现，不要编造数据，可以显示“待统计”或空状态。

个人中心接口：
优先使用：
GET /api/auth/me

如果没有用户统计接口，则不要调用不存在的接口。

UI 要求：

1. 个人中心不要做成简单文字列表；
2. 使用用户信息卡片 + 统计卡片 + 快捷操作；
3. 页面风格与用户端一致；
4. 退出登录按钮要有确认提示；
5. 空数据要有合理提示；
6. 不要出现默认 Element Plus 裸样式。

完成后请说明：

1. 是否成功读取 UI UX Pro Max；
2. 修改了哪些文件；
3. 高风险新闻页调用了哪些接口；
4. 哪些数据来自真实接口；
5. 哪些数据是待后端补充；
6. 个人中心展示了哪些用户信息；
7. 如何测试；
8. 是否存在未完成风险。

# 阶段6提示词：用户端 UI 统一优化与前端自测

你现在作为前端 UI/UX 审查员和代码审查员，基于 UI UX Pro Max、design-system/MASTER.md，对第四阶段用户端 Vue 页面进行统一优化和自测。

本阶段可以修改前端样式和页面结构，但不要修改后端接口和后端业务逻辑。

开始前必须先读取：

1. .codex/skills/ui-ux-pro-max/
2. design-system/MASTER.md
3. src/router
4. src/views
5. src/components
6. src/api
7. src/stores
8. src/styles
9. src/utils

检查范围：

1. 首页；
2. 登录页；
3. 注册页；
4. 新闻检测页；
5. 检测结果页；
6. 历史记录页；
7. 高风险新闻页；
8. 个人中心；
9. 公共组件；
10. 路由守卫；
11. Axios 请求封装；
12. Pinia 用户状态。

UI/UX 检查重点：

1. 是否遵守 UI UX Pro Max；
2. 是否遵守 design-system/MASTER.md；
3. 页面是否统一；
4. 是否存在默认 Element Plus 裸样式；
5. 是否存在页面过于空洞；
6. 是否存在按钮、卡片、表格、标签风格不一致；
7. 风险等级颜色是否统一；
8. 结果页是否足够适合答辩展示；
9. 检测流程是否清晰；
10. 空状态和加载状态是否美观；
11. 移动端是否基本可用；
12. 页面文案是否正式自然。

功能检查重点：

1. 注册是否可用；
2. 登录是否可用；
3. Token 是否正确保存；
4. 请求是否自动携带 Token；
5. 刷新页面后登录态是否恢复；
6. 游客是否可以进入 /detect；
7. 游客检测后是否可以查看本次结果；
8. 登录用户检测后是否可以查看历史；
9. 未登录访问 /history 和 /profile 是否会被拦截；
10. 检测结果页字段为空是否会白屏；
11. 历史记录分页和筛选是否正常；
12. PDF 报告按钮是否没有调用不存在接口；
13. 高风险页无数据时是否显示空状态；
14. 个人中心无统计接口时是否有合理占位。

代码检查重点：

1. 是否存在大量硬编码假数据；
2. 是否在前端私自计算 final_score；
3. 是否在前端私自生成 risk_level；
4. 是否重复封装 Axios；
5. 是否存在没有处理的异常；
6. 是否存在未使用的组件；
7. 是否存在路由命名混乱；
8. 是否影响后续管理员后台开发；
9. 是否有明显控制台报错；
10. 是否有明显 ESLint 或构建错误。

请完成：

1. 修复发现的前端问题；
2. 统一页面视觉风格；
3. 优化结果页展示效果；
4. 优化空状态和加载状态；
5. 确保 npm run dev 可以正常运行；
6. 如果项目有 build 命令，运行 npm run build 检查构建。

完成后请输出审查报告：

1. 是否成功读取 UI UX Pro Max；
2. 修改了哪些文件；
3. 修复了哪些 UI 问题；
4. 修复了哪些功能问题；
5. 当前页面是否满足第四阶段验收标准；
6. 如何启动项目；
7. 如何逐页测试；
8. 是否存在未完成风险。

# 阶段7提示词：第四阶段最终代码审查

请作为前端代码审查员，检查“智闻辨真”第四阶段用户端 Vue 代码。

本阶段只输出审查报告，不要直接修改代码。

请先读取：

1. .codex/skills/ui-ux-pro-max/
2. design-system/MASTER.md
3. docs/01_project_design.md
4. docs/03_api_design.md
5. src/router
6. src/views
7. src/components
8. src/api
9. src/stores
10. src/styles

审查范围：

1. 首页；
2. 登录页；
3. 注册页；
4. 新闻检测页；
5. 检测结果页；
6. 历史记录页；
7. 高风险新闻页；
8. 个人中心；
9. 公共组件；
10. Axios 请求封装；
11. Token 处理；
12. 路由守卫；
13. Pinia 用户状态。

重点检查：

1. 是否成功遵守 UI UX Pro Max；
2. 页面是否仍然像默认 Element Plus 裸样式；
3. 页面风格是否统一；
4. 检测结果页是否适合作为系统演示核心页面；
5. 是否把后端返回字段写错；
6. 是否在前端私自计算 final_score；
7. 是否在前端私自生成 risk_level；
8. Token 是否正确保存和携带；
9. 刷新页面后登录状态是否丢失；
10. 未登录是否能访问需要登录的页面；
11. 游客检测后是否能查看本次结果；
12. 检测结果页是否存在字段为空导致报错；
13. 历史记录是否错误调用管理员接口；
14. 是否存在大量硬编码假数据；
15. PDF 报告按钮是否调用了不存在接口；
16. 高风险新闻页没有接口时是否优雅降级；
17. 个人中心没有统计接口时是否优雅展示；
18. 是否影响后续管理员后台开发；
19. 是否存在控制台报错；
20. 是否可以正常启动和构建。

请输出审查报告，格式如下：

1. 总体结论：是否通过第四阶段验收；
2. 严重问题：阻断验收的问题；
3. 中等问题：建议进入下一阶段前修复的问题；
4. 轻微问题：不阻断但建议优化的问题；
5. UI/UX 评价：是否符合 UI UX Pro Max；
6. 功能完整性评价；
7. 接口联调评价；
8. 权限与 Token 评价；
9. 对第五阶段管理员后台开发的影响；
10. 建议下一步工作。
