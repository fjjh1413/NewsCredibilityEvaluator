# 智闻辨真后端演示环境说明

本文档用于第七阶段联调测试、部署准备和课程答辩演示。当前后端包含用户注册登录、新闻检测、RAG 知识库、Prompt 模板、PDF 报告、管理员统计和高风险新闻审核公开等能力。

## 1. 环境变量

后端不会提交真实本地配置。首次运行请复制环境变量模板：

```powershell
cd E:\nan\NewsCredibilityEvaluator\backend
Copy-Item .env.example .env
```

然后编辑 `backend/.env`：

- `DATABASE_HOST`、`DATABASE_PORT`、`DATABASE_USER`、`DATABASE_PASSWORD`、`DATABASE_NAME`：MySQL 连接信息，不要提交真实密码。
- `DATABASE_URL`：可选完整 SQLAlchemy 连接串；如果设置，会优先生效。
- `SECRET_KEY`：JWT 密钥，演示以外环境请改成足够长的随机字符串。
- `DEEPSEEK_API_KEY`：真实检测流程需要填写，不要提交真实 Key。
- `DASHSCOPE_API_KEY`：正式 RAG/答辩演示的 DashScope `text-embedding-v4` 语义 embedding 需要填写，不要提交真实 Key。
- `EMBEDDING_PROVIDER`：正式 RAG/答辩演示使用 `dashscope`；本地无 API Key 时可临时改为 `hash` fallback。
- `EMBEDDING_DIMENSION`：需与 embedding 模型输出一致，`text-embedding-v4` 推荐使用 `1024`，hash fallback 使用 `384`。
- `CHROMA_PATH`：Chroma 向量库目录，默认建议 `../data/chroma`；旧变量 `CHROMA_PERSIST_DIR` 仍可作为兼容别名。
- `REPORT_DIR`：PDF 报告目录，默认建议 `../data/reports`，必须在 `backend` 源码目录之外。
- `BACKEND_CORS_ORIGINS`：本地演示可用 `*`，部署时建议改为前端域名。

如果 `backend/.env` 缺失，接口会返回明确的数据库配置提示；请优先检查配置文件和 MySQL 服务，而不是把它当作代码逻辑错误。

## 2. MySQL 初始化

先创建数据库：

```sql
CREATE DATABASE zhiyun_bianzhen
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
```

安装依赖并执行 Alembic 迁移：

```powershell
cd E:\nan\NewsCredibilityEvaluator\backend
pip install -r requirements.txt
python -m app.db.migrate
```

然后初始化管理员账号：

```powershell
python -m app.db.init_db
```

旧 SQL 文件已归档到 `migrations/legacy_sql/`，仅用于追溯历史变更。当前数据库结构以 Alembic 版本为准，不再手工执行 legacy SQL。

## 3. 导入演示数据

执行：

```powershell
cd E:\nan\NewsCredibilityEvaluator\backend
python -m app.db.seed_demo_data
```

seed 脚本会重复执行且不会无限新增重复演示数据。它会初始化：

- 2 个普通用户和 1 个管理员用户；
- 30 条课程答辩知识库数据；
- Chroma 知识库向量；
- 最近 7 天分布的检测记录；
- 高风险新闻审核状态和公开状态；
- 默认新闻可信度 Prompt 模板；
- 至少 1 条可用于 PDF 报告生成的检测记录。

演示账号：

```text
普通用户：user_demo
普通用户：user_demo2
管理员：admin_demo
```

演示密码：运行 `python -m app.db.seed_demo_data` 后查看控制台输出；如需固定本地演示密码，可在执行 seed 前设置 `DEMO_PASSWORD` 或 `ADMIN_DEMO_PASSWORD`。

## 4. 启动后端

```powershell
cd E:\nan\NewsCredibilityEvaluator\backend
uvicorn app.main:app --reload
```

访问地址：

```text
后端：http://127.0.0.1:8000
Swagger：http://127.0.0.1:8000/docs
```

## 5. Chroma 与报告目录验证

seed 成功后会输出：

```text
Chroma collection count=<大于 0 的数字>
REPORT_DIR=<实际报告目录>
CHROMA_PATH=<实际向量库目录>
```

如果 Chroma count 为 0 或获取失败，请检查：

- `chromadb` 是否已通过 `pip install -r requirements.txt` 安装；
- `CHROMA_PATH` 是否可写；
- 是否执行过 `python -m app.db.seed_demo_data`。
- 是否在切换 `EMBEDDING_PROVIDER` 或 `EMBEDDING_DIMENSION` 后重建过 Chroma 知识库索引。

切换 embedding provider 或维度后，必须重建 Chroma 索引，避免维度不匹配或旧向量影响检索。可删除旧 `CHROMA_PATH` 后重新执行 `python -m app.db.seed_demo_data`，或用管理员账号调用 `POST /api/admin/knowledge/rebuild-index`。

PDF 报告默认保存到 `REPORT_DIR`，例如 `E:\nan\NewsCredibilityEvaluator\data\reports`。

## 6. 联调自检命令

后端：

```powershell
cd E:\nan\NewsCredibilityEvaluator\backend
python -m unittest discover -s tests -p "test_*.py"
python -m app.db.migrate
python -m app.db.init_db
python -m app.db.seed_demo_data
uvicorn app.main:app --reload
```

前端：

```powershell
cd E:\nan\NewsCredibilityEvaluator\frontend
npm install
npm run dev
npm run build
```

当前 Vite 配置默认端口是 `5173`，如果端口被占用会自动选择下一个端口。前端默认通过 Vite proxy 将 `/api` 转发到 `http://127.0.0.1:8000`。

## 7. 演示验证路径

普通用户：

```text
登录 user_demo
→ 新闻检测
→ 检测结果页
→ 生成并下载 PDF 报告
→ 历史记录
→ 查看公开高风险新闻
```

管理员：

```text
登录 admin_demo
→ 后台统计
→ 知识库管理
→ Prompt 模板管理
→ 报告管理
→ 高风险新闻管理
→ 审核状态和公开状态切换
```

真实 DeepSeek 检测流程需要在 `backend/.env` 中填写 `DEEPSEEK_API_KEY`；默认 DashScope 语义 embedding 需要填写 `DASHSCOPE_API_KEY`。未配置 Key 时，系统应给出明确提示；仅本地演示 Chroma 流程时可临时设置 `EMBEDDING_PROVIDER=hash`、`EMBEDDING_DIMENSION=384`。hash 不具备语义检索能力，不应作为正式 RAG 方案。

## 8. 真实联调检查

`.env`、MySQL 数据库和 seed 都准备好后，建议按下面顺序验证：

```powershell
cd E:\nan\NewsCredibilityEvaluator\backend
python -m app.db.migrate
python -m app.db.init_db
python -m app.db.seed_demo_data
uvicorn app.main:app --reload
```

重点确认：

- seed 输出的 `Chroma collection count` 大于 0；
- 使用 seed 控制台输出或环境变量设置的演示密码，`user_demo` 可以登录；
- `GET /api/detect/history?keyword=台风` 可以按关键词筛选历史记录；
- 历史页报告下载使用 Bearer Token，不再通过裸 `<a href>` 下载；
- 使用同一演示密码，`admin_demo` 可以进入后台统计、知识库、Prompt、报告和高风险管理；
- 普通用户访问管理员接口返回 403；
- 配置真实 `DEEPSEEK_API_KEY` 后，`POST /api/detect/news` 可以进入真实检测流程。
