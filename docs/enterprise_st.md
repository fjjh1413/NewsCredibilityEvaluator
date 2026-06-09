# 企业级代码审查报告

## 项目：智闻辨真 — 基于 RAG 与大语言模型的新闻可信度评估系统

**审查日期**：2026-06-07

**审查范围**：后端 73 个 Python 文件、前端 50+ Vue/JS 文件、测试文件、配置文件和数据库设计

---

## 一、总体结论

**总体评价**：项目架构分层清晰（router → service → crud → model），错误处理体系完整（自定义异常类 + 统一 JSONResponse），Prompt 兜底和 LLM 解析容错机制设计周全。**项目可以进入最终联调和答辩准备阶段**，但存在 3 个必须在联调前修复的严重问题和若干需要关注的中等问题。

- **是否可以继续进入最终联调/答辩准备**：✅ 可以，但需先修复严重问题
- **是否建议先修复关键问题**：✅ 是
- **当前项目整体风险等级**：**中**

---

## 二、严重问题

### 问题 1：后端 `.env` 文件中包含真实 DeepSeek API Key 且密码强度极弱

- **严重等级**：高
- **涉及文件**：`backend/.env`
- **涉及函数或代码位置**：第 34 行 `DEEPSEEK_API_KEY=REDACTED_HISTORICAL_CREDENTIAL`
- **问题描述**：`.env` 文件中同时存在真实 DeepSeek API Key、`DATABASE_PASSWORD=123456`、`FIRST_SUPERUSER_PASSWORD=123456`、`DEMO_PASSWORD=123456`。虽然 `backend/.env` 已在 `.gitignore` 中排除，但本地文件一旦被误提交或截图泄露，API Key 将被他人滥用，产生费用损失和安全隐患。密码 `123456` 为最常见弱密码，答辩演示时易被质疑安全性。
- **影响后果**：API Key 泄露将导致 DeepSeek 额度被盗刷；弱密码可被轻易猜测登录。
- **修复建议**：
  1. 立即在 DeepSeek 平台重置该 API Key
  2. 将 `DATABASE_PASSWORD`、`FIRST_SUPERUSER_PASSWORD`、`DEMO_PASSWORD` 改为强密码（至少 12 位混合字符）
  3. 答辩时将 `.env` 中的真实值替换为占位符，仅保留本地可用配置
- **是否必须立即修复**：**是**

### 问题 2：知识库更新时 MySQL 与 Chroma 存在数据不一致窗口

- **严重等级**：高
- **涉及文件**：
  - `backend/app/services/knowledge_service.py`
  - `backend/app/crud/knowledge_crud.py`
- **涉及函数或代码位置**：
  - `update_knowledge_item()` (第 199–206 行)
  - `knowledge_crud.update_knowledge_item()` 内部先 `db.commit()`
- **问题描述**：`update_knowledge_item()` 调用链路：先调用 `knowledge_crud.update_knowledge_item()` → 内部执行 `db.commit()` 将 MySQL 更新持久化 → 然后调用 `_sync_knowledge_vector()` 更新 Chroma。如果 `_sync_knowledge_vector()` 失败（Chroma 写入异常），MySQL 已经提交了新数据，而 Chroma 中的向量仍是旧内容或 `failed` 状态。这导致 MySQL 中内容已更新但向量检索仍返回旧结果。
- **影响后果**：知识库编辑后 RAG 检索可能返回旧数据，检测结果不准确，答辩演示时编辑知识库后复测可能结果不一致。
- **修复建议**：将 MySQL 更新和 Chroma 同步放入同一事务上下文：先更新 MySQL 但不提交 → 同步 Chroma → 如果 Chroma 成功则 commit MySQL，如果 Chroma 失败则 rollback MySQL 并在 Chroma 成功的分支也更新 MySQL。或采用"先标记 pending → 异步同步 → 确认后标记 synced"的模式。
- **是否必须立即修复**：**是**（答辩演示前至少需要理解并说明此风险）

### 问题 3：风险等级常量 `HIGH_RISK_SCORE_THRESHOLD` 与 `RUMOR_SCORE_THRESHOLD` 均为 40 导致"疑似谣言"区间与"高风险谣言"边界存在歧义

- **严重等级**：高
- **涉及文件**：`backend/app/core/constants.py`
- **涉及函数或代码位置**：第 8–9 行
- **问题描述**：
  ```python
  RUMOR_SCORE_THRESHOLD = 40        # 疑似谣言 >= 40
  HIGH_RISK_SCORE_THRESHOLD = 40    # 高风险谣言 < 40
  ```
  两个阈值相等导致 `risk_level.py` 中逻辑为：
  - score >= 80 → 可信新闻
  - score >= 60 → 存疑信息
  - score >= 40 → 疑似谣言
  - score < 40 → 高风险谣言

  同时 `high_risk.py` 中 `should_mark_high_risk()` 判断为 `score < 40 OR risk_level == "高风险谣言"`。

  虽然逻辑上这两个阈值恰好构成连续区间（40 分落入"疑似谣言"而非"高风险谣言"），但 `HIGH_RISK_SCORE_THRESHOLD = 40` 的命名暗示">=40 为高风险"，实际上却是 "<40 为高风险"。`RUMOR_SCORE_THRESHOLD = 40` 的命名暗示"40 进入疑似谣言"，但 40 实际上被判定为"疑似谣言"。
  
  更严重的问题是：`HIGH_RISK_SCORE_THRESHOLD` 未被 `risk_level.py` 使用，而 `RUMOR_SCORE_THRESHOLD` 用于划分"疑似谣言/高风险谣言"边界。如果将来有人修改 `HIGH_RISK_SCORE_THRESHOLD` 为其他值，`risk_level.py` 不会随之改变，导致 `should_mark_high_risk()` 和 `get_risk_level_from_score()` 产生分歧。
- **影响后果**：一旦有人单独修改一个常量而未同步，高风险标记和风险等级将不一致。答辩时若被问到"两个 40 有什么区别"，无法清晰解释。
- **修复建议**：合并为单一阈值常量 `RUMOR_SCORE_THRESHOLD = 40`，删除 `HIGH_RISK_SCORE_THRESHOLD`，`high_risk.py` 直接引用 `RUMOR_SCORE_THRESHOLD`。
- **是否必须立即修复**：**是**（虽然是逻辑正确但常量冗余，答辩时解释不清可能导致扣分）

---

## 三、中等问题

### 问题 4：检测接口 `/detect/news` 无请求频率限制，可被刷接口耗尽 DeepSeek 额度

- **严重等级**：中
- **涉及文件**：`backend/app/api/v1/detect.py`
- **涉及函数或代码位置**：`detect_news()` 端点
- **问题描述**：检测接口支持游客访问（`get_optional_current_user`），没有任何频率限制、验证码或 IP 限制。攻击者或恶意用户可无限提交检测请求，迅速耗尽 DeepSeek API 额度。
- **影响后果**：API 额度被恶意消耗，答辩演示时可能因额度耗尽导致检测功能不可用。
- **修复建议**：至少实现简单的内存级限流（如每个 IP 每分钟最多 3 次检测），或使用 `slowapi` 库。答辩前可在 `.env` 中配置较低的 `DEEPSEEK_TIMEOUT_SECONDS` 和备用的 fallback 响应。
- **是否必须立即修复**：否（答辩环境可控，但建议至少添加应用层限流）

### 问题 5：`knowledge_service.py` 中 `delete_knowledge_item` 先删 Chroma 再删 MySQL 的设计存在残留风险

- **严重等级**：中
- **涉及文件**：`backend/app/services/knowledge_service.py`
- **涉及函数或代码位置**：`delete_knowledge_item()`（第 209–224 行）
- **问题描述**：删除流程为：① 删除 Chroma 向量 → ② 删除 MySQL 记录。如果步骤①成功但步骤②失败，代码尝试恢复 Chroma 向量，但如果恢复也失败，MySQL 记录仍在而 Chroma 向量已丢失。搜索引擎将无法找到该知识条目。虽然代码有 `_mark_vector_delete_failed` 标记机制，但条目仍处于不一致状态。
- **影响后果**：知识库中出现"数据库有但向量库没有"的幽灵记录，RAG 检索遗漏该条目。
- **修复建议**：考虑"先标记 MySQL 为待删除 → 删 Chroma → 如果成功则提交 MySQL 删除"的软删除方案，或接受当前设计并在管理界面展示 `delete_failed` 状态条目供管理员手动处理。
- **是否必须立即修复**：否（概率较低，答辩时可解释容错设计）

### 问题 6：LLM 解析中 `_normalize_score` 返回类型不一致（`int` 或 `float`）

- **严重等级**：中
- **涉及文件**：`backend/app/services/llm_service.py`
- **涉及函数或代码位置**：`_normalize_score()`（第 571–583 行）
- **问题描述**：当分数为整数（如 85.0）时返回 `int(85)` 即 Python `int` 类型，非整数时返回 `float`。这导致 `llm_score` 字段的类型在 Pydantic 验证中可能触发隐式转换，且 JSON 序列化后前端收到的值可能是 `85`（整数）或 `85.5`（浮点数），不一致。
- **影响后果**：前端评分展示可能出现 `85` 和 `85.0` 格式不一致。
- **修复建议**：统一返回 `float` 类型，去掉 `int(score)` 分支。
- **是否必须立即修复**：否

### 问题 7：Chroma 客户端缓存永不失效

- **严重等级**：中
- **涉及文件**：`backend/app/services/chroma_service.py`
- **涉及函数或代码位置**：`_clients` 和 `_collections` 模块级字典（第 12–13 行）
- **问题描述**：Chroma 客户端和 Collection 对象缓存在模块级字典中，永不失效。如果 Chroma 数据库文件被外部修改、损坏或移动，缓存的连接可能指向无效状态，需要重启服务才能恢复。
- **影响后果**：长时间运行后可能出现奇怪的 Chroma 查询错误，只能通过重启解决。
- **修复建议**：添加健康检查机制，或在查询失败时清除缓存并重连。
- **是否必须立即修复**：否

### 问题 8：`SECRET_KEY` 在 `.env` 中为空时 `create_access_token` 会抛出 `RuntimeError` 但不会被路由层统一捕获

- **严重等级**：中
- **涉及文件**：`backend/app/core/security.py`
- **涉及函数或代码位置**：`_get_secret_key()`（第 21–25 行）
- **问题描述**：如果 `SECRET_KEY` 未配置（为空字符串），`_get_secret_key()` 抛出 `RuntimeError("SECRET_KEY is not configured")`。但在路由中（如 `login`），这个异常没有被专门的异常处理器捕获，会被 FastAPI 转为 500 Internal Server Error，用户看到的是不友好的错误信息而非明确的配置提示。
- **影响后果**：用户登录时看到"Internal Server Error"而非清晰的配置缺失提示。
- **修复建议**：在 `create_app()` 启动时做一次配置校验，如果 `SECRET_KEY` 为空则直接阻止启动并输出明确错误信息。
- **是否必须立即修复**：否

### 问题 9：PDF 报告下载路径遍历保护虽然存在但依赖数据库存储路径的安全性

- **严重等级**：中
- **涉及文件**：`backend/app/services/report_service.py`
- **涉及函数或代码位置**：`_resolve_stored_path()`（第 280–288 行）
- **问题描述**：路径遍历保护 `resolved.is_relative_to(root)` 是正确的，但如果 `report_path` 存储在数据库中被篡改（SQL注入或其他途径），仍然存在风险。
- **影响后果**：低概率但影响严重，可能导致任意文件读取。
- **修复建议**：当前实现已经比较安全，建议额外添加文件名白名单校验（只允许 `report_*.pdf` 和 `report_*.html` 模式）。
- **是否必须立即修复**：否

---

## 四、轻微问题

### 问题 10：前端 `ResultView.vue` 中 `getErrorMessage` 对 Blob 错误响应处理存在竞态条件

- **涉及文件**：`frontend/src/views/ResultView.vue`
- **涉及代码位置**：`getReportErrorMessage()` 函数
- **问题描述**：使用的是 `async/await` 方式读取 Blob，但 `responseData instanceof Blob` 的判断发生在 `error.response.data` 已被 axios 拦截器解包之后。如果后端返回 JSON 错误（非 Blob），`error.response.data` 已是对象，`instanceof Blob` 不会匹配，可以正确处理。
- **影响后果**：报告下载失败时的错误提示可能不准确，但不影响核心功能。
- **修复建议**：统一错误处理逻辑，或确保报告下载 API 使用 `responseType: 'blob'` 配置。

### 问题 11：前端标题验证长度与后端不一致

- **涉及文件**：
  - `frontend/src/views/DetectView.vue` 第 156 行：`max: 120`
  - `backend/app/schemas/detection.py`：`max_length=255`
  - `backend/app/services/detection_service.py`：`clean_text(title, max_length=255)`
- **问题描述**：前端限制标题最多 120 个字符，但后端 schema 允许 255 个字符。前端输入超过 120 字符的标题会被前端验证拦截，但后端可接受 120-255 字符的标题（通过 API 直接调用）。不一致但不会导致实际错误。
- **修复建议**：统一为 255 或保持前端 120（对中文新闻标题足够）。

### 问题 12：`clean_text` 函数缺少文档字符串

- **涉及文件**：`backend/app/utils/text_cleaner.py`
- **问题描述**：代码中 `if max_length is not None and max_length >= 0:` 正确保护了 None 情况。但建议在 docstring 中明确说明 `None` 表示不截断。
- **修复建议**：添加函数文档字符串。

### 问题 13：部分异常处理中没有区分 `HTTPException` 和业务异常

- **涉及文件**：`backend/app/main.py`
- **问题描述**：全局异常处理器仅捕获 `HTTPException`、`RequestValidationError` 和 `SQLAlchemyError`。其他未预期异常（如 `RuntimeError`、`ValueError`）会被 FastAPI 默认处理为 500 并可能泄露堆栈信息。
- **修复建议**：添加全局 `Exception` 捕获器，返回通用 500 错误而不泄露堆栈。

### 问题 14：部分调试日志可能在答辩时泄露敏感信息

- **涉及文件**：`backend/app/services/llm_service.py` 第 132 行
- **问题描述**：`logger.exception("DeepSeek API call failed")` 会打印完整堆栈，可能包含请求 URL 和部分请求内容（如果异常消息中包含）。
- **修复建议**：答辩前将日志级别设为 `WARNING` 以上。

---

## 五、前后端接口字段不一致清单

| 页面/模块 | 前端字段 | 后端字段 | 问题 | 修复建议 |
|---|---|---|---|---|
| 检测结果页 | `input_title` | `data.input_title`（仅在 `DetectionDetailOut` 中返回） | 检测 API `/detect/news` 返回的 `DetectNewsResult` 中**没有** `input_title` 和 `input_content` 字段。前端 `DetectView.vue` 手动将 `form.title` 注入缓存，但直接访问结果页（刷新页面）会调用 `/detect/{id}` API 获取详情，该 API 返回 `DetectionDetailOut` 包含 `input_title`。两种路径都正常工作 | 可考虑在 `DetectNewsResult` 中也返回 `input_title` 和 `input_content` |
| 检测结果页 | `similar_news` | `data.similar_news` | ✅ 字段名匹配 | 无 |
| 检测结果页 | `evidence_list` | `data.evidence_list` | ✅ 字段名匹配 | 无 |
| 检测结果页 | `risk_points` / `riskPoints` | `data.risk_points` | 前端 `getArray()` 同时支持两种命名，兼容性好 | 无 |
| 检测结果页 | `agent_steps` / `agentSteps` | `data.agent_steps` | 前端 `getArray()` 同时支持两种命名，兼容性好 | 无 |
| 检测表单 | 前端限制标题 `max: 120` | 后端 `max_length=255` | 前端更严格，不一致但不影响功能 | 统一为 120 或 255 |
| 管理员用户列表 | `AdminUserOut` | 后端 `/admin/users` | ✅ 字段名完全匹配 | 无 |
| 高风险新闻列表 | `PublicHighRiskItem` | 后端 `/high-risk/public` | ✅ 字段名完全匹配 | 无 |
| 注册/登录 | 请求格式 `{ username, password }` | 后端 `UserCreate` / `UserLogin` | ✅ 匹配 | 无 |
| 报告生成 | `report_id`, `download_url` | `ReportOut` | ✅ 匹配 | 无 |

---

## 六、安全风险清单

| 风险点 | 涉及位置 | 风险等级 | 建议 |
|---|---|---|---|
| `.env` 含真实 DeepSeek API Key | `backend/.env` L34 | **高** | 立即重置该 Key，答辩时使用临时 Key 或配置为环境变量 |
| 数据库密码 `123456` | `backend/.env` L10 | **高** | 改为强密码 |
| 管理员密码 `123456` | `backend/.env` L20 | **高** | 改为强密码 |
| `DEMO_PASSWORD = "123456"` 硬编码 | `backend/app/db/seed_demo_data.py` L37 | **中** | 改为从环境变量读取 |
| CORS 配置 `*`（开发模式） | `backend/.env` L4, `backend/app/core/config.py` L37 | **低** | 答辩演示环境可接受，生产环境需改为具体域名 |
| 无请求频率限制 | 所有 API 端点 | **中** | 至少对 `/detect/news` 添加限流（消耗 LLM 额度） |
| 全局未捕获异常可能泄露堆栈 | `backend/app/main.py` | **中** | 添加通用 Exception handler |
| `SECRET_KEY` 在 `.env` 中已配置（非弱值），但 `.env.example` 中为占位符 | `backend/.env.example` L14 | **低** | `.env.example` 中的提示已经很明确 |
| 无请求体大小限制 | `/detect/news` 端点 | **低** | 添加 `max_length` 或中间件限制 |
| 密码使用 bcrypt 加密存储 | `backend/app/core/security.py` L10 | ✅ 安全 | 无 |
| JWT 使用 HS256 签名 | `backend/app/core/security.py` L50 | ✅ 安全 | 无 |
| PDF 路径遍历保护 | `backend/app/services/report_service.py` L286 | ✅ 安全 | 已有 `is_relative_to` 保护 |

---

## 七、建议优先修复顺序

### 1. 必须先修复的问题（联调前）

1. **重置 `.env` 中泄露的 DeepSeek API Key** 并改用强密码（问题 1）
2. **修复风险等级常量冗余问题**（问题 3）—— 删除 `HIGH_RISK_SCORE_THRESHOLD`，统一使用 `RUMOR_SCORE_THRESHOLD`
3. **修复知识库更新中 MySQL/Chroma 不一致窗口**（问题 2）—— 调整 `update_knowledge_item` 的事务顺序

### 2. 建议联调前修复的问题

4. **添加检测接口频率限制**（问题 4）—— 至少 IP 级别每分钟 3 次
5. **添加全局 Exception 处理器**（问题 13）—— 防止 500 错误泄露堆栈
6. **统一 `_normalize_score` 返回类型为 `float`**（问题 6）
7. **启动时校验 `SECRET_KEY` 非空**（问题 8）

### 3. 可以答辩后优化的问题

8. Chroma 客户端缓存失效机制（问题 7）
9. `clean_text` 函数文档补充（问题 12）
10. 前端标题长度与后端统一（问题 11）
11. PDF 报告路径额外白名单校验（问题 9）
12. Blob 错误处理优化（问题 10）
13. 将 `DEMO_PASSWORD` 移至环境变量（安全建议）

---

## 八、给 Codex 的修复提示词

以下提示词可以直接复制给 Codex，每次只修复一个明确任务：

---

### 修复任务 1：重置泄露的 API Key 并强化密码

```
请帮我完成以下安全整改，只修改 backend/.env 文件：

1. 将 DEEPSEEK_API_KEY 的值替换为占位符 "replace_with_deepseek_api_key"（实际 Key 已经泄露，需要在 DeepSeek 平台手动重置）
2. 将 DATABASE_PASSWORD 从 "123456" 改为一个随机生成的 16 位强密码
3. 将 FIRST_SUPERUSER_PASSWORD 从 "123456" 改为一个随机生成的 12 位强密码
4. 同步更新 backend/app/db/seed_demo_data.py 中的 DEMO_PASSWORD 常量，从环境变量 DEMO_PASSWORD 读取，默认值为 "replace_with_demo_password"

修改文件：backend/.env、backend/app/db/seed_demo_data.py
修改原因：安全加固——消除弱密码和硬编码凭证
测试方式：重新启动后端服务，确认登录和种子数据功能正常
风险：低
```

---

### 修复任务 2：删除冗余的 HIGH_RISK_SCORE_THRESHOLD 常量

```
请帮我删除 backend/app/core/constants.py 中的 HIGH_RISK_SCORE_THRESHOLD，统一使用 RUMOR_SCORE_THRESHOLD。

具体步骤：
1. 在 constants.py 中删除 HIGH_RISK_SCORE_THRESHOLD = 40 这一行
2. 在 app/utils/high_risk.py 中，将 "from app.core.constants import HIGH_RISK_SCORE_THRESHOLD, RISK_LEVEL_HIGH" 改为 "from app.core.constants import RUMOR_SCORE_THRESHOLD, RISK_LEVEL_HIGH"
3. 将 "score < HIGH_RISK_SCORE_THRESHOLD" 改为 "score < RUMOR_SCORE_THRESHOLD"
4. 运行 backend/tests/test_high_risk_utils.py 确认测试通过

修改文件：backend/app/core/constants.py、backend/app/utils/high_risk.py
修改原因：消除两个值相等的冗余常量，防止后续独立修改导致不一致
测试方式：pytest backend/tests/test_high_risk_utils.py -v
风险：低——逻辑等价（两个常量值相同）
```

---

### 修复任务 3：修复知识库更新中 MySQL 和 Chroma 的数据不一致窗口

```
请帮我修复 knowledge_service.py 中 update_knowledge_item 的事务顺序问题。

当前逻辑：先 commit MySQL 更新，再同步 Chroma。如果 Chroma 同步失败，MySQL 已提交新数据但 Chroma 仍是旧数据。

修复方案：将 MySQL 更新和 Chroma 同步放入同一事务上下文：
1. 在 knowledge_crud.update_knowledge_item() 中去掉 db.commit()（让调用方控制提交）
2. 在 knowledge_service.update_knowledge_item() 中：先更新 MySQL → 同步 Chroma → 如果 Chroma 成功则 commit MySQL，如果 Chroma 失败则 rollback MySQL → _mark_vector_failed

注意：
- 不要修改其他 CRUD 函数的 commit 行为
- knowledge_crud.update_knowledge_item 需要提供一个不自动 commit 的版本，或增加一个 auto_commit 参数
- 确保 create_knowledge_item 也检查是否有类似问题

修改文件：backend/app/crud/knowledge_crud.py、backend/app/services/knowledge_service.py
修改原因：防止 MySQL 与 Chroma 向量数据不一致
测试方式：模拟 Chroma 写入失败场景，确认 MySQL 数据回滚
风险：中——涉及事务管理变更，需仔细测试
```

---

### 修复任务 4：添加检测接口频率限制

```
请帮我在检测接口上添加简单的 IP 级别频率限制。

实现方案（建议选择最简单的）：
1. 使用 slowapi 库（pip install slowapi）
2. 在 app/main.py 中初始化 Limiter
3. 在 app/api/v1/detect.py 的 detect_news 端点上添加装饰器 @limiter.limit("3/minute")
4. 其他接口至少添加 @limiter.limit("60/minute") 全局默认

如果没有安装 slowapi，请先用简单的内存字典实现一个轻量限流：
- 在 app/core/ 下新建 rate_limit.py
- 实现一个基于 IP + 时间窗口的限流器
- 在 detect_news 端点中调用

修改文件：backend/app/core/rate_limit.py（新建）、backend/app/api/v1/detect.py、backend/app/main.py、backend/requirements.txt
修改原因：防止恶意用户刷检测接口耗尽 DeepSeek API 额度
测试方式：短时间内连续发送 5 次检测请求，确认第 4 次开始返回 429
风险：低
```

---

### 修复任务 5：添加全局未捕获异常处理器

```
请在 backend/app/main.py 的 create_app() 函数中添加一个全局异常处理器。

在现有的三个异常处理器之后，添加：

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response("服务器内部错误，请稍后重试", code=500),
    )

注意：
- 这个处理器应该在其他三个具体异常处理器之后注册
- 生产环境应该记录日志 logger.exception("Unhandled exception")
- 不要替换现有的 HTTPException、RequestValidationError、SQLAlchemyError 处理器

修改文件：backend/app/main.py
修改原因：防止未捕获异常泄露堆栈信息到前端
测试方式：在某个端点中手动 raise ValueError("test")，确认返回 {"code": 500, "message": "服务器内部错误，请稍后重试"}
风险：低
```

---

> **审查完成时间**：2026-06-07
> **审查范围**：全项目 100+ 源文件，覆盖 8 大审查领域
> **下一轮建议**：修复严重问题后，可进行第二轮针对性审查（着重数据库一致性和前后端联调）
