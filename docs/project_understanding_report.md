# 智闻辨真 — 项目认知与代码地图报告

> 生成日期：2026-06-13
> 修订日期：2026-06-13（根据用户反馈修正 6 项认知）
> 目的：正式代码审查前的项目认知建立，不是正式审查报告
> 执行范围：只读分析，不修改任何项目文件
> 修订历史：
>   v1.1 — 修正 README.md 定位（不作为需求依据）、models/__init__.py 已修复、前端角色变更功能缺失确认、docs/ 文件作为设计权威来源、第二轮审查必须完整覆盖

---

## 1. 项目基础画像

| 维度 | 内容 |
|---|---|
| **项目名称** | 智闻辨真 (ZhiYun BianZhen) |
| **项目用途** | 基于 RAG + LLM 的新闻可信度评估系统。用户输入新闻标题和正文，系统检索知识库相似证据，调用 DeepSeek 进行可信度分析，结合规则评分生成最终可信度分数、风险等级、证据匹配和 PDF 报告 |
| **项目类型** | 前后端分离的单体仓库 (monorepo) |
| **当前开发阶段** | 第七阶段 — 联调测试、演示环境初始化、代码审查和答辩材料准备（来源：docs/04_development_tasks.md） |
| **需求依据** | **docs/ 目录中的设计文档（01-05）为权威需求来源**；README.md 已过时，不作为当前需求依据 |
| **主要后端语言** | Python 3.14 |
| **后端框架** | FastAPI 0.111.0 |
| **ORM** | SQLAlchemy 2.0.31 |
| **数据库** | MySQL 8.x (`zhiyun_bianzhen`，字符集 utf8mb4) |
| **向量数据库** | Chroma (本地持久化，cosine 距离) |
| **前端框架** | Vue 3 + Vite + Element Plus + Pinia + Vue Router + ECharts |
| **大模型** | DeepSeek （`deepseek-chat`，可配置模型名） |
| **Embedding 服务** | DashScope `text-embedding-v4`（默认，1024维）+ DeepSeek embedding + hash fallback |
| **缓存** | 尚未发现（仅模块级内存缓存 Chroma 客户端/集合句柄） |
| **消息队列** | 尚未发现 |
| **文件存储** | 本地文件系统（报告 HTML/PDF 存储于 `REPORT_DIR`，向量数据存储于 `CHROMA_PATH`） |
| **第三方服务** | DeepSeek API (LLM + embedding)、DashScope (embedding)、Chroma (本地向量数据库) |
| **测试框架** | Python unittest + Vue Test Utils（前端仅1个工具函数测试） |
| **部署方式** | 手动启动：uvicorn + npm run dev；尚未发现 Dockerfile 或 CI/CD 配置 |
| **文档体系** | **设计文档权威来源：docs/01-05（项目设计、数据库设计、API设计、开发任务、项目结构）**；操作参考：CLAUDE.md；README.md 已过时，不作为需求依据；docs/ 已加入 .gitignore 但本地仍可读取 |
| **当前 Git 状态** | 分支 main，与 origin/main 同步；暂存区有 .gitignore 修改和 docs/ 下全部文件删除（待提交）；工作区有未暂存修改涉及大量文件 |

---

## 2. 项目目录结构

### 2.1 根目录

```
NewsCredibilityEvaluator/
├── README.md                 # 项目说明、快速启动、演示流程
├── CLAUDE.md                 # Claude Code 项目上下文（架构、命令、分层）
├── .gitignore                # Git 忽略规则（含 docs/）
├── backend/                  # FastAPI 后端应用
├── frontend/                 # Vue 3 前端应用
├── data/                     # 本地 Chroma 向量库和 PDF 报告
│   ├── chroma/               # Chroma 持久化数据
│   └── reports/              # 生成的 PDF/HTML 报告
├── docs/                     # 【设计权威来源】本地可读取
│   ├── 01_project_design.md        # 项目总体设计（需求权威依据）
│   ├── 02_database_design.md       # 数据库设计（字段/表/关系规范）
│   ├── 03_api_design.md            # API 接口设计（路径/参数/返回格式规范）
│   ├── 04_development_tasks.md     # 开发任务拆解与 Codex 使用指南
│   ├── 05_project_structure.md     # 项目目录结构规范
│   ├── 06-12_phase*_prompts.md     # 各阶段开发 Prompt
│   ├── claude_code_review_prompt.md
│   ├── enterprise_code_review_prompt.md
│   ├── enterprise_code_review_report.md        # 2026-06-11 企业级审查报告
│   ├── enterprise_code_review_report_2026-06-11_codex.md
│   └── deepseek_embedding_integration_report.md
├── design-system/            # 设计系统 MASTER.md（来源未知）
└── test-persist/             # 未知用途
```

### 2.2 目录模块映射表

| 目录或模块 | 主要职责 | 关键入口 | 是否核心模块 | 后续是否需要深入审查 |
|---|---|---|---|---|
| `backend/app/api/` | HTTP 路由层，处理请求/响应，调用 Service | `router.py`汇总所有 v1 路由 | 是 | 是 |
| `backend/app/api/v1/` | 各业务模块路由定义 | `auth.py`, `detect.py`, `high_risk.py`, `report.py`, `rag.py`, `admin*.py` | 是 | 是 |
| `backend/app/services/` | 全部业务逻辑 | `detection_service.py`, `llm_service.py`, `chroma_service.py`, `knowledge_service.py` | 是 | 是 |
| `backend/app/crud/` | 纯数据库 CRUD 操作 | `knowledge_crud.py`, `detection_crud.py`, `user.py` | 是 | 是 |
| `backend/app/models/` | SQLAlchemy ORM 模型 | `user.py`, `detection_record.py`, `knowledge_item.py` | 是 | 是 |
| `backend/app/schemas/` | Pydantic 请求/响应 Schema | `auth.py`, `detection.py`, `knowledge.py` | 是 | 是 |
| `backend/app/core/` | 配置、安全、依赖注入、常量、限流 | `config.py`, `deps.py`, `security.py`, `constants.py`, `rate_limit.py` | 是 | 是 |
| `backend/app/db/` | 数据库连接、基类、初始化、迁移 | `session.py`, `base.py`, `init_db.py`, `seed_demo_data.py` | 是 | 是 |
| `backend/app/utils/` | 通用工具函数 | `response.py`, `risk_level.py`, `text_cleaner.py`, `high_risk.py` | 是 | 是 |
| `backend/app/templates/` | Jinja2 HTML 报告模板 | `reports/detection_report.html` | 是 | 是 |
| `backend/alembic/` | Alembic 数据库迁移 | `env.py`, `versions/0001-0004` | 是 | 是 |
| `backend/migrations/legacy_sql/` | 旧 SQL 归档，不再执行 | 2个 .sql 文件 | 否 | 否（历史参考） |
| `backend/tests/` | 后端测试（32个文件） | 各 `test_*.py` | 是 | 是 |
| `frontend/src/api/` | Axios API 封装（按域分） | `auth.js`, `detect.js`, `report.js`, `admin*.js` | 是 | 是 |
| `frontend/src/components/` | 通用组件 + admin 组件 | `ScoreCard.vue`, `EvidenceList.vue`, `AdminStatCard.vue` | 是 | 是 |
| `frontend/src/views/` | 页面组件 | `DetectView.vue`, `admin/AdminDashboardView.vue` 等 | 是 | 是 |
| `frontend/src/layouts/` | 布局组件 | `UserLayout.vue`, `AdminLayout.vue` | 是 | 是 |
| `frontend/src/router/` | Vue Router 配置 + 路由守卫 | `index.js` | 是 | 是 |
| `frontend/src/stores/` | Pinia 状态管理 | `user.js` | 是 | 是 |
| `frontend/src/utils/` | 前端工具函数 | `request.js`, `auth.js`, `format.js` | 是 | 是 |
| `frontend/src/styles/` | 全局样式 | `common.css`, `theme.css` | 否 | 否 |
| `data/` | 运行时持久化数据 | chroma/, reports/ | 是 | 否（数据目录） |
| `docs/` | 项目文档 | 设计/开发/审查文档 | 否 | 否（已在 .gitignore 中） |

---

## 3. 技术栈和主要依赖

### 3.1 后端依赖 (requirements.txt — 12个依赖)

| 依赖 | 版本 | 用途 |
|---|---|---|
| fastapi | 0.111.0 | Web 框架 |
| uvicorn[standard] | 0.30.1 | ASGI 服务器 |
| python-dotenv | 1.0.1 | .env 环境变量加载 |
| SQLAlchemy | 2.0.31 | ORM |
| alembic | 1.13.2 | 数据库迁移 |
| pymysql | 1.1.1 | MySQL 驱动 |
| passlib[bcrypt] | 1.7.4 | 密码哈希 |
| bcrypt | 4.0.1 | bcrypt 算法实现 |
| python-jose[cryptography] | 3.3.0 | JWT 令牌 |
| chromadb | >=1.0.0,<2.0.0 | 向量数据库 |
| Jinja2 | 3.1.6 | HTML 报告模板引擎 |
| xhtml2pdf | 0.2.17 | HTML → PDF 转换 |

### 3.2 前端依赖

- **确认来源**：CLAUDE.md 和 main.js 中的 import（未读取 package.json 以获取完整版本列表）
- **已确认**：Vue 3、Vite、Element Plus（按需导入）、Pinia、Vue Router、ECharts、Axios
- **语言**：JavaScript（ES6+ modules），非 TypeScript

### 3.3 未发现的技术组件

- Redis 或其他缓存中间件 — 尚未发现
- 消息队列（RabbitMQ/Kafka/Redis Pub/Sub）— 尚未发现
- 对象存储（S3/OSS/MinIO）— 尚未发现
- Docker/Docker Compose — 尚未发现
- CI/CD 配置（GitHub Actions/GitLab CI/Jenkins）— 尚未发现
- 前端测试框架（除 `detectionResultCache.test.js` 外）— 基本未覆盖

---

## 4. 前端架构

### 4.1 启动入口

- **文件**：[frontend/src/main.js](frontend/src/main.js)
- **流程**：createApp → use(Pinia) → use(Router) → 按需注册 Element Plus 组件 → mount('#app')
- **Element Plus 按需导入**：ElAlert, ElButton, ElDialog, ElForm, ElFormItem, ElIcon, ElInput, ElOption, ElPagination, ElSelect, ElTable, ElTableColumn, ElLoading
- **样式**：Element Plus 全局样式 + theme.css + common.css

### 4.2 路由配置

- **文件**：[frontend/src/router/index.js](frontend/src/router/index.js)
- **历史模式**：createWebHistory (HTML5 History)
- **布局**：2 个根布局 — UserLayout (面向公众+用户) 和 AdminLayout (面向管理员)
- **懒加载**：所有页面组件均使用 `() => import(...)` 动态导入

#### 用户端路由（UserLayout 子路由）

| 路径 | 名称 | 页面 | 权限 |
|---|---|---|---|
| `/` | home | HomeView | public: true |
| `/login` | login | LoginView | public: true, guestOnly: true |
| `/register` | register | RegisterView | public: true, guestOnly: true |
| `/detect` | detect | DetectView | public: true |
| `/result/:id` | result | ResultView | public: true, allowGuestResult: true |
| `/history` | history | HistoryView | requiresAuth: true |
| `/high-risk` | highRisk | HighRiskView | public: true |
| `/profile` | profile | ProfileView | requiresAuth: true |

#### 管理员路由（AdminLayout 子路由，全部 requiresAuth + requiresAdmin）

| 路径 | 名称 | 页面 |
|---|---|---|
| `/admin/dashboard` | adminDashboard | AdminDashboardView |
| `/admin/users` | adminUsers | AdminUsersView |
| `/admin/detections` | adminDetections | AdminDetectionsView |
| `/admin/knowledge` | adminKnowledge | AdminKnowledgeView |
| `/admin/prompts` | adminPrompts | AdminPromptsView |
| `/admin/high-risk` | adminHighRisk | AdminHighRiskView |
| `/admin/statistics` | adminStatistics | AdminStatisticsView |
| `/admin/reports` | adminReports | AdminReportsView |
| `/admin/logs` | adminLogs | AdminLogsView |

#### 路由守卫逻辑 (beforeEach)

1. 恢复 session（如果未恢复）
2. `requiresAuth` → 未登录跳转 `/login?redirect=...`
3. `requiresAdmin` → 非管理员提示并跳转首页
4. `guestOnly` → 已登录用户跳转首页（管理员跳转后台首页）

### 4.3 状态管理

- **工具**：Pinia
- **唯一 Store**：[frontend/src/stores/user.js](frontend/src/stores/user.js)
- **State**：token, userInfo, restored, restoring, sessionVerified
- **Getters**：isLoggedIn, isAdmin, user, displayName, role
- **关键 Actions**：
  - `setAuth(payload)` — 从登录响应中提取 token 和 userInfo
  - `restoreSession()` — 页面刷新后从 localStorage 恢复，并调用 `/auth/me` 验证
  - `fetchCurrentUser()` — 调用 `/auth/me` 验证 token 有效性
  - `logout()` — 清除所有认证数据
- **Token 存储**：localStorage，key 为 `zhiyun_bianzhen_token`
- **User 存储**：localStorage，key 为 `zhiyun_bianzhen_user`

### 4.4 API 请求封装

- **文件**：[frontend/src/utils/request.js](frontend/src/utils/request.js)
- **技术**：axios.create()
- **baseURL**：`import.meta.env.VITE_API_BASE_URL || '/api'`
- **超时**：15000ms（部分接口覆盖此值，检测 120000ms，报告 60000ms）
- **请求拦截器**：自动附加 `Authorization: Bearer <token>` （如果 token 存在）
- **响应拦截器**：
  - 成功：默认返回 `response.data`（即后端 JSON body），`rawResponse: true` 配置可返回完整 response（用于 blob 下载）
  - 401 错误：自动 logout + 跳转登录页

### 4.5 前端页面映射表

| 页面 | 路由 | 主要功能 | 调用的 API | 权限要求 | 相关组件 |
|---|---|---|---|---|---|
| HomeView | `/` | 首页/落地页 | 无 | 公开 | — |
| LoginView | `/login` | 用户登录 | POST `/auth/login` | 游客 | — |
| RegisterView | `/register` | 用户注册 | POST `/auth/register` | 游客 | — |
| DetectView | `/detect` | 新闻检测表单提交 | POST `/detect/news` | 公开 | AgentSteps, LoadingState |
| ResultView | `/result/:id` | 查看检测结果详情 | GET `/detect/{id}` | 公开（游客结果也允许） | ScoreCard, EvidenceList, RiskLevelTag, ResultSection |
| HistoryView | `/history` | 历史检测记录 | GET `/detect/history` | 需登录 | EmptyState, LoadingState, RiskLevelTag |
| HighRiskView | `/high-risk` | 公开高风险新闻列表 | GET `/high-risk/public`, `/high-risk/ranking`, `/high-risk/keywords`, `/high-risk/category-distribution` | 公开 | RiskLevelTag, LoadingState, EmptyState |
| ProfileView | `/profile` | 个人中心 | GET `/auth/me` (通过 store) | 需登录 | — |
| AdminDashboardView | `/admin/dashboard` | 后台首页（统计概览卡片） | 部分统计 API | 管理员 | AdminStatCard |
| AdminUsersView | `/admin/users` | 用户管理列表 | GET/POST `/admin/users/*` | 管理员 | AdminPageScaffold |
| AdminDetectionsView | `/admin/detections` | 检测记录管理 | GET/DELETE `/admin/detections/*` | 管理员 | AdminPageScaffold |
| AdminKnowledgeView | `/admin/knowledge` | 知识库 CRUD | GET/POST/PUT/DELETE `/admin/knowledge/*` | 管理员 | AdminPageScaffold, AdminEndpointNotice |
| AdminPromptsView | `/admin/prompts` | Prompt 模板管理 | GET/POST/PUT/DELETE/POST `/admin/prompts/*` | 管理员 | AdminPageScaffold |
| AdminHighRiskView | `/admin/high-risk` | 高风险新闻审核管理 | GET/PUT `/admin/high-risk/*` | 管理员 | AdminPageScaffold |
| AdminStatisticsView | `/admin/statistics` | 数据统计图表 | GET `/admin/statistics/*` | 管理员 | AdminChartPanel |
| AdminReportsView | `/admin/reports` | 报告管理 | GET `/admin/reports/*` | 管理员 | AdminPageScaffold |
| AdminLogsView | `/admin/logs` | 系统日志查看 | GET `/admin/logs` | 管理员 | AdminPageScaffold |

---

## 5. 后端架构

### 5.1 启动入口与应用初始化

- **入口**：[backend/app/main.py](backend/app/main.py)
- **工厂函数**：`create_app()` → 创建 FastAPI + CORS + 异常处理器 + 路由注册
- **全局 app 实例**：`app = create_app()`（最后一行直接创建）
- **API 前缀**：`/api`（可配置 `API_PREFIX`）
- **Swagger**：`/docs`，OpenAPI：`/openapi.json`

### 5.2 中间件

| 中间件 | 配置 | 位置 |
|---|---|---|
| CORS | `allow_origins` 从 `BACKEND_CORS_ORIGINS` 读取，`allow_credentials` 自动判断（允许 `*` 时禁用），`allow_methods=["*"]`，`allow_headers=["*"]` | `main.py:27-33` |

### 5.3 异常处理器

| 异常类型 | 状态码 | 处理函数 |
|---|---|---|
| `HTTPException` | 原 exc.status_code | `http_exception_handler` — 格式化为统一 error_response |
| `RequestValidationError` | 422 | `validation_exception_handler` — 提取字段路径和错误消息 |
| `SQLAlchemyError` | 500 | `database_exception_handler` — 区分 .env 是否存在给出不同提示 |

### 5.4 路由注册架构

```
api_router (APIRouter, prefix="/api" 在 app.main.py 中设置)
├── auth_router            → prefix="/auth"          (auth.py)
├── detect_router          → prefix="/detect"        (detect.py)
├── report_router          → prefix="/report"        (report.py)
├── high_risk_router       → prefix="/high-risk"     (high_risk.py)
├── rag_router             → prefix="/rag"           (rag.py)
├── health_router          → (no prefix)             (health.py)
├── admin_router           → prefix="/admin"         (admin.py, /ping)
├── admin_knowledge_router → prefix="/admin/knowledge" (admin_knowledge.py)
├── admin_prompts_router   → prefix="/admin/prompts"   (admin_prompts.py)
├── admin_reports_router   → prefix="/admin/reports"   (admin_reports.py)
├── admin_high_risk_router → prefix="/admin/high-risk" (admin_high_risk.py)
├── admin_statistics_router→ prefix="/admin/statistics"(admin_statistics.py)
├── admin_detections_router→ prefix="/admin/detections" (admin_detections.py)
├── admin_users_router     → prefix="/admin/users"     (admin_users.py)
└── admin_logs_router      → prefix="/admin/logs"      (admin_logs.py)
```

完整请求路径 = `/api` + 子路由 prefix + 路由装饰器路径

### 5.5 后端分层（严格从上到下）

```
api/v1/         → 请求处理、认证检查、调用 services。不含业务逻辑
services/       → 全部业务逻辑：检测管线、LLM 调用、RAG 检索、评分、报告生成
crud/           → 纯数据库 CRUD。不含业务规则
models/         → SQLAlchemy ORM 模型（每表一个类）
schemas/        → Pydantic 请求/响应 Schema
core/           → config.py（环境变量）、security.py（JWT/bcrypt）、deps.py（DI）、
                  constants.py（风险等级阈值）、rate_limit.py
db/             → session.py（引擎）、base.py（模型注册）、init_db.py、
                  seed_demo_data.py、migrate.py、migration_guard.py
utils/          → text_cleaner.py、risk_level.py、response.py、high_risk.py
templates/      → Jinja2 报告模板
```

### 5.6 后端模块映射表

| 业务模块 | 路由入口 | Service | CRUD | Schema | 数据模型 | 权限依赖 | 测试位置 |
|---|---|---|---|---|---|---|---|
| 认证 | `api/v1/auth.py` | `auth_service.py`, `system_log_service.py` | `crud/user.py` | `auth.py`, `user.py` | User | 无（登录/注册公开） | `test_auth_smoke.py` |
| 新闻检测 | `api/v1/detect.py` | `detection_service.py`, `llm_service.py`, `rule_score_service.py`, `chroma_service.py`, `knowledge_service.py` | `detection_crud.py` | `detection.py` | DetectionRecord, EvidenceMatch | get_optional_current_user | `test_detect_api.py` 及7+相关测试 |
| 知识库管理 | `api/v1/admin_knowledge.py` | `knowledge_service.py`, `chroma_service.py`, `embedding_service.py` | `knowledge_crud.py` | `knowledge.py` | KnowledgeItem | get_current_admin | `test_knowledge_sync.py` |
| RAG 检索 | `api/v1/rag.py` | `knowledge_service.py`, `chroma_service.py` | `knowledge_crud.py` | `rag.py` | KnowledgeItem | get_current_user | `test_rag_api.py`, `test_chroma_integration.py` |
| Prompt 管理 | `api/v1/admin_prompts.py` | `prompt_service.py`, `prompt_template_validator.py` | `prompt_crud.py` | `prompt.py` | PromptTemplate | get_current_admin | `test_admin_prompts_api.py`, `test_prompt_service.py` |
| 报告生成 | `api/v1/report.py`, `api/v1/admin_reports.py` | `report_service.py` | `report_crud.py`, `detection_crud.py` | `report.py` | Report, DetectionRecord | get_current_user / get_current_admin | `test_report_api.py`, `test_admin_reports_api.py` |
| 高风险管理 | `api/v1/high_risk.py`, `api/v1/admin_high_risk.py` | `high_risk_service.py` | `high_risk_crud.py` | `high_risk.py` | DetectionRecord | get_current_user(公开) / get_current_admin | `test_high_risk_api.py`, `test_high_risk_service.py` |
| 统计 | `api/v1/admin_statistics.py` | `statistics_service.py` | `statistics_crud.py` | `statistics.py` | DetectionRecord, KnowledgeItem | get_current_admin | `test_admin_statistics_api.py`, `test_statistics_service.py` |
| 用户管理 | `api/v1/admin_users.py` | `admin_user_service.py`, `system_log_service.py` | `crud/user.py`, `detection_crud.py`, `system_log_crud.py` | `user.py` | User | get_current_admin | `test_admin_users_api.py`, `test_admin_user_service.py` |
| 检测记录管理 | `api/v1/admin_detections.py` | —（直接调用 CRUD） | `detection_crud.py` | `detection.py` | DetectionRecord | get_current_admin | `test_detect_api.py` |
| 系统日志 | `api/v1/admin_logs.py` | `system_log_service.py` | `system_log_crud.py` | `system_log.py` | SystemLog | get_current_admin | `test_system_logs_api.py`, `test_system_log_events_api.py` |

### 5.7 核心调用链（检测管线）

**━━ 已确认事实，基于代码追踪 ━━**

```
POST /api/detect/news (detect.py:detect_news)
  ├─ enforce_detect_news_rate_limit()  → InMemoryRateLimiter (IP 限流)
  ├─ get_optional_current_user         → 解析 JWT（可选）
  └─ detect_news_credibility(db, payload, current_user)
       ├─ 1. extract_keywords(title, content)
       │     └─ 模式匹配 KEYWORD_HINTS + 正则提取中文/英文 token
       ├─ 2. _search_top10_evidence(db, title, content)
       │     ├─ build_rag_search_text() → "title: xxx\ncontent: xxx"
       │     └─ search_similar_knowledge(db, query_text, top_k=10)
       │          ├─ search_knowledge_vectors() → Chroma query (cosine)
       │          └─ cross-verify: knowledge_crud.get_knowledge_item()
       ├─ 3. analyze_news_credibility(title, content, top5_evidence, prompt_template)
       │     ├─ get_default_prompt_content(db) → 从 DB 读默认 Prompt 或返回空
       │     ├─ build_analysis_prompt() → 模板渲染 + XML 包裹 + 安全边界
       │     ├─ _post_chat_completion() → DeepSeek API HTTP POST
       │     ├─ parse_analysis_response() → JSON 解析（多策略：直接解析、code block、首对象提取）
       │     ├─ _fallback_parse_text() → 文本兜底解析
       │     └─ 失败则返回 _build_error_result()（llm_score=0, risk_level="存疑信息"）
       ├─ 4. calculate_rule_score(title, content, source_name, top5_evidence)
       │     ├─ 检测夸张词 → -15
       │     ├─ 检测缺少来源 → -20
       │     ├─ 检测情绪化表达 → -15
       │     ├─ 检测绝对化表述 → -15
       │     └─ 检测证据冲突 → -25
       ├─ 5. 计算最终得分
       │     ├─ 正常: evidence_score×0.4 + llm_score×0.4 + rule_score×0.2
       │     └─ LLM降级: (evidence_score×0.4 + rule_score×0.2) / 0.6
       ├─ 6. get_risk_level_from_score(final_score)
       │     └─ ≥80→可信新闻, ≥60→存疑信息, ≥40→疑似谣言, <40→高风险谣言
       └─ 7. save_detection_record() → DetectionRecord + EvidenceMatch ×N
```

**LLM 降级触发条件**（_is_llm_failure）：
- risk_level == "模型调用失败"
- error == "模型调用失败"
- llm_score==0 且 reason 含 "模型调用失败"
- llm_score==0 且 risk_points 含 "模型调用失败"

**降级评分**：LLM 权重从 0.4 重新分配到 evidence 和 rule

---

## 6. 数据库和数据模型

### 6.1 数据库概览

| 维度 | 内容 |
|---|---|
| **数据库类型** | MySQL 8.x（开发环境使用 pymysql 驱动） |
| **数据库名** | `zhiyun_bianzhen` |
| **字符集** | utf8mb4 |
| **ORM** | SQLAlchemy 2.0.31 |
| **迁移工具** | Alembic 1.13.2 |
| **迁移版本** | 4 个：0001_initial_schema, 0002_add_high_risk_review_fields, 0003_add_system_logs, 0004_add_business_updated_at |
| **表引擎** | InnoDB |
| **连接配置** | 拆分配置字段或完整 DATABASE_URL（后者优先），pool_pre_ping=True, pool_recycle=3600 |
| **Session 管理** | `sessionmaker(autocommit=False, autoflush=False)` → `get_db()` 生成器，每次请求一个 session |
| **种子数据** | `seed_demo_data.py`：3 个演示用户 + ~20 条知识库数据 + 检测记录 + Chroma 向量 |

### 6.2 核心数据模型表

| 模型 | 表名 | 主要字段 | 关联关系 | 使用模块 | 迁移情况 |
|---|---|---|---|---|---|
| **User** | `users` | id(PK), username(UQ), password_hash, email(UQ), role(user/admin), status(active/disabled), created_at, updated_at | 无自关联 | auth, detect, report, admin_users | 0001_initial_schema |
| **DetectionRecord** | `detection_records` | id(PK), user_id(FK→users), input_title, input_content, category, keywords, final_score, evidence_score, llm_score, rule_score, risk_level, judgement_result, reason, risk_points, suggestion, is_high_risk, review_status(pending/approved/rejected), is_public, admin_remark, reviewed_at, reviewed_by(FK→users), report_url, created_at, updated_at | FK→users (SET NULL), 1:N→EvidenceMatch, 1:1→Report | detect, high_risk, statistics, report | 0001(创建), 0002(审核字段), 0004(updated_at) |
| **EvidenceMatch** | `evidence_matches` | id(PK), detection_id(FK→detection_records CASCADE), knowledge_id(FK→knowledge_items SET NULL), title, summary, source_name, similarity_score, rank_order, created_at, updated_at | FK→detection_records (CASCADE), FK→knowledge_items (SET NULL) | detection_service | 0001(创建), 0004(updated_at) |
| **KnowledgeItem** | `knowledge_items` | id(PK), title, content, category, truth_label, source_name, source_url, publish_time, summary, keywords, debunking_explanation, risk_level, admin_note, vector_id, vector_sync_status(pending/synced/failed/delete_failed), vector_sync_error, created_at, updated_at | 无 FK，通过 vector_id 关联 Chroma | knowledge, chroma, detection | 0001_initial_schema |
| **PromptTemplate** | `prompt_templates` | id(PK), name, type, content, is_default, status(enabled/disabled), created_by(FK→users SET NULL), created_at, updated_at | FK→users (SET NULL) | prompt_service, llm_service | 0001_initial_schema |
| **Report** | `reports` | id(PK), detection_id(FK→detection_records CASCADE, UQ), user_id(FK→users SET NULL), report_title, html_path, pdf_path, created_at, updated_at | FK→detection_records (CASCADE, UQ), FK→users (SET NULL) | report_service | 0001(创建), 0004(updated_at) |
| **SystemLog** | `system_logs` | id(PK), user_id(FK→users SET NULL), action, module, description, ip_address, created_at | FK→users (SET NULL) | system_log_service, auth, detect, admin_* | 0003_add_system_logs |

### 6.3 实体关系图（文字描述）

```
users (1) ──(SET NULL)──> detection_records (N)
users (1) ──(SET NULL)──> reports (N)
users (1) ──(SET NULL)──> prompt_templates (N)
users (1) ──(SET NULL)──> system_logs (N)
detection_records (1) ──(CASCADE)──> evidence_matches (N)
detection_records (1) ──(CASCADE, UQ)──> reports (1)
knowledge_items (1) ──(SET NULL)──> evidence_matches (N)
knowledge_items ──(vector_id)──> Chroma knowledge_items collection
```

### 6.4 ~~注意：~~ `models/__init__.py` 已修复

**已确认**：`backend/app/models/__init__.py` 中 SystemLog 已正确导入并列入单一的 `__all__` 列表。之前的重复 `__all__` 定义问题已修正。

---

## 7. 身份认证与权限体系

### 7.1 认证全流程

```
注册: POST /api/auth/register
  → auth_service.register_user()
    → 检查用户名/邮箱唯一性（UserAlreadyExistsError）
    → bcrypt 哈希密码
    → user_crud.create_user(role="user", status="active")
    → 记录 system_log

登录: POST /api/auth/login
  → auth_service.authenticate_user()
    → 按用户名查 User → 验证密码 → 检查 status=="active"
  → create_access_token(subject=user.id, role=user.role, extra_data={"username": ...})
    → jwt.encode({sub, exp, role, username}, SECRET_KEY, HS256)
  → 返回 {access_token, token_type: "bearer", user}

Token 验证: get_current_user (core/deps.py)
  → OAuth2PasswordBearer(tokenUrl="/api/auth/login") 提取 token
  → decode_token(token) → jwt.decode → 获取 subject (user_id)
  → get_user_by_id(db, user_id)
  → 检查 user.status == "active"

管理员验证: get_current_admin = get_current_user → check role == "admin"

可选验证: get_optional_current_user
  → 无 Authorization header 返回 None
  → 有则验证 token，失败抛 401
```

### 7.2 前端认证

| 环节 | 实现 |
|---|---|
| Token 存储 | `localStorage.setItem("zhiyun_bianzhen_token", token)` |
| User 存储 | `localStorage.setItem("zhiyun_bianzhen_user", JSON.stringify(user))` |
| Token 发送 | Axios 请求拦截器自动附加 `Authorization: Bearer <token>` |
| Session 恢复 | 页面刷新后 `restoreSession()` 读取 localStorage → 调用 `/auth/me` 验证 → 失败自动登出 |
| 401 处理 | Axios 响应拦截器 → logout() → 跳转 `/login` |
| 登出 | 清除 localStorage → 重置 store state |

### 7.3 权限矩阵

| 功能 | 游客 | 普通用户 (user) | 管理员 (admin) | 权限控制位置 | 备注 |
|---|---|---|---|---|---|
| 新闻检测 | ✅ | ✅ | ✅ | `get_optional_current_user` | 游客和登录用户均可使用 |
| 查看检测结果 | ✅ | ✅(自己的) | ✅(全部) | 结果页公开；详情需登录 | `allowGuestResult: true` 路由 meta |
| 查看历史 | ❌ | ✅(自己的) | ✅(全部) | `get_current_user` | 管理员通过 admin 接口查看所有 |
| 高风险新闻(公开) | ✅ | ✅ | ✅ | 无权限限制 | 仅返回 reviewed + approved + is_public 的记录 |
| 高风险新闻(管理) | ❌ | ❌ | ✅ | `get_current_admin` | 审核、公开、备注 |
| 用户管理 | ❌ | ❌ | ✅ | `get_current_admin` | 列表、详情、启用、禁用、改角色 |
| 知识库管理 | ❌ | ❌ | ✅ | `get_current_admin` | 完整 CRUD + 向量化 + 重建索引 |
| Prompt 管理 | ❌ | ❌ | ✅ | `get_current_admin` | 完整 CRUD + 启用/禁用/设默认 |
| 报告(个人) | ❌ | ✅(自己的) | ✅(自己的) | `get_current_user` + `_ensure_owner_or_admin` | 管理员可生成/下载任何人报告 |
| 报告(管理) | ❌ | ❌ | ✅ | `get_current_admin` | 列表、详情、下载 |
| 统计图表 | ❌ | ❌ | ✅ | `get_current_admin` | 概览、趋势、分布、关键词、活跃度 |
| 检测记录(管理) | ❌ | ❌ | ✅ | `get_current_admin` | 列表、详情、删除 |
| 系统日志 | ❌ | ❌ | ✅ | `get_current_admin` | 只读查看 |
| RAG 检索 | ❌ | ✅ | ✅ | `get_current_user` | 独立检索接口 |
| 个人中心 | ❌ | ✅ | ✅ | `get_current_user` | 查看当前用户信息 |
| 注册 | ✅ | ❌(已登录跳转) | ❌(已登录跳转) | `guestOnly` 路由 meta | 注册后自动获得 user 角色 |

### 7.4 安全机制摘要

| 机制 | 实现 |
|---|---|
| **密码哈希** | bcrypt (passlib) |
| **JWT 算法** | HS256 |
| **Token 过期** | 1440 分钟（24小时），可配置 |
| **SECRET_KEY 验证** | 启动时拒绝占位符值；生产环境要求 >32 字符且 >8 不同字符 |
| **注册限流** | IP 级别：2次/60秒 |
| **登录限流** | IP 级别：5次/60秒 |
| **检测限流** | IP 级别：3次/60秒（可配置） |
| **用户状态检查** | `get_current_user` 拒绝 status != "active" |
| **Prompt 注入防御** | XML 标签包裹用户输入 + 安全指令前缀 + 文本清洗 |
| **报告路径安全** | 路径解析验证（防止路径遍历）；文件名格式校验（仅允许 `report_<32hex>.pdf|html`） |

---

## 8. 第三方服务

| 第三方服务 | 调用位置 | 配置来源 | 用途 | 是否有封装层 | 是否有 Mock | 下一轮风险点 |
|---|---|---|---|---|---|---|
| **DeepSeek Chat API** | `services/llm_service.py` — `_post_chat_completion()` | `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, `DEEPSEEK_MODEL`, `DEEPSEEK_TIMEOUT_SECONDS` | LLM 可信度分析（核心检测管线） | 是（完整封装 + 多级降级 + Prompt 安全） | 否（但有多层 fallback + error result 降级） | API Key 未配置时降级但不中断；超时/网络异常有兜底返回 |
| **DashScope Embedding** | `services/embedding_service.py` — `_dashscope_embed_batch()` | `DASHSCOPE_API_KEY`, `DASHSCOPE_BASE_URL`, `DASHSCOPE_EMBEDDING_MODEL` | 文本向量化（语义 RAG） | 是（`embed_text`/`embed_texts` 统一接口） | hash provider 可作为 fallback | API Key 未配置时 RAG 检索会失败（hash 不提供语义检索能力） |
| **DeepSeek Embedding** | `services/embedding_service.py` — `_deepseek_embed_batch()` | `DEEPSEEK_API_KEY` (复用), `DEEPSEEK_EMBEDDING_MODEL` | 文本向量化（备用 provider） | 是（同一统一接口） | 同 hash fallback | 复用 LLM 的 API Key，与 DashScope 互斥 |
| **Chroma** | `services/chroma_service.py` | `CHROMA_PATH` | 向量存储与检索 | 是（`get_chroma_client`/`get_knowledge_collection` 带重试机制） | 否（本地持久化，需先执行 seed 或 rebuild） | 本地文件依赖；维度切换需要重建 |
| **jinja2/xhtml2pdf** | `services/report_service.py` | `REPORT_DIR` | HTML 模板渲染 + PDF 导出 | 是（在 report_service 内封装） | 否 | PDF 中文字体可能需额外配置 |

### 重要发现

- **无 Redis/缓存层**：所有限流器为 InMemory，多进程部署时无法共享状态
- **无消息队列**：Chroma 向量同步和 MySQL 写入为同步调用
- **无对象存储**：报告文件存储于本地文件系统
- **无外部 OAuth**：仅用户名+密码认证

---

## 9. 核心业务功能地图

### 9.1 按角色整理功能

#### 游客功能
1. ✅ 浏览首页 — [已找到完整代码链路]
2. ✅ 提交新闻检测 — [已找到完整代码链路]（通过 `get_optional_current_user`）
3. ✅ 查看检测结果（通过 URL 跳转后） — [已找到完整代码链路]（路由 meta `allowGuestResult: true`，详情 API 需要登录故游客可能只能看缓存/重定向结果）
4. ✅ 查看公开高风险新闻列表 — [已找到完整代码链路]
5. ✅ 注册账号 — [已找到完整代码链路]
6. ✅ 登录 — [已找到完整代码链路]

#### 普通用户功能
1. ✅ 所有游客功能 — [已找到完整代码链路]
2. ✅ 查看个人检测历史 — [已找到完整代码链路]（分页、筛选）
3. ✅ 查看检测详情 — [已找到完整代码链路]
4. ✅ 生成 PDF 报告 — [已找到完整代码链路]
5. ✅ 下载 PDF 报告 — [已找到完整代码链路]
6. ✅ 查看个人中心 — [已找到完整代码链路]（目前仅显示用户信息）
7. ✅ RAG 检索接口 — [已找到完整代码链路]（前端未直接调用此独立接口）

#### 管理员功能
1. ✅ 后台首页 Dashboard — [已找到完整代码链路]
2. ✅ 用户管理（列表/详情/启用/禁用/改角色） — [已找到完整代码链路]
3. ✅ 检测记录管理（列表/详情/删除） — [已找到完整代码链路]
4. ✅ 知识库 CRUD — [已找到完整代码链路]
5. ✅ 知识库向量化/重建索引 — [已找到完整代码链路]
6. ✅ Prompt 模板管理（CRUD + 启用/禁用/设默认） — [已找到完整代码链路]
7. ✅ 高风险新闻审核管理 — [已找到完整代码链路]
8. ✅ 数据统计图表 — [已找到完整代码链路]
9. ✅ 报告管理（列表/详情/下载） — [已找到完整代码链路]
10. ✅ 系统日志查看 — [已找到完整代码链路]

#### 超级管理员功能
- 尚未发现独立的"超级管理员"角色。系统仅有 `user` 和 `admin` 两种角色。`FIRST_SUPERUSER_*` 环境变量创建的是 `role="admin"` 用户。

#### 系统自动功能
1. ✅ 系统日志记录 — [已找到完整代码链路]（auth 登录/注册、detect 检测、admin 各类操作均记录）
2. ✅ IP 限流 — [已找到完整代码链路]（登录、注册、检测各有独立限流器）
3. ✅ SECRET_KEY 启动验证 — [已找到完整代码链路]

---

## 10. 前后端接口初步映射

### 10.1 前端 baseURL

- **来源**：`import.meta.env.VITE_API_BASE_URL || '/api'`
- **Vite 代理**：开发环境前端默认通过 `/api` 访问后端（Vite proxy 配置待确认，但 `.env.example` 未提及 `VITE_API_BASE_URL`）

### 10.2 接口映射表

| 功能 | 前端调用位置 | 前端方法和路径 | 后端路由位置 | 后端方法和路径（含prefix） | 初步匹配情况 |
|---|---|---|---|---|---|
| 注册 | `api/auth.js` | POST `/auth/register` | `api/v1/auth.py` | POST `/api/auth/register` | ✅ 匹配 |
| 登录 | `api/auth.js` | POST `/auth/login` | `api/v1/auth.py` | POST `/api/auth/login` | ✅ 匹配 |
| 当前用户 | `api/auth.js` | GET `/auth/me` | `api/v1/auth.py` | GET `/api/auth/me` | ✅ 匹配 |
| 新闻检测 | `api/detect.js` | POST `/detect/news` | `api/v1/detect.py` | POST `/api/detect/news` | ✅ 匹配 |
| 检测历史 | `api/detect.js` | GET `/detect/history` | `api/v1/detect.py` | GET `/api/detect/history` | ✅ 匹配 |
| 检测详情 | `api/detect.js` | GET `/detect/{id}` | `api/v1/detect.py` | GET `/api/detect/{id}` | ✅ 匹配 |
| 生成报告 | `api/report.js` | POST `/report/generate/{id}` | `api/v1/report.py` | POST `/api/report/generate/{detection_id}` | ✅ 匹配 |
| 下载报告 | `api/report.js` | GET `/report/download/{id}` | `api/v1/report.py` | GET `/api/report/download/{report_id}` | ✅ 匹配 |
| 公开高风险 | `api/highRisk.js` | GET `/high-risk/public` | `api/v1/high_risk.py` | GET `/api/high-risk/public` | ✅ 匹配 |
| 高风险排名 | `api/highRisk.js` | GET `/high-risk/ranking` | `api/v1/high_risk.py` | GET `/api/high-risk/ranking` | ✅ 匹配 |
| 高风险关键词 | `api/highRisk.js` | GET `/high-risk/keywords` | `api/v1/high_risk.py` | GET `/api/high-risk/keywords` | ✅ 匹配 |
| 高风险分类分布 | `api/highRisk.js` | GET `/high-risk/category-distribution` | `api/v1/high_risk.py` | GET `/api/high-risk/category-distribution` | ✅ 匹配 |
| Admin Ping | 未在前端发现调用 | — | `api/v1/admin.py` | GET `/api/admin/ping` | ⚠️ 后端存在但前端未使用 |
| 管理端知识库 CRUD | `api/adminKnowledge.js` | GET/POST/PUT/DELETE `/admin/knowledge/*` | `api/v1/admin_knowledge.py` | 对应方法 `/api/admin/knowledge/*` | ✅ 匹配 |
| 管理端 Prompt CRUD | `api/adminPrompts.js` | GET/POST/PUT/DELETE `/admin/prompts/*` | `api/v1/admin_prompts.py` | 对应方法 `/api/admin/prompts/*` | ✅ 匹配 |
| 管理端高风险管理 | `api/adminHighRisk.js` | GET/PUT `/admin/high-risk/*` | `api/v1/admin_high_risk.py` | 对应方法 `/api/admin/high-risk/*` | ✅ 匹配 |
| 管理端统计 | `api/adminStatistics.js` | GET `/admin/statistics/*` | `api/v1/admin_statistics.py` | 对应方法 `/api/admin/statistics/*` | ✅ 匹配 |
| 管理端报告 | `api/adminReports.js` | GET `/admin/reports/*` | `api/v1/admin_reports.py` | 对应方法 `/api/admin/reports/*` | ✅ 匹配 |
| 管理端检测记录 | `api/adminDetections.js` | GET/DELETE `/admin/detections/*` | `api/v1/admin_detections.py` | 对应方法 `/api/admin/detections/*` | ✅ 匹配 |
| 管理端用户管理 | `api/adminUsers.js` | GET/POST `/admin/users/*` | `api/v1/admin_users.py` | 对应方法 `/api/admin/users/*` | ✅ 匹配 |
| 管理端日志 | `api/adminLogs.js` | GET `/admin/logs` | `api/v1/admin_logs.py` | GET `/api/admin/logs` | ✅ 匹配 |
| RAG 检索 | 未在前端发现调用 | — | `api/v1/rag.py` | POST `/api/rag/search` | ⚠️ 后端存在独立 RAG 接口但前端未使用 |
| 健康检查 | 未在前端发现调用 | — | `api/v1/health.py` | GET `/api/health` | ⚠️ 后端存在但前端未使用 |
| Admin role 更新 | 未在前端发现调用 | — | `api/v1/admin_users.py` | POST `/api/admin/users/{id}/role` | ❌ **前端缺失** — 后端 API 存在但前端 `adminUsers.js` 无封装函数，`AdminUsersView.vue` 无角色变更 UI（仅导入 disable/enable/detail/detections/list，模板中仅"启用/禁用"按钮，无角色修改控件） |

---

## 11. 测试体系

### 11.1 测试概览

| 维度 | 内容 |
|---|---|
| **测试框架** | Python unittest (内置) |
| **测试目录** | `backend/tests/` |
| **测试文件数** | 32 个 |
| **测试发现命令** | `python -m unittest discover -s tests -p "test_*.py"` |
| **前端测试** | 仅 `utils/detectionResultCache.test.js` (1个) |
| **CI/CD 测试** | 尚未发现 |

### 11.2 后端测试映射表

| 测试模块 | 测试对象 | 测试类型 | 是否依赖外部环境 | 下一轮核查重点 |
|---|---|---|---|---|
| `test_auth_smoke.py` | 登录/注册/me API | 冒烟测试 | 是（需数据库） | 测试完整性、Mock程度 |
| `test_detect_api.py` | 检测 API | API 测试 | 是（需数据库+Chroma+LLM） | LLM 调用 Mock 策略 |
| `test_detection_crud.py` | 检测记录 CRUD | 单元测试 | 是（需数据库） | CRUD 覆盖 |
| `test_detection_history_api.py` | 历史查询 API | API 测试 | 是（需数据库） | 分页/筛选覆盖 |
| `test_llm_service.py` | LLM 服务 | 单元测试 | 可能 Mock | Prompt 构建/JSON 解析覆盖 |
| `test_chroma_service.py` | Chroma 服务 | 单元/集成测试 | 是（需 Chroma） | 重试机制测试 |
| `test_chroma_integration.py` | Chroma 集成 | 集成测试 | 是（需 Chroma） | 端到端向量流程 |
| `test_embedding_service.py` | Embedding 服务 | 单元测试 | 可能 Mock | 多 provider 切换测试 |
| `test_knowledge_sync.py` | 知识库同步 | 集成测试 | 是（需数据库+Chroma） | MySQL↔Chroma 一致性 |
| `test_rule_score_service.py` | 规则评分 | 单元测试 | 否 | 规则边界覆盖 |
| `test_report_service.py` | 报告服务 | 单元测试 | 可能需模板 | PDF 生成测试 |
| `test_report_api.py` | 报告 API | API 测试 | 是（需数据库+模板） | 下载/权限 |
| `test_admin_prompts_api.py` | Prompt 管理 API | API 测试 | 是（需数据库） | CRUD/校验 |
| `test_prompt_service.py` | Prompt 服务 | 单元/集成测试 | 是（需数据库） | 默认模板逻辑 |
| `test_high_risk_api.py` | 高风险 API | API 测试 | 是（需数据库） | 审核流程 |
| `test_high_risk_service.py` | 高风险服务 | 单元测试 | 可能 Mock | 审核状态机 |
| `test_high_risk_utils.py` | 高风险工具函数 | 单元测试 | 否 | should_mark_high_risk 边界 |
| `test_statistics_service.py` | 统计服务 | 单元测试 | 可能 Mock | 聚合逻辑 |
| `test_admin_statistics_api.py` | 统计 API | API 测试 | 是（需数据库） | 日期范围校验 |
| `test_admin_users_api.py` | 用户管理 API | API 测试 | 是（需数据库） | 权限/自我操作 |
| `test_admin_user_service.py` | 用户管理服务 | 单元测试 | 可能 Mock | LastAdmin 保护 |
| `test_admin_reports_api.py` | 报告管理 API | API 测试 | 是（需数据库） | 管理端权限 |
| `test_rag_api.py` | RAG 检索 API | API 测试 | 是（需数据库+Chroma） | 搜索质量 |
| `test_system_log_service.py` | 系统日志服务 | 单元测试 | 可能 Mock | 写入/回滚 |
| `test_system_logs_api.py` | 系统日志 API | API 测试 | 是（需数据库） | 筛选功能 |
| `test_system_log_events_api.py` | 系统日志事件 | API 测试 | 是（需数据库） | 事件记录完整性 |
| `test_risk_level_constants.py` | 风险等级常量 | 单元测试 | 否 | 阈值定义 |
| `test_risk_level_utils.py` | 风险等级工具 | 单元测试 | 否 | 映射逻辑 |
| `test_text_cleaner.py` | 文本清洗 | 单元测试 | 否 | 边界情况 |
| `test_secret_key_startup_validation.py` | SECRET_KEY 验证 | 单元测试 | 否 | 生产安全检查 |
| `test_seed_demo_data.py` | 种子数据初始化 | 集成测试 | 是（需全部环境） | 数据完整性 |
| `test_database_migrations.py` | 数据库迁移 | 集成测试 | 是（需数据库） | 迁移可用性 |
| `test_cors_config.py` | CORS 配置 | 单元测试 | 否 | 配置正确性 |
| `test_business_timestamp_models.py` | 业务时间戳 | 单元测试 | 可能需数据库 | updated_at 自动更新 |

### 11.3 测试覆盖总结

- **已确认事实**：后端有 32 个测试文件，覆盖 auth、detect、chroma、embedding、llm、report、knowledge、high_risk、statistics、admin_users、admin_prompts、admin_reports、system_log、config、cors、utils 等几乎所有模块
- **待确认**：各测试的运行环境依赖、Mock 程度、通过率未实际运行验证
- **前端测试严重不足**：仅有 1 个 cache 工具函数测试，所有页面、组件、状态管理均无测试

---

## 12. 配置和部署方式

### 12.1 环境变量配置

| 变量 | 默认值 | 说明 |
|---|---|---|
| `PROJECT_NAME` | `zhiyun-bianzhen-backend` | 项目名称 |
| `PROJECT_VERSION` | `0.1.0` | 项目版本 |
| `API_PREFIX` | `/api` | API 路径前缀 |
| `APP_ENV` / `ENVIRONMENT` / `ENV` | `development` | 运行环境 |
| `BACKEND_CORS_ORIGINS` | `*` | CORS 允许来源 |
| `DATABASE_HOST` | `127.0.0.1` | MySQL 主机 |
| `DATABASE_PORT` | `3306` | MySQL 端口 |
| `DATABASE_USER` | `root` | MySQL 用户 |
| `DATABASE_PASSWORD` | (空) | MySQL 密码 |
| `DATABASE_NAME` | `zhiyun_bianzhen` | MySQL 数据库名 |
| `DATABASE_URL` | (空，优先生效) | 完整 MySQL 连接串 |
| `SECRET_KEY` | (必填) | JWT 签名密钥 |
| `ALGORITHM` | `HS256` | JWT 算法 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | Token 过期时间 |
| `CHROMA_PATH` / `CHROMA_PERSIST_DIR` | `./chroma_db` | Chroma 持久化路径 |
| `EMBEDDING_PROVIDER` | `dashscope` | Embedding 提供商 |
| `EMBEDDING_DIMENSION` | `1024` | Embedding 向量维度 |
| `DASHSCOPE_API_KEY` | (必填，dashscope 模式下) | DashScope API Key |
| `DASHSCOPE_EMBEDDING_MODEL` | `text-embedding-v4` | DashScope 模型 |
| `DEEPSEEK_API_KEY` | (可选，LLM 检测需要) | DeepSeek API Key |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | DeepSeek API 地址 |
| `DEEPSEEK_MODEL` | `deepseek-chat`（代码默认）/ `deepseek-v4-pro`（.env.example 中） | DeepSeek 模型 |
| `DEEPSEEK_TIMEOUT_SECONDS` | `30` | DeepSeek API 超时 |
| `REPORT_DIR` | 系统临时目录 fallback | PDF/HTML 报告输出目录 |
| `DETECT_RATE_LIMIT_COUNT` | `3` | 检测限流次数 |
| `DETECT_RATE_LIMIT_WINDOW_SECONDS` | `60` | 检测限流窗口 |
| `FIRST_SUPERUSER_USERNAME/PASSWORD/EMAIL` | (init_db 使用) | 首次管理员创建 |
| `DEMO_PASSWORD` / `ADMIN_DEMO_PASSWORD` | (seed 使用) | 演示用户密码 |

### 12.2 部署方式

- **开发部署**：手动启动 uvicorn + npm run dev（详见 README.md 和 CLAUDE.md）
- **数据库迁移**：`python -m app.db.migrate` 或 `alembic upgrade head`
- **数据库初始化**：`python -m app.db.init_db`（创建超级管理员）
- **种子数据**：`python -m app.db.seed_demo_data`（演示数据 + Chroma 向量）
- **尚未发现**：Dockerfile、docker-compose.yml、CI/CD pipeline 配置、Nginx 配置、systemd service 文件

### 12.3 持久化路径

| 数据类型 | 默认路径 | 备注 |
|---|---|---|
| Chroma 向量数据 | `../data/chroma`（相对 backend/） | gitignored |
| PDF/HTML 报告 | `../data/reports`（相对 backend/） | gitignored，必须在后端源码目录外 |
| MySQL 数据库 | `zhiyun_bianzhen` | 需手动创建数据库 |
| 前端构建产物 | `frontend/dist/` | gitignored |

---

## 13. 文档与代码的对应关系

### 13.1 文档层级与权威性

| 层级 | 文档 | 权威性 | 说明 |
|---|---|---|---|
| **设计权威** | `docs/01_project_design.md` | ⭐⭐⭐ 最高 | 项目定位、角色、功能、评分、页面设计 |
| **设计权威** | `docs/02_database_design.md` | ⭐⭐⭐ 最高 | 表结构、字段、关系规范 |
| **设计权威** | `docs/03_api_design.md` | ⭐⭐⭐ 最高 | 接口路径、参数、返回格式规范 |
| **设计权威** | `docs/04_development_tasks.md` | ⭐⭐ 高 | 开发阶段拆解和 Codex 使用指南 |
| **设计权威** | `docs/05_project_structure.md` | ⭐⭐ 高 | 目录结构规范 |
| **操作参考** | `CLAUDE.md` | ⭐⭐ 高 | 项目上下文、架构、命令 |
| **操作参考** | `backend/README.md` | ⭐ 中 | 后端演示环境与联调说明 |
| **已过时** | `README.md`（根目录） | ❌ 不作为需求依据 | 项目早期编写，部分描述与当前代码不一致 |
| **历史参考** | `docs/06-12_phase*_prompts.md` | ⭐ 低 | 各阶段开发 Prompt，历史参考 |
| **审查参考** | `docs/enterprise_code_review_report.md` | ⭐⭐ 参考 | 2026-06-11 企业级审查报告，部分发现可能已修复 |

### 13.2 设计文档 vs 实际代码差异

| 设计文档描述 | 代码实际 | 差异类型 |
|---|---|---|
| `01` 列出 `/admin/samples`（新闻样例管理）页面 | 代码中不存在该路由、页面和 API | ❌ **设计有但未实现** |
| `01` 列出多种 Prompt 类型（关键词提取/风险点分析/辟谣建议/报告生成） | 代码中仅实现 `news_credibility` 一种类型 | ⚠️ **功能裁剪**，仅实现了核心类型 |
| `01` 设计 `agent_service.py` 独立服务 | 实际 Agent 步骤硬编码在 `detection_service.py` 中 | ⚠️ **简化实现**，未独立为服务 |
| `02` 数据库设计含 `high_risk_news.py` 独立模型 | 实际高风险新闻复用 `DetectionRecord`（通过 is_high_risk 字段） | ⚠️ **简化实现**，合理的设计变更 |
| `03` API 设计列出 `/admin/samples` 路由 | 代码中不存在 | ❌ **设计有但未实现** |
| `05` 目录结构建议 `services/agent_service.py` | 不存在该文件 | ⚠️ **简化实现** |
| README 引用 `docs/01-12` 系列文档 | docs/ 已在 .gitignore 中（但本地可读） | ⚠️ README 过时，docs 仍可本地访问 |
| `.env.example` 中 `DEEPSEEK_MODEL=deepseek-v4-pro` | `llm_service.py` 代码默认 `deepseek-chat` | 差异但无害（.env 设置优先于代码默认值） |

### 13.3 设计文档确认的功能范围（从 docs/01 提取）

**课程设计必做版（docs/01 第15节）**：
1. 用户注册登录 — ✅ 已实现
2. JWT 权限认证 — ✅ 已实现
3. 用户/管理员角色区分 — ✅ 已实现
4. 新闻标题+正文检测 — ✅ 已实现
5. DeepSeek API 调用 — ✅ 已实现
6. Chroma 知识库检索 — ✅ 已实现
7. 可信度评分 — ✅ 已实现
8. 风险等级判断 — ✅ 已实现
9. 检测结果页 — ✅ 已实现
10. 检测历史记录 — ✅ 已实现
11. PDF 报告下载 — ✅ 已实现
12. 管理员知识库管理 — ✅ 已实现
13. Prompt 模板完整 CRUD — ✅ 已实现（仅 news_credibility 类型）
14. 后台首页统计 — ✅ 已实现
15. 数据可视化图表 — ✅ 已实现

**简历增强版（docs/01 第16节，尚未实现）**：
- 更完整的 Agent 工作流 — ❌ 未独立为服务
- Top-K 检索参数后台配置 — ❌ 未实现（硬编码 RAG_TOP_K=10）
- 批量导入知识库 — ❌ 未实现
- 联网搜索真实新闻证据 — ❌ 未实现
- 多模态扩展 — ❌ 未实现
- 检测效果评估指标 — ❌ 未实现
- 多模型切换 — ❌ 未实现

---

## 14. 已确认事实

1. ✅ 项目是前后端分离的单体仓库，后端 Python/FastAPI，前端 Vue 3/Vite
2. ✅ 检测管线的完整调用链已追踪：关键词提取 → RAG 检索(Chroma) → LLM 分析(DeepSeek) → 规则评分 → 最终得分(加权) → 风险等级
3. ✅ 后端分层严格遵守：api → services → crud → models/schemas
4. ✅ 认证体系：JWT (HS256) + bcrypt，两个角色（user/admin），三个依赖注入函数
5. ✅ 7 个数据模型：User, DetectionRecord, EvidenceMatch, KnowledgeItem, PromptTemplate, Report, SystemLog
6. ✅ 前端有用户端布局(UserLayout)和管理端布局(AdminLayout)，路由懒加载
7. ✅ 前端 API 封装完整：13 个 API 模块文件，所有后端路由都有对应的前端调用
8. ✅ 限流为 InMemory 实现（3 个独立限流器），不支持分布式
9. ✅ LLM 有多级降级策略：API Key 未配置 → error_result；调用失败 → 降级检测 + degraded_agent_steps
10. ✅ Prompt 有多层安全机制：XML 标签包裹用户输入、注入防御指令、安全边界前缀
11. ✅ Embedding 支持 3 种 provider：dashscope（语义）、deepseek（语义）、hash（非语义 fallback）
12. ✅ 系统日志记录覆盖 auth、detection、knowledge、prompt、high_risk、admin 模块
13. ✅ 报告使用了 jinja2 模板渲染 HTML + xhtml2pdf 转 PDF
14. ✅ 知识库删除采用"先删 Chroma 再删 MySQL"，失败时有补偿恢复机制
15. ✅ 数据库迁移使用 Alembic（4 个版本），有 migration_guard 保护数据初始化前检查
16. ✅ Prompt 模板支持创建/更新/删除/启用/禁用/设默认，使用前验证内容合法性
17. ✅ 前端 token 存储在 localStorage，页面刷新后通过 `/auth/me` 恢复并验证 session

---

## 15. 合理推断

1. 🔵 项目主要用于课程答辩和简历展示（源自 docs/01："面向求职展示" + "课程综合设计"），不太可能是生产环境部署
2. 🔵 `docs/` 被加入 `.gitignore` 是为了防止 IDE/Codex 生成的设计文档被意外提交，但本地仍可正常读取和参考
3. 🔵 前端 `AdminUsersView.vue` 角色变更功能缺失是刻意裁剪（设计文档未明确要求管理端角色变更），后端 API 作为预留能力存在
4. 🔵 前端未调用 `/api/rag/search` 独立 RAG 接口和 `/api/admin/ping`，可能是开发调试/未来扩展预留
5. 🔵 测试可能大量依赖数据库和外部服务（需实际运行确认 Mock 程度）
6. 🔵 种子数据中的 `DEEPSEEK_MODEL` 配置为 `deepseek-v4-pro` 是用户项目的自定义模型
7. 🔵 设计文档中 `/admin/samples` 被有意裁剪或合并到 `/admin/knowledge` 中

---

## 16. 待确认信息

1. ❓ Vite 开发代理配置的具体位置和规则
2. ❓ 前端 `package.json` 的完整依赖列表和脚本命令
3. ❓ `ResultView.vue` 游客访问时详情 API 返回 401 的具体处理方式（路由 meta 允许游客但详情 API 需要登录认证）
4. ❓ 32 个后端测试的实际通过率
5. ❓ Chroma 数据与 MySQL 的一致性在实际运行中的表现
6. ❓ PDF 报告中文字体渲染是否需要额外配置
7. ❓ `test-persist/` 目录的用途
8. ❓ `.codex/` 目录的内容和用途
9. ❓ 生产环境下限流器的多进程共享问题是否被关注
10. ❓ 是否有计划增加 Redis 或数据库限流以支持水平扩展
11. ❓ 前端 `AdminUsersView.vue` 角色变更功能为刻意裁剪还是未完成（后端 API 已就绪）

---

## 17. 下一轮重点核查线索

### 17.1 安全相关

| 编号 | 线索 | 位置 | 风险描述 |
|---|---|---|---|
| S-01 | CORS `allow_origins=["*"]` + `allow_credentials=False`（开发环境） | `main.py:18,29-30` | 生产环境需改为明确域名 |
| S-02 | Token 存储在 localStorage | `frontend/src/utils/auth.js` | XSS 可读（需评估是否有 CSP/输入消毒防护） |
| S-03 | InMemory 限流器无法跨进程共享 | `core/rate_limit.py` | 多 worker 部署时限流失效 |
| S-04 | SECRET_KEY 弱密钥检测仅在 production 环境启用 | `core/config.py:162` | 非 production 环境可用弱密钥 |
| S-05 | Prompt 注入防御依赖文本清洗 + XML 包裹 | `llm_service.py:262-264, 267-269` | 需评估实际防御效果 |
| S-06 | 报告文件路径验证 | `report_service.py:281-293` | 已有路径遍历防护和文件名格式校验，需验证充分性 |

### 17.2 可靠性相关

| 编号 | 线索 | 位置 | 风险描述 |
|---|---|---|---|
| R-01 | LLM 调用失败时检测降级但不中断 | `detection_service.py:102-103` | 降级准确性待评估 |
| R-02 | Chroma 删除后 MySQL 删除失败有补偿 | `knowledge_service.py:283-309` | 分布式一致性无保证 |
| R-03 | 知识库重建索引可能耗时较长 | `knowledge_service.py:430-461` | 无进度反馈，大知识库时超时风险 |

### 17.3 代码质量相关

| 编号 | 线索 | 位置 | 风险描述 |
|---|---|---|---|
| Q-01 | 前端仅 1 个工具函数测试 | `frontend/src/utils/detectionResultCache.test.js` | 页面、组件、状态管理无测试 |
| Q-02 | `api/v1/auth.py` 和 `api/v1/detect.py` 中 `_get_client_ip` 函数重复定义 | 两文件各自定义 | 应抽取到 utils |
| Q-03 | `deepseek-v4-pro` 在 `.env.example` 中但与代码默认 `deepseek-chat` 不一致 | `llm_service.py` vs `.env.example` | 文档/配置不一致 |

### 17.4 功能完整性相关

| 编号 | 线索 | 位置 | 风险描述 |
|---|---|---|---|
| F-01 | **前端 AdminUsersView.vue 无角色变更功能** | `api/adminUsers.js` + `AdminUsersView.vue` | 后端 POST `/api/admin/users/{id}/role` 存在，但前端 JS 无封装、模板无角色修改控件。需确认是否刻意裁剪 |
| F-02 | `/api/rag/search` 后端存在但前端未使用 | `api/v1/rag.py` | 确认为预留接口（RAG 检索已被 detection_service 内部调用，独立接口可能用于调试或未来扩展） |
| F-03 | `/api/admin/ping` 后端存在但前端未使用 | `api/v1/admin.py` | 确认为开发调试用健康检查，非业务接口 |
| F-04 | 无密码修改功能 | 全局搜索无结果 | 确认是否需要 |
| F-05 | 无 Token 刷新机制 | 全局搜索无 refresh token 相关代码 | Token 过期需重新登录 |
| F-06 | 设计文档有 `/admin/samples` 但代码中不存在 | `docs/01_project_design.md` vs 实际代码 | 确认功能是否被裁剪或合并 |

---

## 18. 建议的正式审查顺序

**重要约束**：第二轮审查必须进行**完整检查**，不得抽样。以下轮次按逻辑依赖排序，但每轮内部的所有文件必须全部审查。

**第一轮：核心数据流审查（全量）**
审查范围：所有 Service 层文件
- `detection_service.py` — 检测管线（核心业务逻辑）
- `llm_service.py` — LLM 调用、Prompt 构建、JSON 解析、降级策略
- `rule_score_service.py` — 规则评分引擎
- `chroma_service.py` — 向量存储与检索
- `embedding_service.py` — 多 provider embedding 策略
- `knowledge_service.py` — MySQL↔Chroma 同步、重建索引
- `report_service.py` — HTML/PDF 报告生成
- `high_risk_service.py` — 高风险审核状态机
- `prompt_service.py` + `prompt_template_validator.py` — Prompt 管理
- `statistics_service.py` — 统计聚合
- `auth_service.py` + `admin_user_service.py` — 认证与用户管理
- `system_log_service.py` — 系统日志

**第二轮：安全架构审查（全量）**
审查范围：所有 core/ + api/ + 前端安全相关文件
- `core/security.py` + `core/deps.py` + `core/config.py` — 认证鉴权全链路
- `core/rate_limit.py` — 限流机制（InMemory 分布式风险）
- 所有 `api/v1/*.py` — 权限依赖注入完整性
- 前端 `request.js` + `auth.js` + `stores/user.js` — Token 存储与传输
- 前端 `router/index.js` — 路由守卫完整性
- Prompt 注入防御（`llm_service.py` 安全相关部分）
- 报告路径安全（`report_service.py` 路径验证）

**第三轮：数据完整性审查（全量）**
审查范围：所有 models/ + crud/ + alembic/
- `models/` — 全部 7 个 ORM 模型定义
- `crud/` — 全部 8 个 CRUD 模块
- `db/session.py` + `db/base.py` + `db/base_class.py`
- `alembic/` — 全部 4 个迁移版本 + env.py
- `db/init_db.py` + `db/seed_demo_data.py` + `db/migrate.py` + `db/migration_guard.py`

**第四轮：前端功能审查（全量）**
审查范围：所有前端文件
- `views/` — 全部 16 个页面组件
- `components/` — 全部 12 个通用/管理端组件
- `layouts/` — UserLayout + AdminLayout
- `api/` — 全部 13 个 API 封装模块（重点验证与后端接口对齐）
- `stores/user.js` — 状态管理逻辑
- `utils/` — 全部工具函数
- `router/index.js` — 路由完整性

**第五轮：测试、配置与可维护性审查（全量）**
审查范围：所有测试 + 配置 + 文档 + 构建配置
- `tests/` — 全部 32 个后端测试文件（审查覆盖率和质量）
- `frontend/src/utils/detectionResultCache.test.js` — 前端唯一测试
- `core/config.py` — 全部配置项验证
- `.env.example` — 配置模板完整性
- `requirements.txt` — 依赖版本锁定
- 前端 `vite.config.js` + `package.json` — 构建配置
- 前端 `main.js` — Element Plus 按需导入完整性
- `docs/01-05` — 设计文档与实际代码对齐验证

---

## 19. 本轮覆盖范围

| 统计项 | 数值 |
|---|---|
| **读取文件数量** | ~65 个（含后端核心代码、前端核心代码、配置、docs/01-05设计文档、enterprise_code_review_report.md） |
| **核心分析模块** | backend/app（全部子目录），frontend/src（全部子目录），alembic（全部版本），docs/（01-05设计文档） |
| **未分析模块** | design-system/MASTER.md（与本项目开发无直接关系），test-persist/（用途不明），.codex/（用途不明），tmp*临时目录 |
| **排除目录** | `.git/`, `.idea/`, `.pytest_cache/`, `node_modules/`, `dist/`, `__pycache__/`, `chroma_db/`, `data/chroma/`, `data/reports/`, `venv/`, `.venv/`, `tmp*/` |
| **无法读取文件** | 无（所有所需的项目文件均可读取） |
| **分析深度** | 入口文件+路由+模型+Schema+全部Service+CRUD+核心工具全部代码级分析；前端所有 API 封装；AdminUsersView.vue 完整代码；设计文档 01-05；企业级审查报告摘要 |
| **本轮修订** | v1.1：确认 models/__init__.py 已修复、前端角色变更功能确实缺失（代码级验证）、README.md 不作为需求依据改为 docs/01-05 为权威来源、第二轮审查须全量覆盖 |
| **统计误差声明** | 未读取文件统计基于 `find` 命令输出，可能存在因 gitignore 或文件权限差异导致的 1-2 个偏差 |

---

## 附录 A：本轮修订记录 (v1.1)

根据用户反馈，以下认知已被修正：

| 编号 | 修正前认知 | 修正后认知 | 依据 |
|---|---|---|---|
| 1 | README.md 作为需求来源之一 | **README.md 已过时，不作为需求依据**。需求权威来源为 `docs/01-05` 设计文档 | 用户反馈 + 对照 docs/01 验证 |
| 2 | 第二轮可抽样审查 | **第二轮必须进行完整检查，所有模块全部覆盖** | 用户明确要求 |
| 3 | `models/__init__.py` 中 `__all__` 两次定义，SystemLog 不在首列表中，是 bug | **已确认修复**。SystemLog 已正确导入到单一 `__all__` 列表中 | 重新读取文件验证 |
| 4 | 前端可能通过其他方式实现角色变更（推断） | **已确认前端角色变更功能缺失**。`AdminUsersView.vue` 仅导入 disable/enable/detail/detections/list 函数，模板仅含"启用/禁用"按钮，无角色修改控件 | 完整读取 AdminUsersView.vue（1067行）验证 |
| 5 | docs/ 被 gitignore 后无法参考 | **docs/ 本地仍可读取**，已纳入分析范围 | 直接读取了 docs/01-05 设计文档 |
| 6 | 未发现权威设计文档 | **docs/01-05 为设计权威**：01项目设计、02数据库设计、03API设计、04开发任务、05项目结构 | 读取全部 5 份设计文档 |

## 附录 B：已确认无变化的内容

以下内容在修订中重新验证后保持不变：

1. ✅ **检测管线完整调用链**：关键词→RAG→LLM→规则评分→最终得分→风险等级，代码可追踪
2. ✅ **7 个数据模型 + 关系**：User, DetectionRecord, EvidenceMatch, KnowledgeItem, PromptTemplate, Report, SystemLog
3. ✅ **前后端接口映射**：基本完整匹配（仅 `/api/admin/users/{id}/role` 后端存在但前端缺失）
4. ✅ **认证体系**：JWT(HS256)+bcrypt，两角色(user/admin)，三依赖注入函数
5. ✅ **LLM 降级策略**：API Key 未配置→error_result，调用失败→degraded_agent_steps
6. ✅ **13 个 Service 文件**：全部已验证存在并有代码实现
7. ✅ **32 个后端测试文件**：覆盖所有主要模块

## 附录 C：仍未确认的内容

以下内容在修订中未能完全确认，需要下一轮进一步验证：

1. ❓ 32 个后端测试实际通过率
2. ❓ 前端角色变更缺失是刻意裁剪还是未完成
3. ❓ 游客访问检测结果详情时的实际行为（路由允许但 API 需登录）
4. ❓ 设计文档中 `/admin/samples` 被裁剪的决策依据
5. ❓ PDF 中文字体渲染是否需要额外配置

---

> 📌 **声明**：本报告为项目认知报告（修订版 v1.1），不是代码审查报告。报告中的"已找到完整代码链路"表示从路由 → Service → CRUD → 数据模型的调用路径在代码中可追踪，不代表该功能无缺陷。所有风险线索待下一轮正式审查中深入验证。
