# 本地开发与配置指南

[返回项目首页](../README.md)

本文区分三个目标：验证页面与工程流程、接入真实模型、启用 v2 混合检索。hash 向量和预置演示结果不能用于证明语义检索或新闻判断效果。

## 1. 本地源码开发（PowerShell）

需要 Python 3.12、Node.js 22 与 npm、可连接的 MySQL 8.x。Docker 用户先按[首页快速启动](../README.md#quick-start)运行，无需另外安装本地 MySQL。

### 安装并准备配置

从仓库根目录开始：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-test.txt
Copy-Item backend/.env.example backend/.env
```

编辑 `backend/.env`：

- 填写 `DATABASE_HOST`、`DATABASE_PORT`、`DATABASE_USER`、`DATABASE_PASSWORD`、`DATABASE_NAME`。`DATABASE_URL` 如被设置，会优先于拆分配置。
- 替换 `SECRET_KEY` 和 `FIRST_SUPERUSER_PASSWORD`；使用随机密钥和自行设置的管理员密码。
- 保留 `APP_ENV=development`、`REDIS_ENABLED=false`、`ASYNC_DETECTION_ENABLED=false`，先运行同步流程。
- `REPORT_DIR=../data/reports` 必须位于 backend 源码目录之外；`CHROMA_PERSIST_DIR=../data/chroma` 指向本地向量目录。兼容变量 `CHROMA_PATH` 同时设置时优先。

初次无需模型密钥的体验，在 `backend/.env` 修改：

```dotenv
EMBEDDING_PROVIDER=hash
EMBEDDING_DIMENSION=384
DASHSCOPE_API_KEY=
DEEPSEEK_API_KEY=
BOCHA_API_KEY=
WEB_SEARCH_ENABLED=false
CRAWL_ENABLED=false
OTEL_TRACING_ENABLED=false
PYROSCOPE_ENABLED=false
```

请清空 Key，不要把非空占位字符串当作关闭集成的开关。没有真实 DeepSeek Key 时，新检测会降级为“无法判断”。这个模式用于检查页面、数据库、报告和异常状态；hash 不具有语义检索能力。用户主动使用链接提取仍会访问指定网址。

### 初始化数据库

在 MySQL 客户端创建与配置同名的数据库：

```sql
CREATE DATABASE zhiyun_bianzhen
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
```

在当前 PowerShell 窗口执行：

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m app.db.migrate
..\.venv\Scripts\python.exe -m app.db.init_db
```

迁移必须先于管理员初始化。`init_db` 使用 `FIRST_SUPERUSER_*` 创建管理员，不会通过修改该变量重设已存在账号的密码。

可选：仅在专用演示数据库中执行以下命令：

```powershell
..\.venv\Scripts\python.exe -m app.db.seed_demo_data
```

脚本创建或更新 `user_demo`、`user_demo2`、`admin_demo`，并写入演示知识、预置检测和报告。每次 seed 会重设这些演示账号密码；密码由控制台提供，也可通过 `DEMO_PASSWORD` 或 `ADMIN_DEMO_PASSWORD` 指定。不要将真实口令和运行日志提交到仓库。

演示记录不是实时模型效果。seed 将知识索引工作入队，API 启动后的调度器默认每 60 秒处理任务，因此首次看到 Chroma 计数为 0 可能正常。DashScope 模式下，后台消费任务才会请求外部 Embedding。

### 启动前后端

在刚才的 backend 目录中启动 API：

```powershell
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

打开第二个终端，从仓库根目录启动前端：

```powershell
npm --prefix frontend ci
npm --prefix frontend run dev
```

| 地址 | 用途 |
|---|---|
| <http://127.0.0.1:5173> | Vue 开发页面，Vite 将 `/api` 代理到 8000 端口 |
| <http://127.0.0.1:8000/docs> | development 模式的 Swagger |
| <http://127.0.0.1:8000/api/health> | 存活检查 |
| <http://127.0.0.1:8000/api/ready> | 就绪检查，当前不代表所有模型、数据库及向量依赖均可用 |

macOS/Linux 在仓库根目录使用 `.venv/bin/python`，进入 backend 后使用 `../.venv/bin/python`；用 `cp`、`cd` 替换 PowerShell 文件与目录命令。若 5173 被占用，以 Vite 实际输出的地址为准。

## 2. 接入真实模型与搜索

在本地 `backend/.env` 配置真实值：

```dotenv
EMBEDDING_PROVIDER=dashscope
EMBEDDING_DIMENSION=1024
DASHSCOPE_EMBEDDING_MODEL=text-embedding-v4
DASHSCOPE_API_KEY=replace_with_your_dashscope_key
DEEPSEEK_API_KEY=replace_with_your_deepseek_key
BOCHA_API_KEY=replace_with_your_bocha_key
WEB_SEARCH_ENABLED=true
CRAWL_ENABLED=false
```

- DeepSeek 模型名由 `DEEPSEEK_MODEL` 控制，按自己的供应商可用模型配置；模板中的模型名不代表所有账户均可使用。
- Bocha 只在需要联网能力时配置。定时抓取由 `CRAWL_ENABLED` 单独控制，首次联调保持关闭。
- 真实检测和语义知识索引可能产生供应商调用费用。
- 切换 Embedding 模型、维度或 RAG 索引版本后，需要重新生成知识索引；即使两个模型维度相同，也不能混用向量空间。
- 更换模型/维度时优先使用新 Chroma 目录，例如本地设置 `CHROMA_PERSIST_DIR=../data/chroma-dashscope-v4-1024`，并确认没有旧的 `CHROMA_PATH` 覆盖它。v2/hybrid 的普通重建只删除 v2 文档，不重建 collection，不能解除旧 collection 的维度约束。
- 修改本地 `.env` 后，停止并重新启动 API，再由管理员通过知识库索引重建入口或 `POST /api/admin/knowledge/rebuild-index` 重建，随后检查任务与知识同步状态。不要依赖自动 reload 重新读取 `.env`，也不要把删除数据库或所有数据卷当作常规升级方式。

### Docker 从 demo 切换到真实模型

在根目录 `.env` 设置 provider、dimension 和真实 API Key，同时将 `CRAWL_ENABLED`、`ASYNC_DETECTION_ENABLED`、`OTEL_TRACING_ENABLED`、`PYROSCOPE_ENABLED` 保持 `false`，按需设置 `WEB_SEARCH_ENABLED`。

下一次运行时**去掉 demo 覆盖文件**，否则它仍会清空 Key 并强制 hash 模式：

```powershell
docker compose -f docker-compose.yml up -d --wait backend worker
docker compose -f docker-compose.yml restart frontend
```

随后重建知识索引。默认 v1 路径的重建会重建 collection；如果同时切换到 v2，按下一节使用新目录后重建，不要直接在旧 hash/384 collection 上执行 v2 重建。切换运行模式不会自动删除或重建旧向量。模型名等当前未映射变量需要显式加入服务 environment；根目录 `.env` 不是自动传入所有容器的通用配置文件。重建 backend 容器后重启前端 Nginx，使代理重新解析服务地址。

<a id="rag-v2"></a>

## 3. 启用 v2 混合检索

默认是 `RAG_INDEX_VERSION=v1`。本地开发在 `backend/.env` 将该值修改为 `v2`，重启后端并重建知识索引；需要兼容回退时使用 `hybrid`。hybrid 写入 v2，读取时仅在 v2 无结果后尝试 v1，不是双写。

Compose 不会自动把根目录 `.env` 的所有变量传给容器。要启用 v2，创建以下**本地配置文件** `docker-compose.rag-v2.yml`：

```yaml
services:
  backend:
    environment:
      RAG_INDEX_VERSION: v2
      CHROMA_PERSIST_DIR: /data/chroma/dashscope-v4-1024-v2
  worker:
    environment:
      RAG_INDEX_VERSION: v2
      CHROMA_PERSIST_DIR: /data/chroma/dashscope-v4-1024-v2
```

完成上一节真实模型配置后，将它与基础文件一起使用，让 API 和 worker 保持一致：

```powershell
docker compose -f docker-compose.yml -f docker-compose.rag-v2.yml config --quiet
docker compose -f docker-compose.yml -f docker-compose.rag-v2.yml up -d --wait backend worker
docker compose -f docker-compose.yml -f docker-compose.rag-v2.yml restart frontend
```

上述子目录仍位于共享 Chroma 数据卷中，让 API 与 worker 使用同一份新索引，并保留原目录。若之后更换模型/维度，请另选新目录。随后执行知识库索引重建，检查同步状态，再验证返回结果中的 `retrieval_version`、`index_version`、分块和候选信息。启用 v2 只代表进入增强实现，不等于检索效果已经得到实验验证。

## 4. 可选异步、缓存与观测

- 本地 Redis 默认关闭；基础 Compose 显式开启 Redis。`AI_CACHE_ENABLED=true` 等缓存开关只有在 Redis 可用时才有实际效果。
- `ASYNC_DETECTION_ENABLED=true` 时，后端可以返回 HTTP 202 和 `task_id`，由客户端查询 `/api/detect/tasks/{task_id}`。当前 Vue 提交页尚未完整处理轮询，使用现有页面时保留 `false`。
- 知识索引任务由 APScheduler 扫描，与 Celery 检测任务分开。当前没有完整的多 Worker 原子领取与崩溃租约恢复能力。
- 基础 Compose 没有部署 Tempo/Pyroscope 等完整观测组件。根目录环境模板含生产观测选项，普通体验应关闭；需要完整组件时参考[部署文档](deployment/docker.md)和[运行手册](deployment/runbook.md)。

<a id="tests"></a>

## 5. 在隔离配置中运行检查

需要本机 Python 3.12、Node.js 22 与 npm。建议打开一个**专门用于测试的新 PowerShell 窗口**，从仓库根目录执行。尚未创建虚拟环境的 Docker 用户先执行 `python -m venv .venv`。下面变量仅影响该终端及其子进程；关闭窗口即可结束这组测试配置。

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-test.txt
$env:PYTHON_DOTENV_DISABLED = "1"
$env:APP_ENV = "testing"
$env:DATABASE_URL = "sqlite:///:memory:"
$env:SECRET_KEY = [Guid]::NewGuid().ToString("N")
$env:BACKEND_CORS_ORIGINS = "*"
$env:REDIS_ENABLED = "false"
$env:REDIS_REQUIRED = "false"
$env:EMBEDDING_PROVIDER = "hash"
$env:EMBEDDING_DIMENSION = "384"
$env:DEEPSEEK_API_KEY = ""
$env:DASHSCOPE_API_KEY = ""
$env:BOCHA_API_KEY = ""
$env:WEB_SEARCH_ENABLED = "false"
$env:CRAWL_ENABLED = "false"
$env:KNOWLEDGE_INDEX_JOB_ENABLED = "false"
$env:OTEL_TRACING_ENABLED = "false"
$env:PYROSCOPE_ENABLED = "false"

.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -t backend -p "test_*.py"
.\.venv\Scripts\python.exe -m pytest evaluation/tests -q
npm --prefix frontend ci
npm --prefix frontend test
npm --prefix frontend run build
git diff --check
```

这是测试专用密钥和数据库配置，不应作为部署配置。评测目录包含 pytest 函数，不能只运行 unittest 后就声称评测测试全部通过。

独立标题检索基线可从根目录运行：

```powershell
.\.venv\Scripts\python.exe -m evaluation.run_title_retrieval_baseline
```

该命令会写入基线结果；重新运行后应检查差异，不要把机器耗时变化当作算法改进。它不调用生产 RAG 或付费模型，发布指标时必须保留[评测说明](../evaluation/README.md)中的样本范围和限制。

## 6. 常见问题

| 现象 | 优先检查 |
|---|---|
| 启动报密钥或配置错误 | 是否替换 SECRET_KEY，占位符是否仍留在必需配置中，是否编辑了正确的环境文件 |
| 数据库表不存在或管理员初始化失败 | MySQL 是否可连接，是否先运行 `app.db.migrate`，数据库名是否一致 |
| 新检测显示“无法判断” | 当前是否为 demo 模式；区分模型失败 `degraded` 和证据不足 `insufficient_evidence` |
| 修改知识后暂时查不到 | 索引任务和同步状态是否完成；v2 会拒绝状态或版本指纹不匹配的 dense 候选 |
| 切换模型后向量维度不一致 | 是否同步修改维度并使用新目录重建；v2 普通重建不会解除旧 collection 维度约束 |
| Docker 设置 v2 后仍返回 v1 | 变量是否显式进入 backend/worker 的 environment，运行命令是否包含覆盖文件 |
| 开启异步后页面没有跳转 | 当前前端仍期待同步结果；恢复同步，或实现 task_id 查询流程 |
| Docker 下找不到 Swagger | Compose 默认 production 会关闭文档接口；源码 development 模式访问 8000 端口 |
| 报告目录校验失败 | `REPORT_DIR` 是否位于 backend 源码目录之外，以及目录是否可写 |

更多工程边界和验证范围见[发布验证记录](security/publication-2026-09-24.md)。
