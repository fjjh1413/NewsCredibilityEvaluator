# 智闻辨真后端说明

本文档说明第一阶段后端如何安装、配置、启动和测试。

项目名称：

```text
智闻辨真：基于 RAG 与大语言模型的新闻可信度评估系统
```

第一阶段只完成后端基础能力：

- FastAPI 后端项目结构
- MySQL 连接配置
- SQLAlchemy 基础配置
- `users` 用户表 ORM
- 用户注册、登录、JWT 认证
- `user/admin` 角色区分
- 管理员权限测试接口
- 健康检查接口
- Swagger 接口文档

当前阶段暂未实现：

- 新闻检测接口
- Chroma 向量数据库
- DeepSeek API
- PDF 报告
- Vue 前端页面
- 真实后台管理功能

## 技术栈

```text
Python
FastAPI
Uvicorn
MySQL
SQLAlchemy
PyMySQL
Pydantic
python-jose
passlib + bcrypt
python-dotenv
```

## 目录结构

```text
backend/
├── app/
│   ├── api/
│   │   ├── router.py
│   │   └── v1/
│   │       ├── admin.py
│   │       ├── auth.py
│   │       └── health.py
│   ├── core/
│   │   ├── config.py
│   │   ├── deps.py
│   │   └── security.py
│   ├── crud/
│   │   └── user.py
│   ├── db/
│   │   ├── base.py
│   │   ├── base_class.py
│   │   ├── init_db.py
│   │   └── session.py
│   ├── models/
│   │   └── user.py
│   ├── schemas/
│   │   ├── auth.py
│   │   └── user.py
│   ├── services/
│   │   └── auth_service.py
│   ├── utils/
│   │   └── response.py
│   └── main.py
├── .env.example
├── requirements.txt
└── README.md
```

## 环境要求

- Python 3.10 或更高版本
- MySQL 8.x 或兼容版本
- PowerShell
- pip

查看 Python 版本：

```powershell
python --version
```

## 创建虚拟环境

进入后端目录：

```powershell
cd E:\nan\NewsCredibilityEvaluator\backend
```

创建虚拟环境：

```powershell
python -m venv .venv
```

启用虚拟环境：

```powershell
.\.venv\Scripts\Activate.ps1
```

如果 PowerShell 提示脚本执行策略限制，可以先执行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

然后重新启用虚拟环境。

## 安装依赖

```powershell
pip install -r requirements.txt
```

## 配置 .env

复制环境变量示例：

```powershell
Copy-Item .env.example .env
```

打开 `.env`，按本地 MySQL 信息修改：

```text
PROJECT_NAME=zhiyun-bianzhen-backend
PROJECT_VERSION=0.1.0
API_PREFIX=/api
BACKEND_CORS_ORIGINS=*

DATABASE_HOST=127.0.0.1
DATABASE_PORT=3306
DATABASE_USER=root
DATABASE_PASSWORD=your_mysql_password
DATABASE_NAME=zhiyun_bianzhen

SECRET_KEY=replace_with_a_long_random_secret
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

FIRST_SUPERUSER_USERNAME=admin
FIRST_SUPERUSER_PASSWORD=replace_with_admin_password
FIRST_SUPERUSER_EMAIL=admin@example.com
```

说明：

- `DATABASE_PASSWORD` 改成你的 MySQL 密码。
- `SECRET_KEY` 必须改成较长随机字符串，不要使用示例值。
- `FIRST_SUPERUSER_PASSWORD` 是初始化管理员账号的密码，也不要使用示例值。
- `.env` 不应提交到 Git。

## 创建 MySQL 数据库

登录 MySQL 后执行：

```sql
CREATE DATABASE zhiyun_bianzhen
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
```

如果你的 `.env` 中 `DATABASE_NAME` 使用了其他名称，建库 SQL 也要同步修改。

可以用下面的命令测试数据库连接：

```powershell
@'
from sqlalchemy import text
from app.db.session import engine

with engine.connect() as connection:
    result = connection.execute(text("SELECT 1")).scalar()
    print(f"database connection ok: {result}")
'@ | python -
```

看到下面输出代表连接正常：

```text
database connection ok: 1
```

## 初始化管理员账号

确保数据库已创建、`.env` 已配置后，执行：

```powershell
python -m app.db.init_db
```

这个命令会：

- 创建当前阶段已注册的数据库表，目前包括 `users` 和 `knowledge_items`；
- 从 `.env` 读取 `FIRST_SUPERUSER_USERNAME`、`FIRST_SUPERUSER_PASSWORD`、`FIRST_SUPERUSER_EMAIL`；
- 创建一个 `role=admin`、`status=active` 的管理员账号；
- 使用哈希方式保存密码，不保存明文密码。

重复运行不会重复创建同名管理员。如果管理员已存在，会输出跳过信息。

如果你是在第二阶段字段调整前已经创建过 `knowledge_items` 表，需要按实际缺失字段执行迁移。`vector_sync_status` 必须带数据库默认值：

```sql
ALTER TABLE knowledge_items
  ADD COLUMN vector_sync_status VARCHAR(20) NOT NULL DEFAULT 'pending',
  ADD COLUMN vector_sync_error TEXT NULL;
```

## 启动后端

在 `backend` 目录下执行：

```powershell
uvicorn app.main:app --reload
```

启动成功后，默认地址是：

```text
http://127.0.0.1:8000
```

## 访问 Swagger

浏览器打开：

```text
http://127.0.0.1:8000/docs
```

当前 Swagger 中应能看到：

- `GET /api/health`
- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `GET /api/admin/ping`

## 测试健康检查接口

浏览器打开：

```text
http://127.0.0.1:8000/api/health
```

或使用 PowerShell：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

预期返回：

```json
{
  "code": 200,
  "message": "service is running",
  "data": {
    "service": "zhiyun-bianzhen-backend",
    "status": "ok",
    "version": "0.1.0"
  }
}
```

## 测试注册登录接口

### 注册普通用户

在 Swagger 中调用：

```text
POST /api/auth/register
```

请求体：

```json
{
  "username": "test_user",
  "password": "123456",
  "email": "test@example.com"
}
```

预期返回：

```json
{
  "code": 200,
  "message": "注册成功",
  "data": {
    "id": 1,
    "username": "test_user",
    "role": "user"
  }
}
```

### 登录用户

调用：

```text
POST /api/auth/login
```

请求体：

```json
{
  "username": "test_user",
  "password": "123456"
}
```

预期返回：

```json
{
  "code": 200,
  "message": "登录成功",
  "data": {
    "access_token": "jwt_token_here",
    "token_type": "bearer",
    "user": {
      "id": 1,
      "username": "test_user",
      "role": "user"
    }
  }
}
```

### 获取当前用户

复制登录返回的 `access_token`。

在 Swagger 右上角点击 `Authorize`，填写：

```text
Bearer 你的access_token
```

然后调用：

```text
GET /api/auth/me
```

预期返回：

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": 1,
    "username": "test_user",
    "email": "test@example.com",
    "role": "user",
    "status": "active"
  }
}
```

不携带 Token 调用 `/api/auth/me` 会返回 `401`。

## 测试管理员权限

先执行初始化管理员账号：

```powershell
python -m app.db.init_db
```

使用 `.env` 中的管理员账号登录：

```json
{
  "username": "admin",
  "password": "你的FIRST_SUPERUSER_PASSWORD"
}
```

复制管理员登录返回的 `access_token`，在 Swagger 右上角 `Authorize` 中填写：

```text
Bearer 管理员access_token
```

调用：

```text
GET /api/admin/ping
```

预期返回：

```json
{
  "code": 200,
  "message": "admin pong",
  "data": {
    "username": "admin",
    "role": "admin",
    "status": "ok"
  }
}
```

普通用户访问 `/api/admin/ping` 会返回 `403`。
未登录访问 `/api/admin/ping` 会返回 `401`。

## 常见问题

### 1. `ModuleNotFoundError: No module named 'app'`

请确认命令是在 `backend` 目录下执行：

```powershell
cd E:\nan\NewsCredibilityEvaluator\backend
```

### 2. 数据库连接失败

请检查：

- MySQL 服务是否已启动；
- `.env` 中 `DATABASE_HOST`、`DATABASE_PORT` 是否正确；
- `DATABASE_USER` 和 `DATABASE_PASSWORD` 是否正确；
- 是否已创建 `zhiyun_bianzhen` 数据库。

### 3. `SECRET_KEY is not configured`

请检查 `.env` 中是否设置了：

```text
SECRET_KEY=replace_with_a_long_random_secret
```

并把示例值替换为你自己的随机字符串。

### 4. 登录失败

请检查：

- 用户是否已经注册；
- 密码是否正确；
- 用户 `status` 是否为 `active`；
- 初始化管理员后，是否使用了 `.env` 中的管理员密码。

### 5. 端口 8000 被占用

可以换一个端口启动：

```powershell
uvicorn app.main:app --reload --port 8001
```

然后访问：

```text
http://127.0.0.1:8001/docs
```
