# 05_project_structure.md

# 智闻辨真项目目录结构说明

> 项目名称：智闻辨真：基于 RAG 与大语言模型的新闻可信度评估系统  
> 技术栈：FastAPI + Vue3 + Element Plus + MySQL + Chroma + DeepSeek API  
> 本文档用于规范项目目录结构，防止 Codex 在开发过程中随意创建文件、混乱分层或破坏项目结构。

---

## 1. 项目总目录结构

建议项目根目录命名为：

```text
zhiyun-bianzhen/
```

完整目录建议如下：

```text
zhiyun-bianzhen/
├── backend/                         # 后端 FastAPI 项目
│   ├── app/
│   │   ├── api/                     # 路由接口层
│   │   │   ├── v1/
│   │   │   │   ├── auth.py          # 登录注册、JWT 认证接口
│   │   │   │   ├── users.py         # 用户管理接口
│   │   │   │   ├── detect.py        # 新闻检测接口
│   │   │   │   ├── rag.py           # RAG 检索接口
│   │   │   │   ├── knowledge.py     # 知识库管理接口
│   │   │   │   ├── prompts.py       # Prompt 模板管理接口
│   │   │   │   ├── high_risk.py     # 高风险新闻接口
│   │   │   │   ├── reports.py       # 报告生成与下载接口
│   │   │   │   ├── statistics.py    # 数据统计接口
│   │   │   │   └── logs.py          # 系统日志接口
│   │   │   └── router.py            # API 路由统一注册
│   │   ├── core/                    # 核心配置层
│   │   │   ├── config.py            # 环境变量与项目配置
│   │   │   ├── security.py          # JWT、密码加密、权限校验
│   │   │   └── deps.py              # FastAPI 依赖注入
│   │   ├── db/                      # 数据库连接层
│   │   │   ├── session.py           # MySQL 数据库连接
│   │   │   ├── base.py              # SQLAlchemy Base
│   │   │   └── init_db.py           # 初始化数据库数据
│   │   ├── models/                  # SQLAlchemy ORM 模型
│   │   │   ├── user.py
│   │   │   ├── knowledge_item.py
│   │   │   ├── detection_record.py
│   │   │   ├── evidence_match.py
│   │   │   ├── prompt_template.py
│   │   │   ├── high_risk_news.py
│   │   │   ├── report.py
│   │   │   └── system_log.py
│   │   ├── schemas/                 # Pydantic 请求和响应模型
│   │   │   ├── auth.py
│   │   │   ├── user.py
│   │   │   ├── knowledge.py
│   │   │   ├── detect.py
│   │   │   ├── rag.py
│   │   │   ├── prompt.py
│   │   │   ├── high_risk.py
│   │   │   ├── report.py
│   │   │   └── statistics.py
│   │   ├── crud/                    # 数据库 CRUD 操作层
│   │   │   ├── user.py
│   │   │   ├── knowledge.py
│   │   │   ├── detection.py
│   │   │   ├── prompt.py
│   │   │   ├── high_risk.py
│   │   │   ├── report.py
│   │   │   └── log.py
│   │   ├── services/                # 业务服务层
│   │   │   ├── auth_service.py      # 认证业务
│   │   │   ├── detect_service.py    # 新闻检测主流程
│   │   │   ├── rag_service.py       # RAG 检索业务
│   │   │   ├── chroma_service.py    # Chroma 向量库封装
│   │   │   ├── embedding_service.py # 文本向量化服务
│   │   │   ├── llm_service.py       # DeepSeek API 调用
│   │   │   ├── scoring_service.py   # 可信度评分计算
│   │   │   ├── rule_service.py      # 风险规则评分
│   │   │   ├── agent_service.py     # 轻量 Agent 流程编排
│   │   │   ├── report_service.py    # HTML/PDF 报告生成
│   │   │   └── statistics_service.py# 数据统计服务
│   │   ├── utils/                   # 工具函数
│   │   │   ├── response.py          # 统一响应格式
│   │   │   ├── exceptions.py        # 自定义异常
│   │   │   ├── text_cleaner.py      # 文本清洗
│   │   │   ├── keyword_extractor.py # 关键词提取
│   │   │   └── time_utils.py        # 时间处理
│   │   ├── templates/               # 报告 HTML 模板
│   │   │   └── report_template.html
│   │   ├── static/                  # 后端静态资源
│   │   │   └── reports/             # PDF 报告输出目录
│   │   └── main.py                  # FastAPI 应用入口
│   ├── tests/                       # 后端测试
│   │   ├── test_auth.py
│   │   ├── test_knowledge.py
│   │   ├── test_rag.py
│   │   └── test_detect.py
│   ├── chroma_db/                   # Chroma 本地持久化目录
│   ├── alembic/                     # 数据库迁移目录，可选
│   ├── requirements.txt             # Python 依赖
│   ├── .env.example                 # 环境变量示例
│   └── README.md                    # 后端说明
│
├── frontend/                        # 前端 Vue3 项目
│   ├── public/
│   ├── src/
│   │   ├── api/                     # Axios 接口封装
│   │   │   ├── auth.js
│   │   │   ├── detect.js
│   │   │   ├── knowledge.js
│   │   │   ├── prompt.js
│   │   │   ├── highRisk.js
│   │   │   ├── report.js
│   │   │   └── statistics.js
│   │   ├── assets/                  # 图片、图标、样式资源
│   │   ├── components/              # 通用组件
│   │   │   ├── RiskTag.vue
│   │   │   ├── ScoreCard.vue
│   │   │   ├── EvidenceList.vue
│   │   │   ├── AgentSteps.vue
│   │   │   └── PageHeader.vue
│   │   ├── layouts/                 # 页面布局
│   │   │   ├── UserLayout.vue
│   │   │   └── AdminLayout.vue
│   │   ├── router/                  # 路由
│   │   │   └── index.js
│   │   ├── stores/                  # Pinia 状态管理
│   │   │   ├── auth.js
│   │   │   └── user.js
│   │   ├── utils/                   # 前端工具函数
│   │   │   ├── request.js           # Axios 实例
│   │   │   ├── auth.js              # Token 处理
│   │   │   └── format.js            # 格式化工具
│   │   ├── views/
│   │   │   ├── user/                # 用户端页面
│   │   │   │   ├── Home.vue
│   │   │   │   ├── Login.vue
│   │   │   │   ├── Register.vue
│   │   │   │   ├── Detect.vue
│   │   │   │   ├── Result.vue
│   │   │   │   ├── History.vue
│   │   │   │   ├── HighRisk.vue
│   │   │   │   └── Profile.vue
│   │   │   └── admin/               # 管理员后台页面
│   │   │       ├── Dashboard.vue
│   │   │       ├── Users.vue
│   │   │       ├── Detections.vue
│   │   │       ├── Knowledge.vue
│   │   │       ├── Prompts.vue
│   │   │       ├── HighRiskManage.vue
│   │   │       ├── Statistics.vue
│   │   │       ├── Reports.vue
│   │   │       └── Logs.vue
│   │   ├── App.vue
│   │   └── main.js
│   ├── package.json
│   ├── vite.config.js
│   └── README.md
│
├── docs/                            # 项目设计与 Codex 开发文档
│   ├── 01_project_design.md
│   ├── 02_database_design.md
│   ├── 03_api_design.md
│   ├── 04_development_tasks.md
│   ├── 05_project_structure.md
│   └── 06_phase1_prompts.md
│
├── data/                            # 演示数据
│   ├── knowledge_seed.csv
│   ├── knowledge_seed.json
│   └── fake_news_examples.json
│
├── screenshots/                     # 系统截图，后续写课程报告使用
│   ├── user/
│   └── admin/
│
├── README.md                        # 项目总说明
└── .gitignore
```

---

## 2. 后端目录说明

后端采用典型 FastAPI 分层结构。

### 2.1 api 层

`app/api/v1/` 只负责接收请求、校验权限、调用 service，不写复杂业务逻辑。

示例职责：

```text
auth.py       登录注册接口
detect.py     新闻检测接口
knowledge.py  知识库管理接口
rag.py        RAG 检索接口
prompts.py    Prompt 模板接口
```

禁止在 api 层直接写大模型调用、Chroma 操作、复杂评分逻辑。

---

### 2.2 core 层

`app/core/` 存放系统核心配置。

```text
config.py      读取 .env 配置，例如数据库地址、DeepSeek API Key
security.py    密码加密、JWT 生成和解析
deps.py        获取当前用户、管理员权限校验
```

---

### 2.3 db 层

`app/db/` 负责数据库连接。

```text
session.py     创建 SQLAlchemy Session
base.py        注册所有 ORM Model
init_db.py     初始化管理员账号、默认 Prompt
```

---

### 2.4 models 层

`app/models/` 定义 MySQL 表结构对应的 SQLAlchemy ORM。

每张表一个文件，避免所有模型堆在一个文件中。

---

### 2.5 schemas 层

`app/schemas/` 定义请求参数和响应数据。

示例：

```text
LoginRequest
TokenResponse
NewsDetectRequest
NewsDetectResponse
KnowledgeCreate
KnowledgeUpdate
```

---

### 2.6 crud 层

`app/crud/` 只负责数据库增删改查，不负责业务判断。

示例：

```text
crud/user.py        用户表 CRUD
crud/knowledge.py   知识库表 CRUD
crud/detection.py   检测记录 CRUD
```

---

### 2.7 services 层

`app/services/` 是项目核心业务层。

其中最重要的是：

```text
detect_service.py     新闻检测主流程
rag_service.py        RAG 检索流程
chroma_service.py     Chroma 向量数据库操作
llm_service.py        DeepSeek API 调用
scoring_service.py    可信度评分计算
agent_service.py      轻量 Agent 流程编排
report_service.py     HTML/PDF 报告生成
```

Codex 开发时必须优先保持 service 层清晰，不要把所有代码塞到接口文件里。

---

## 3. 前端目录说明

前端采用 Vue3 + Element Plus + ECharts。

### 3.1 api 目录

`src/api/` 专门封装后端接口请求。

示例：

```text
auth.js          登录注册接口
detect.js        新闻检测接口
knowledge.js     知识库接口
statistics.js    数据统计接口
```

页面中不要直接写 axios 请求，应统一从 api 文件调用。

---

### 3.2 components 目录

`src/components/` 放可复用组件。

重点组件：

```text
RiskTag.vue        风险等级标签
ScoreCard.vue      可信度评分卡片
EvidenceList.vue   检索证据列表
AgentSteps.vue     AI 分析过程步骤条
PageHeader.vue     页面标题组件
```

这些组件能提升前端复用性，也方便后续美化。

---

### 3.3 views/user 目录

用户端页面：

```text
Home.vue       首页
Detect.vue     新闻检测页
Result.vue     检测结果页
History.vue    历史记录页
HighRisk.vue   高风险新闻展示页
Profile.vue    个人中心
```

检测结果页是用户端最重要页面，需要优先美化。

---

### 3.4 views/admin 目录

管理员后台页面：

```text
Dashboard.vue       后台首页
Users.vue           用户管理
Detections.vue      检测记录管理
Knowledge.vue       知识库管理
Prompts.vue         Prompt 模板管理
Statistics.vue      数据统计页
Reports.vue         报告管理
Logs.vue            系统日志
```

后台统一使用侧边栏布局，建议科技蓝白风。

---

## 4. docs 目录说明

`docs/` 是给你和 Codex 共同使用的开发说明书。

```text
01_project_design.md        项目总体设计
02_database_design.md       数据库设计
03_api_design.md            接口设计
04_development_tasks.md     开发任务清单
05_project_structure.md     项目目录结构说明
06_phase1_prompts.md        第一阶段开发提示词合集
```

Codex 每次开发前，都应先阅读相关文档。

---

## 5. data 目录说明

`data/` 存放演示数据和知识库种子数据。

建议准备：

```text
knowledge_seed.csv       知识库初始化数据
knowledge_seed.json      JSON 格式知识库数据
fake_news_examples.json  谣言示例数据
```

第一阶段可以先准备 30 条数据，后续扩展到 100 条。

---

## 6. screenshots 目录说明

`screenshots/` 用于保存课程报告和答辩 PPT 所需截图。

建议按模块保存：

```text
screenshots/user/
screenshots/admin/
```

常见截图包括：

```text
登录页
首页
新闻检测页
检测结果页
PDF 报告
历史记录页
后台首页
知识库管理
Prompt 模板管理
数据统计页
```

---

## 7. Codex 开发纪律

后续使用 Codex 时，必须遵守以下原则：

```text
1. 不允许随意更换技术栈。
2. 不允许一次性生成完整系统。
3. 每次只开发一个模块。
4. 修改前说明要改哪些文件。
5. 修改后说明每个文件作用。
6. 不允许随意改接口路径。
7. 不允许随意改数据库字段。
8. 不允许把 API Key 写死在代码里。
9. 不允许删除已有功能。
10. 必须给出运行方式和测试方法。
```

---

## 8. 推荐开发顺序

```text
阶段 1：后端基础框架
阶段 2：用户注册登录与 JWT
阶段 3：知识库 MySQL 管理
阶段 4：Chroma 向量检索
阶段 5：DeepSeek API 调用
阶段 6：新闻检测主流程
阶段 7：用户端前端页面
阶段 8：管理员后台页面
阶段 9：PDF 报告生成
阶段 10：数据可视化与答辩优化
```

第一阶段不要急着做前端，也不要急着做完整 RAG。  
先保证后端结构、数据库连接、认证机制和 Swagger 文档正常运行。

---

## 9. 给 Codex 的目录约束提示词

后续可以复制下面这段给 Codex：

```text
请严格按照 docs/05_project_structure.md 中定义的项目目录结构进行开发。

要求：
1. 不要随意创建无关目录；
2. 不要把所有代码写在 main.py；
3. api 层只写接口，复杂业务必须放到 services 层；
4. 数据库操作放到 crud 层；
5. ORM 模型放到 models 层；
6. Pydantic 模型放到 schemas 层；
7. 配置读取放到 core/config.py；
8. JWT 和密码加密放到 core/security.py；
9. 前端接口请求统一放到 src/api；
10. 页面组件尽量拆分到 src/components。

本次开发前，请先说明你准备新增或修改哪些文件。
```
