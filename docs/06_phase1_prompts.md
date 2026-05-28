# 06_phase1_prompts.md

# 第一阶段开发提示词合集

> 项目名称：智闻辨真：基于 RAG 与大语言模型的新闻可信度评估系统  
> 本文档用于指导 Codex 完成第一阶段开发。  
> 第一阶段目标：先搭建稳定、规范、可运行的后端基础框架，为后续 RAG、DeepSeek、Vue 前端开发打基础。

---

## 1. 第一阶段开发目标

第一阶段不要追求完整业务功能，重点是搭建项目地基。

必须完成：

```text
1. FastAPI 后端基础项目结构
2. MySQL 数据库连接
3. SQLAlchemy ORM 配置
4. Pydantic Schema 规范
5. JWT 登录认证基础能力
6. 用户注册、登录、获取当前用户
7. user / admin 角色区分
8. 健康检查接口
9. Swagger 接口文档可访问
10. .env.example 环境变量示例
11. requirements.txt 依赖文件
```

第一阶段不要做：

```text
1. 不要做 Vue 前端
2. 不要接入 DeepSeek
3. 不要接入 Chroma
4. 不要做新闻检测
5. 不要做 PDF 报告
6. 不要做复杂后台管理
7. 不要一次性生成完整系统
```

---

## 2. 第一阶段推荐目录

第一阶段先创建后端目录即可：

```text
backend/
├── app/
│   ├── api/
│   │   ├── v1/
│   │   │   ├── auth.py
│   │   │   └── health.py
│   │   └── router.py
│   ├── core/
│   │   ├── config.py
│   │   ├── security.py
│   │   └── deps.py
│   ├── db/
│   │   ├── session.py
│   │   ├── base.py
│   │   └── init_db.py
│   ├── models/
│   │   └── user.py
│   ├── schemas/
│   │   ├── auth.py
│   │   └── user.py
│   ├── crud/
│   │   └── user.py
│   ├── services/
│   │   └── auth_service.py
│   ├── utils/
│   │   ├── response.py
│   │   └── exceptions.py
│   └── main.py
├── requirements.txt
├── .env.example
└── README.md
```

---

## 3. 使用 Codex 前的总提示词

第一次让 Codex 进入项目时，先发这个提示词：

```text
你现在是本项目的辅助开发工程师。

请先阅读 docs/01_project_design.md、docs/02_database_design.md、docs/03_api_design.md、docs/04_development_tasks.md、docs/05_project_structure.md、docs/06_phase1_prompts.md，理解本项目的业务目标、技术栈、目录规范和第一阶段开发范围。

项目名称：
智闻辨真：基于 RAG 与大语言模型的新闻可信度评估系统

技术栈：
后端：Python + FastAPI
前端：Vue3 + Element Plus + ECharts
数据库：MySQL
向量数据库：Chroma
大模型：DeepSeek API
认证方式：JWT

当前只进行第一阶段开发。

第一阶段目标：
1. 搭建 FastAPI 后端基础框架；
2. 配置 MySQL + SQLAlchemy；
3. 实现用户注册、登录、JWT 认证；
4. 支持 user/admin 角色；
5. 提供健康检查接口；
6. 确保 Swagger 文档可访问。

注意：
1. 不要开发新闻检测功能；
2. 不要接入 Chroma；
3. 不要接入 DeepSeek；
4. 不要开发前端；
5. 不要一次性生成完整系统；
6. 不要随意更改 docs 中规定的接口路径和数据库字段；
7. 修改前请先说明你准备新增或修改哪些文件；
8. 修改后请说明每个文件的作用、运行方式和测试方法。

请先输出你对第一阶段任务的理解，以及你准备创建的文件清单。暂时不要写代码。
```

---

## 4. 提示词 1：创建后端基础框架

```text
请开始实现第一阶段的后端基础框架。

任务范围：
1. 创建 backend/app 目录结构；
2. 创建 FastAPI 应用入口 app/main.py；
3. 创建统一路由注册文件 app/api/router.py；
4. 创建健康检查接口 GET /api/health；
5. 配置 CORS；
6. 配置统一响应格式；
7. 创建 requirements.txt；
8. 创建 .env.example；
9. 创建 backend/README.md。

目录必须符合 docs/05_project_structure.md 和 docs/06_phase1_prompts.md。

技术要求：
1. 使用 FastAPI；
2. 使用 uvicorn 启动；
3. 健康检查接口返回系统名称、状态、版本；
4. Swagger 文档地址应为 /docs；
5. 不要实现用户登录注册；
6. 不要连接数据库；
7. 不要接入 Chroma 或 DeepSeek。

完成后请说明：
1. 新增了哪些文件；
2. 每个文件的作用；
3. 如何安装依赖；
4. 如何启动后端；
5. 如何访问健康检查接口；
6. 如何访问 Swagger 文档。
```

### 验收标准

```text
1. backend/app/main.py 存在；
2. 启动命令 uvicorn app.main:app --reload 可用；
3. 浏览器访问 http://127.0.0.1:8000/docs 正常；
4. GET /api/health 返回正常；
5. 没有把所有逻辑写进 main.py。
```

---

## 5. 提示词 2：配置 MySQL 与 SQLAlchemy

```text
请在现有 FastAPI 后端基础上配置 MySQL 数据库连接和 SQLAlchemy。

任务范围：
1. 创建 app/core/config.py；
2. 创建 app/db/session.py；
3. 创建 app/db/base.py；
4. 从 .env 读取数据库连接信息；
5. 在 .env.example 中补充数据库配置示例；
6. 添加数据库连接测试说明。

技术要求：
1. 使用 SQLAlchemy；
2. 使用 pymysql 或 mysqlclient 连接 MySQL；
3. 不要把数据库账号密码写死在代码里；
4. 配置项必须从环境变量读取；
5. 暂时不创建业务表；
6. 不要实现登录注册；
7. 不要修改健康检查接口的路径。

环境变量建议：
DATABASE_HOST
DATABASE_PORT
DATABASE_USER
DATABASE_PASSWORD
DATABASE_NAME

完成后请说明：
1. 数据库连接配置在哪里；
2. 如何创建 MySQL 数据库；
3. 如何配置 .env；
4. 如何验证数据库连接是否正常；
5. 修改了哪些文件。
```

### 验收标准

```text
1. .env.example 有数据库配置；
2. config.py 能读取环境变量；
3. session.py 有 SQLAlchemy engine 和 SessionLocal；
4. 没有硬编码数据库密码；
5. 原有 /api/health 仍然可用。
```

---

## 6. 提示词 3：创建用户表 ORM 与 Schema

```text
请创建用户表对应的 SQLAlchemy ORM 模型和 Pydantic Schema。

任务范围：
1. 创建 app/models/user.py；
2. 创建 app/schemas/user.py；
3. 创建 app/schemas/auth.py；
4. 在 app/db/base.py 中注册 User 模型；
5. 用户表字段必须符合 docs/02_database_design.md。

用户表字段：
id
username
password_hash
role
email
status
created_at
updated_at

角色：
user
admin

状态：
active
disabled

要求：
1. username 唯一；
2. email 可以为空，但如果填写需要唯一；
3. password_hash 不允许为空；
4. role 默认 user；
5. status 默认 active；
6. 不要存储明文密码；
7. 不要实现接口；
8. 不要修改已有接口路径。

完成后请说明：
1. User 模型字段；
2. Pydantic Schema 类型；
3. 数据库表名；
4. 如何创建表。
```

### 验收标准

```text
1. User ORM 模型存在；
2. UserCreate、UserLogin、UserResponse 等 Schema 存在；
3. 响应模型不返回 password_hash；
4. role 和 status 有默认值；
5. 代码层次清晰。
```

---

## 7. 提示词 4：实现密码加密与 JWT 工具

```text
请实现密码加密和 JWT 工具函数。

任务范围：
1. 创建或完善 app/core/security.py；
2. 实现密码哈希函数；
3. 实现密码校验函数；
4. 实现 JWT Token 生成函数；
5. 实现 JWT Token 解析函数；
6. 在 .env.example 中增加 JWT 配置。

JWT 配置建议：
SECRET_KEY
ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES

技术要求：
1. 密码必须使用安全哈希算法，例如 passlib[bcrypt]；
2. JWT 使用 python-jose 或 PyJWT；
3. SECRET_KEY 必须从环境变量读取；
4. 不要把 SECRET_KEY 写死；
5. 不要实现登录接口；
6. 不要修改数据库连接配置。

完成后请说明：
1. 使用了哪些依赖；
2. 新增了哪些安全函数；
3. Token 中包含哪些信息；
4. 如何配置 SECRET_KEY。
```

### 验收标准

```text
1. 密码不会明文保存；
2. verify_password 可用；
3. create_access_token 可用；
4. decode_token 可用；
5. SECRET_KEY 来自环境变量。
```

---

## 8. 提示词 5：实现用户 CRUD 和认证服务

```text
请实现用户相关 CRUD 和认证业务服务。

任务范围：
1. 创建 app/crud/user.py；
2. 创建 app/services/auth_service.py；
3. 实现根据 username 查询用户；
4. 实现创建用户；
5. 实现校验用户名和密码；
6. 实现注册时用户名重复检查；
7. 实现登录时账号状态检查。

要求：
1. CRUD 层只写数据库操作；
2. auth_service 层负责注册和登录业务逻辑；
3. 不要在 api 层直接写数据库查询；
4. 不要实现接口；
5. 不要开发前端；
6. 不要接入新闻检测功能。

完成后请说明：
1. CRUD 层提供了哪些函数；
2. auth_service 提供了哪些函数；
3. 注册和登录的业务流程；
4. 异常情况如何处理。
```

### 验收标准

```text
1. 用户查询和创建逻辑在 crud/user.py；
2. 注册和登录业务在 auth_service.py；
3. 密码加密逻辑被正确调用；
4. 登录时会校验密码；
5. 禁用用户不能登录。
```

---

## 9. 提示词 6：实现注册、登录和当前用户接口

```text
请实现用户注册、登录和获取当前用户接口。

接口路径必须为：
POST /api/auth/register
POST /api/auth/login
GET  /api/auth/me

任务范围：
1. 创建或完善 app/api/v1/auth.py；
2. 在 app/api/router.py 中注册认证路由；
3. 实现注册接口；
4. 实现登录接口；
5. 实现获取当前用户接口；
6. 创建 app/core/deps.py，用于获取当前登录用户；
7. 登录成功后返回 JWT Token。

要求：
1. 请求和响应必须使用 Pydantic Schema；
2. 注册时不能返回 password_hash；
3. 登录失败要返回明确错误；
4. 被禁用用户不能登录；
5. GET /api/auth/me 必须校验 Token；
6. 不要实现新闻检测；
7. 不要开发前端。

完成后请说明：
1. 每个接口的请求参数；
2. 每个接口的返回示例；
3. 如何在 Swagger 中测试；
4. 如何携带 Bearer Token 调用 /api/auth/me。
```

### 验收标准

```text
1. POST /api/auth/register 可注册用户；
2. POST /api/auth/login 可返回 access_token；
3. GET /api/auth/me 携带 Token 后可返回当前用户；
4. 不携带 Token 访问 /api/auth/me 会失败；
5. Swagger 文档可正常显示认证接口。
```

---

## 10. 提示词 7：实现管理员权限依赖

```text
请实现管理员权限校验依赖。

任务范围：
1. 在 app/core/deps.py 中增加 get_current_admin；
2. get_current_admin 依赖 get_current_user；
3. 当前用户 role 必须为 admin 才能访问管理员接口；
4. 创建一个测试接口 GET /api/admin/ping；
5. 只有 admin 用户可以访问该接口。

要求：
1. 普通 user 访问 /api/admin/ping 应返回权限不足；
2. 未登录用户访问应返回未认证；
3. admin 用户访问应返回成功；
4. 不要实现真正的后台管理功能；
5. 不要开发前端。

完成后请说明：
1. 管理员权限如何判断；
2. 如何创建 admin 测试账号；
3. 如何测试普通用户和管理员用户的权限差异。
```

### 验收标准

```text
1. get_current_admin 可用；
2. GET /api/admin/ping 存在；
3. 普通用户不能访问管理员测试接口；
4. admin 用户可以访问；
5. 权限逻辑没有写死某个用户名。
```

---

## 11. 提示词 8：初始化管理员账号和默认数据

```text
请实现数据库初始化脚本，用于创建默认管理员账号。

任务范围：
1. 完善 app/db/init_db.py；
2. 支持创建默认 admin 用户；
3. 默认账号和密码从 .env 读取；
4. 如果管理员已存在，不重复创建；
5. 在 README.md 中说明初始化方式。

环境变量建议：
FIRST_SUPERUSER_USERNAME
FIRST_SUPERUSER_PASSWORD
FIRST_SUPERUSER_EMAIL

要求：
1. 默认密码不能写死在代码里；
2. 初始化逻辑可以通过命令手动执行；
3. 不要影响正常应用启动；
4. 不要创建新闻知识库数据；
5. 不要接入 Chroma 或 DeepSeek。

完成后请说明：
1. 初始化脚本如何运行；
2. 管理员账号如何配置；
3. 重复运行会不会重复创建；
4. 修改了哪些文件。
```

### 验收标准

```text
1. 可以创建默认 admin；
2. 重复运行不重复创建；
3. 密码加密存储；
4. 配置来自 .env；
5. README 有说明。
```

---

## 12. 提示词 9：补充 README 和运行说明

```text
请完善 backend/README.md，写清楚第一阶段后端如何运行和测试。

README 至少包括：
1. 项目简介；
2. 技术栈；
3. 目录结构；
4. 环境要求；
5. 创建虚拟环境；
6. 安装依赖；
7. 配置 .env；
8. 创建 MySQL 数据库；
9. 启动后端；
10. 访问 Swagger；
11. 测试健康检查接口；
12. 测试注册登录接口；
13. 初始化管理员账号；
14. 常见问题。

要求：
1. 面向初学者；
2. 命令要可复制；
3. 不要写不存在的功能；
4. 不要提新闻检测已完成；
5. 不要夸大项目进度。
```

### 验收标准

```text
1. 初学者能按 README 启动项目；
2. README 不包含尚未实现功能的使用说明；
3. 有 Swagger 地址；
4. 有 .env 配置说明；
5. 有注册登录测试说明。
```

---

## 13. 第一阶段总验收清单

完成第一阶段后，你需要手动检查：

```text
1. 后端能启动；
2. Swagger 能打开；
3. /api/health 正常；
4. MySQL 能连接；
5. users 表能创建；
6. 用户能注册；
7. 用户能登录；
8. 登录后能拿到 JWT；
9. 携带 JWT 能访问 /api/auth/me；
10. 普通用户不能访问 admin 测试接口；
11. admin 用户能访问 admin 测试接口；
12. README 写清楚运行方式；
13. .env.example 不包含真实密码；
14. requirements.txt 依赖完整；
15. 代码没有把所有逻辑堆在 main.py。
```

---

## 14. 第一阶段代码审查提示词

当 Codex 完成第一阶段后，复制下面这段让它自查：

```text
请对第一阶段代码进行一次严格代码审查。

重点检查：
1. 是否符合 docs/05_project_structure.md 的目录规范；
2. 是否存在把业务逻辑堆到 main.py 或 api 层的问题；
3. 数据库配置是否从 .env 读取；
4. 是否存在明文密码存储；
5. JWT SECRET_KEY 是否硬编码；
6. 注册登录接口是否有基本异常处理；
7. /api/auth/me 是否正确校验 Token；
8. admin 权限是否根据 role 判断；
9. Swagger 文档是否正常；
10. README 是否和实际功能一致；
11. 是否存在未实现但声称已实现的功能；
12. 是否有可以优化的地方。

请输出：
1. 已完成内容；
2. 发现的问题；
3. 修改建议；
4. 是否需要立即修复；
5. 下一阶段开发前的注意事项。
```

---

## 15. Bug 修复提示词模板

如果运行报错，不要直接让 Codex 乱改。使用这个模板：

```text
我运行项目时遇到了错误。请你只针对这个错误进行分析和修复，不要重构无关代码。

错误信息如下：
【粘贴完整报错】

当前操作：
【例如：启动后端 / 注册用户 / 登录 / 访问 Swagger】

要求：
1. 先分析错误原因；
2. 说明可能涉及哪些文件；
3. 给出最小修改方案；
4. 不要改动无关功能；
5. 修复后说明如何重新测试；
6. 如果需要我提供更多信息，请明确说明需要哪一项。
```

---

## 16. 提交 Git 前检查提示词

每完成一个小阶段，可以让 Codex 帮你检查是否适合提交：

```text
请检查当前代码是否适合进行一次 Git 提交。

请输出：
1. 本阶段完成了哪些功能；
2. 修改了哪些文件；
3. 是否存在敏感信息，例如 API Key、数据库密码；
4. 是否存在临时文件、缓存文件、无关文件；
5. .gitignore 是否需要补充；
6. 推荐的 Git commit message；
7. 下一步开发建议。
```

推荐提交信息：

```text
feat: initialize FastAPI backend structure
feat: add MySQL SQLAlchemy configuration
feat: add user auth with JWT
feat: add admin role dependency
docs: add backend setup guide
```

---

## 17. 第一阶段完成后的下一步

第一阶段完成后，不要立刻开发前端。  
建议进入第二阶段：

```text
第二阶段：知识库 MySQL 管理模块
```

第二阶段目标：

```text
1. 创建 knowledge_items 表；
2. 实现管理员知识库增删改查；
3. 支持新闻标题、正文、类别、真实性标签、来源、摘要、关键词等字段；
4. 为后续 Chroma 向量化做准备。
```

进入第二阶段前，必须确保：

```text
1. 登录认证已经稳定；
2. admin 权限已经稳定；
3. MySQL 连接没有问题；
4. Swagger 能测试接口；
5. 目录结构没有混乱。
```
