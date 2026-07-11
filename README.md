# 智闻辨真：基于 RAG 与大语言模型的新闻可信度评估系统

智闻辨真是一个面向课程答辩和简历展示的新闻可信度评估系统。用户输入新闻标题和正文后，系统会检索知识库相似证据，调用 DeepSeek 进行可信度分析，结合规则评分生成最终可信度分数、风险等级、判断理由、风险点、相似证据和 PDF 报告。

当前项目已进入第七阶段，重点是联调测试、演示环境初始化、部署说明、代码审查和答辩材料准备。

## 技术栈

| 层级 | 技术 |
|---|---|
| 后端 | FastAPI、SQLAlchemy、Pydantic、JWT、bcrypt |
| 前端 | Vue 3、Vite、Element Plus、Pinia、Vue Router、ECharts |
| 数据库 | MySQL |
| 向量数据库 | Chroma |
| 大模型 | DeepSeek |
| 报告 | HTML 模板、PDF 导出 |

## 核心功能

- 用户注册、登录、JWT 鉴权和管理员权限控制。
- 新闻标题与正文检测，支持游客和登录用户提交。
- RAG 知识库检索，从 Chroma 召回相似新闻和核查证据。
- DeepSeek 可信度分析，结合 Prompt 模板和检索证据生成结构化结果。
- 规则评分，检查来源缺失、夸张表达、情绪化用词、绝对化表述和证据冲突。
- 综合评分，输出可信新闻、存疑信息、疑似谣言、高风险谣言等风险等级。
- 检测历史、结果详情、相似证据、风险点和建议展示。
- PDF 报告生成与下载。
- 管理员后台：知识库管理、Prompt 模板管理、报告管理、高风险新闻审核、统计图表。
- 演示数据初始化，支持课程答辩快速启动。

## 项目结构

```text
NewsCredibilityEvaluator/
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── api/             # 路由层
│   │   ├── core/            # 配置、安全、依赖、常量
│   │   ├── crud/            # 数据库 CRUD
│   │   ├── db/              # 数据库连接、迁移检查、演示数据
│   │   ├── models/          # SQLAlchemy 模型
│   │   ├── schemas/         # Pydantic schema
│   │   ├── services/        # 业务逻辑、RAG、LLM、评分、报告
│   │   ├── templates/       # 报告模板
│   │   └── utils/           # 通用工具
│   ├── alembic/             # Alembic 迁移配置与版本
│   ├── migrations/          # legacy_sql 旧 SQL 归档
│   └── tests/               # 后端测试
├── frontend/                # Vue3 前端
│   └── src/
│       ├── api/             # 接口封装
│       ├── components/      # 通用组件
│       ├── layouts/         # 用户端和管理端布局
│       ├── router/          # 路由与权限守卫
│       ├── stores/          # Pinia 状态
│       ├── utils/           # 请求、缓存、格式化工具
│       └── views/           # 页面
├── data/                    # 本地 Chroma 和报告目录，默认不提交
├── docs/                    # 设计、开发、审查和答辩文档
├── CLAUDE.md                # Claude Code 项目上下文
└── README.md
```

## 快速启动

### 1. 准备后端配置

```powershell
cd E:\nan\NewsCredibilityEvaluator\backend
Copy-Item .env.example .env
```

编辑 `backend/.env`，填写本地 MySQL 密码、`SECRET_KEY`、用于检测分析的 `DEEPSEEK_API_KEY`，以及用于正式 RAG 语义 embedding 的 `DASHSCOPE_API_KEY`。正式 RAG/答辩演示默认使用 DashScope `text-embedding-v4`；本地没有 DashScope API Key 时，可以临时改用 hash fallback。不要提交真实密码、真实 API Key 或生产密钥。

方式 A：拆分 MySQL 字段。

```env
DATABASE_HOST=127.0.0.1
DATABASE_PORT=3306
DATABASE_USER=root
DATABASE_PASSWORD=请填写本机MySQL密码
DATABASE_NAME=zhiyun_bianzhen
SECRET_KEY=请替换为随机长字符串
DEEPSEEK_API_KEY=请替换为真实Key
DASHSCOPE_API_KEY=请替换为真实Key
EMBEDDING_PROVIDER=dashscope
EMBEDDING_DIMENSION=1024
CHROMA_PATH=../data/chroma
REPORT_DIR=../data/reports
BACKEND_CORS_ORIGINS=*
```

本地仅验证 Chroma 流程且没有 `DASHSCOPE_API_KEY` 时，可临时设置 `EMBEDDING_PROVIDER=hash`、`EMBEDDING_DIMENSION=384`。hash 只是不具备语义能力的本地演示 fallback，不作为正式 RAG 检索方案。

方式 B：完整连接串。如果设置了 `DATABASE_URL`，它会优先生效。

```env
DATABASE_URL=mysql+pymysql://root:请填写本机MySQL密码@127.0.0.1:3306/zhiyun_bianzhen?charset=utf8mb4
```

### 2. 创建 MySQL 数据库

```sql
CREATE DATABASE zhiyun_bianzhen
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
```

### 3. 初始化后端和演示数据

```powershell
cd E:\nan\NewsCredibilityEvaluator\backend
pip install -r requirements.txt
python -m app.db.migrate
python -m app.db.init_db
python -m app.db.seed_demo_data
```

`seed_demo_data` 会初始化用户、知识库、Chroma 向量、检测记录、高风险新闻、Prompt 模板和可用于 PDF 报告的演示记录。输出中的 `Chroma collection count` 应大于 0。切换 `EMBEDDING_PROVIDER` 或 `EMBEDDING_DIMENSION` 后，必须重新生成 Chroma 知识库向量；可删除旧 `CHROMA_PATH` 数据后重新执行 seed，或以管理员调用 `POST /api/admin/knowledge/rebuild-index`。

### 4. 启动后端

```powershell
cd E:\nan\NewsCredibilityEvaluator\backend
uvicorn app.main:app --reload
```

```text
后端：http://127.0.0.1:8000
Swagger：http://127.0.0.1:8000/docs
```

### 5. 启动前端

```powershell
cd E:\nan\NewsCredibilityEvaluator\frontend
npm install
npm run dev
```

```text
前端：http://127.0.0.1:5173
```

前端默认通过 `/api` 访问后端。真实 DeepSeek 检测需要在 `backend/.env` 中配置 `DEEPSEEK_API_KEY`；演示数据初始化不依赖真实 Key。

## 演示账号

```text
普通用户：user_demo
普通用户：user_demo2
管理员：admin_demo
```

演示密码：运行 `python -m app.db.seed_demo_data` 后查看控制台输出；如需固定本地演示密码，可在执行 seed 前设置 `DEMO_PASSWORD` 或 `ADMIN_DEMO_PASSWORD`。

## 演示流程

普通用户流程：

```text
登录 user_demo
→ 新闻检测
→ 查看检测结果
→ 生成并下载 PDF 报告
→ 查看历史记录
→ 查看公开高风险新闻
```

管理员流程：

```text
登录 admin_demo
→ 后台统计
→ 知识库管理
→ Prompt 模板管理
→ 报告管理
→ 高风险新闻管理
→ 审核状态和公开状态切换
```

## 自检命令

后端测试和语法检查：

```powershell
cd E:\nan\NewsCredibilityEvaluator\backend
python -m unittest discover -s tests -p "test_*.py"
python -m py_compile app/db/seed_demo_data.py app/core/config.py app/main.py app/db/init_db.py app/db/migration_guard.py app/db/migrate.py
```

前端构建：

```powershell
cd E:\nan\NewsCredibilityEvaluator\frontend
npm run build
```

Git 空白检查：

```powershell
cd E:\nan\NewsCredibilityEvaluator
git diff --check
```

## 联调检查清单

完成 `.env`、MySQL 建库、Alembic 迁移和 seed 后，建议依次验证：

- `Chroma collection count` 大于 0。
- 使用 seed 控制台输出或环境变量设置的演示密码，`user_demo` 可以登录。
- `POST /api/detect/news` 可以提交检测。
- `GET /api/detect/history?keyword=台风` 能返回当前用户历史记录。
- `POST /api/report/generate/{detection_id}` 能生成报告。
- `GET /api/report/download/{report_id}` 需要登录态。
- `GET /api/high-risk/public` 只返回已审核且公开的高风险记录。
- 使用同一演示密码，`admin_demo` 可以访问后台统计、知识库、Prompt、报告和高风险管理。
- 普通用户访问 `/api/admin/statistics/overview` 应返回 403。

## 配置与安全注意

- `backend/.env`、`data/reports/`、`data/chroma/`、`backend/chroma_db/`、`node_modules/`、`dist/` 不应提交。
- `backend/.env.example` 只能保留模板值，不应包含真实 MySQL 密码、真实 DeepSeek / DashScope API Key 或真实生产 `SECRET_KEY`。
- 本地演示可以使用 `BACKEND_CORS_ORIGINS=*`；部署时建议改为明确的前端域名。
- `REPORT_DIR` 建议放在后端源码目录之外，例如 `../data/reports`。
- 数据库结构以 Alembic 为准，初始化或导入演示数据前先执行 `python -m app.db.migrate` 或 `alembic upgrade head`。旧 SQL 已归档到 `backend/migrations/legacy_sql/`，仅作历史参考，不再手工执行。
- 默认推荐配置使用 DashScope `text-embedding-v4` 语义 embedding。`hash` embedding 只适合本地无 API Key 时演示 Chroma 流程，不代表真实语义检索能力，也不应作为正式 RAG 方案。
- 切换 `EMBEDDING_PROVIDER` 或 `EMBEDDING_DIMENSION` 后必须重建 Chroma 知识库索引，否则可能出现维度不匹配或旧向量检索结果不可靠。



## 相关文档

- `CLAUDE.md`：Claude Code 项目上下文和关键架构说明。
- `backend/README.md`：后端演示环境与联调说明。
- `docs/01_project_design.md`：项目设计说明。
- `docs/02_database_design.md`：数据库设计。
- `docs/03_api_design.md`：API 设计。
- `docs/12_phase7_testing_deployment_prompts.md`：第七阶段测试、部署和答辩材料。
- `docs/claude_code_review_prompt.md`：代码审查提示词。
- `docs/enterprise_code_review_prompt.md`：企业级项目审查提示词。
