# 智闻辨真：第七阶段演示环境快速入口

本项目是“基于 RAG 与大语言模型的新闻可信度评估系统”。第七阶段重点是联调测试、演示环境初始化、部署说明和答辩材料准备。

## 快速准备

1. 复制后端配置：

```powershell
cd E:\nan\NewsCredibilityEvaluator\backend
Copy-Item .env.example .env
```

2. 编辑 `backend/.env`，填写本地 MySQL 密码、`SECRET_KEY` 和可选的 `DEEPSEEK_API_KEY`。不要把真实密码或 API Key 提交到仓库。

当前后端支持两种 MySQL 配置。方式 A 是拆分字段：

```env
DATABASE_HOST=127.0.0.1
DATABASE_PORT=3306
DATABASE_USER=root
DATABASE_PASSWORD=请填写本机MySQL密码
DATABASE_NAME=zhiyun_bianzhen
SECRET_KEY=请替换为随机长字符串
DEEPSEEK_API_KEY=请替换为真实Key
CHROMA_PATH=../data/chroma
REPORT_DIR=../data/reports
BACKEND_CORS_ORIGINS=*
```

方式 B 是完整连接串；如果设置了 `DATABASE_URL`，它会优先生效：

```env
DATABASE_URL=mysql+pymysql://root:请填写本机MySQL密码@127.0.0.1:3306/zhiyun_bianzhen?charset=utf8mb4
```

3. 创建 MySQL 数据库：

```sql
CREATE DATABASE zhiyun_bianzhen
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
```

4. 初始化表和演示数据：

```powershell
cd E:\nan\NewsCredibilityEvaluator\backend
pip install -r requirements.txt
python -m app.db.init_db
python -m app.db.seed_demo_data
```

5. 启动服务：

```powershell
cd E:\nan\NewsCredibilityEvaluator\backend
uvicorn app.main:app --reload

cd E:\nan\NewsCredibilityEvaluator\frontend
npm install
npm run dev
```

访问地址：

```text
前端：http://127.0.0.1:5173
后端：http://127.0.0.1:8000
Swagger：http://127.0.0.1:8000/docs
```

## 演示账号

```text
普通用户：user_demo / 123456
普通用户：user_demo2 / 123456
管理员：admin_demo / 123456
```

## 演示数据

`python -m app.db.seed_demo_data` 会初始化：

- 30 条知识库数据，并同步到 Chroma；
- 最近 7 天检测记录，支撑统计趋势、风险分布、类别分布、关键词和用户活跃度；
- 多种审核状态的高风险新闻，其中用户端只展示 `approved + is_public`；
- 默认 Prompt 模板；
- 至少 1 条可生成 PDF 报告的检测记录。

Chroma 验证：seed 输出中的 `Chroma collection count` 应大于 0。

报告目录：默认 `REPORT_DIR=../data/reports`，实际路径会在 seed 输出中显示。

## 自检命令

```powershell
cd E:\nan\NewsCredibilityEvaluator\backend
python -m unittest discover -s tests -p "test_*.py"
python -m py_compile app/db/seed_demo_data.py app/core/config.py app/main.py app/db/init_db.py

cd E:\nan\NewsCredibilityEvaluator\frontend
npm run build

cd E:\nan\NewsCredibilityEvaluator
git diff --check
```

## 配置注意

- `.gitignore` 已忽略 `backend/.env`、`data/reports/` 和 `data/chroma/`。
- 真实 DeepSeek 检测必须配置 `DEEPSEEK_API_KEY`；演示 seed 不需要真实 Key。
- Chroma 目录优先使用 `CHROMA_PATH`，旧变量 `CHROMA_PERSIST_DIR` 仍可作为兼容别名。
- 如果使用旧数据库且缺少高风险审核字段，执行 `backend/migrations/20260604_add_high_risk_review_fields.sql`。
- `backend/.env.example` 只包含模板值，不包含真实 MySQL 密码、真实 DeepSeek API Key 或真实生产 `SECRET_KEY`。

## 真实联调检查

完成 `.env`、MySQL 建库和 seed 后，建议按下面顺序核验：

```powershell
cd E:\nan\NewsCredibilityEvaluator\backend
python -m app.db.init_db
python -m app.db.seed_demo_data
uvicorn app.main:app --reload
```

seed 输出里的 `Chroma collection count` 应大于 0。随后访问 `http://127.0.0.1:8000/docs`，用 `user_demo / 123456` 登录后验证：

- `GET /api/detect/history?keyword=台风` 能返回当前用户历史记录；
- `POST /api/report/generate/{detection_id}` 能生成报告；
- `GET /api/report/download/{report_id}` 需要登录态，前端历史页通过 Bearer Token 下载；
- `GET /api/high-risk/public` 只返回已审核且公开的高风险记录。

用 `admin_demo / 123456` 登录后验证：

- `GET /api/admin/statistics/overview` 有检测、用户、知识库和报告统计；
- `GET /api/admin/knowledge` 有 30 条左右演示知识库；
- `GET /api/admin/prompts` 有默认新闻可信度 Prompt；
- `GET /api/admin/high-risk` 能看到不同审核状态；
- 普通用户访问 `/api/admin/statistics/overview` 应返回 403。
