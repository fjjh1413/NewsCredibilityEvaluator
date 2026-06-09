# 智闻辨真 新闻可信度评估系统 — 代码审查报告

> 审查时间：2026-06-06 | 审查范围：全栈（FastAPI + Vue3 + MySQL + Chroma） | 审查方式：只读，不修改任何文件

---

## 一、总体结论

**项目整体完成度较高**，分层架构清晰（router → service → crud → model），错误处理覆盖较全面，LLM 调用有兜底解析机制，管理员权限管控到位。项目可以在当前状态下进入联调和答辩演示。

**但存在 3 个需要立即修复的问题**：CORS 安全配置错误、高风险判断兜底逻辑错误、知识库删除操作的数据一致性缺陷。建议先修复这 3 个问题后再进行答辩演示。

- **是否可以继续进入最终联调/答辩准备**：可以，但建议先修复"严重问题"中的前 3 项
- **是否建议先修复关键问题**：是
- **当前项目整体风险等级**：**中**（3 个高严重性问题，若干中等问题）

---

## 二、严重问题

### 问题 1：CORS 配置 `allow_credentials=True` 与 `origins=["*"]` 不安全组合

- **严重等级**：高
- **涉及文件**：`backend/app/main.py:24-29`、`backend/.env.example:4`
- **涉及函数或代码位置**：`create_app()` 中的 `CORSMiddleware` 配置
- **问题描述**：`BACKEND_CORS_ORIGINS=*` 且 `allow_credentials=True` 同时设置。浏览器规范禁止 `Access-Control-Allow-Origin: *` 与 `Access-Control-Allow-Credentials: true` 同时出现，浏览器会直接拒绝该响应。虽然某些场景下 Starlette 可能会自动回退为反射 Origin，但依赖这种行为是脆弱的。更重要的是，如果后续部署时将 `origins` 改为具体值但未改 `allow_credentials`，会带来凭据泄露风险。
- **影响后果**：跨域请求可能被浏览器拦截；安全审计时会被标记为配置缺陷
- **修复建议**：如果 demo 阶段需要全开放，设置 `allow_credentials=False`；如果需要携带 Cookie/Token，必须指定具体的前端域名列表，不能使用 `*`
- **是否必须立即修复**：是

### 问题 2：`should_mark_high_risk()` 兜底值 `100.0` 导致高风险新闻漏判

- **严重等级**：高
- **涉及文件**：`backend/app/utils/high_risk.py:7-13`
- **涉及函数或代码位置**：`should_mark_high_risk()`
- **问题描述**：当 `final_score` 无法解析为 float 时（如传入 `None`、字符串 `"N/A"`、空字符串），代码 catch 异常后默认返回 `score = 100.0`，然后判断 `score < 40` 为 False，导致该条记录**不会被标记为高风险**。这完全违背了安全原则——当数据异常时，应该保守地标记为高风险或抛出错误，而不是默认为安全。
- **影响后果**：评分数据异常的高风险新闻不会被标记，可能展示在公开页面误导用户
- **修复建议**：当 score 无法解析时，应默认返回高风险（如 `return True`），或至少返回 `score = 0.0` 触发高风险标记
- **是否必须立即修复**：是

### 问题 3：知识库删除操作 `delete_knowledge_item()` 存在数据一致性缺陷

- **严重等级**：高
- **涉及文件**：`backend/app/services/knowledge_service.py:181-196`
- **涉及函数或代码位置**：`delete_knowledge_item()`
- **问题描述**：删除流程为：先删 Chroma 向量 → 成功后再删 MySQL。如果 Chroma 删除成功但 MySQL 删除失败，代码尝试 `_restore_vector_after_mysql_delete_failure()` 恢复向量。但恢复向量本身也可能失败，此时会出现"Chroma 向量已删除，MySQL 记录还在"的不一致状态。此外，`_restore_vector_after_mysql_delete_failure` 中如果 MySQL 记录还在，会标记 `vector_sync_status="synced"`，但实际上刚恢复的向量可能和原始向量 ID 不同，旧向量已在 Chroma 中丢失。
- **影响后果**：知识库数据与向量数据不一致，RAG 检索结果可能包含已"删除"的旧数据或遗漏有效数据
- **修复建议**：方案一——改为"先标记 MySQL 为待删除 → 删 Chroma → 再删 MySQL"的事务补偿模式。方案二——使用软删除，不立即物理删除 MySQL 记录，而是标记为 `deleted`，定期清理时再同步删除向量
- **是否必须立即修复**：是（答辩前至少应明确此风险的应对策略）

---

## 三、中等问题

### 问题 4：`_build_error_result()` 返回的 `risk_level = "模型调用失败"` 不在四类标准值中

- **严重等级**：中
- **涉及文件**：`backend/app/services/llm_service.py:634-646`、`backend/app/services/detection_service.py:36`
- **涉及函数或代码位置**：`_build_error_result()`、`LLM_FAILURE_RISK_LEVEL`
- **问题描述**：当 LLM 调用失败时，`analyze_news_credibility()` 返回 `risk_level = "模型调用失败"`，这不是 `RISK_LEVELS` 四元组（可信新闻、存疑信息、疑似谣言、高风险谣言）中的任一值。虽然在 `detection_service.py` 中通过 `_is_llm_failure()` 检测后抛出异常，阻止了该值流入数据库，但一旦调用方未做此检测（如未来新增调用），该值会突破 schema 校验写入数据库。
- **影响后果**：前端风险等级展示异常，统计分布图可能出现第五类
- **修复建议**：将 LLM 失败时的 `risk_level` 设为 `"存疑信息"` 并在 `reason` 中说明失败原因，或者直接在 `analyze_news_credibility()` 层抛出异常而非返回异常结果
- **是否必须立即修复**：否（当前有保护逻辑，但建议联调前修复）

### 问题 5：Prompt 模板禁用时仍可能在检测中被引用

- **严重等级**：中
- **涉及文件**：`backend/app/services/prompt_service.py:181-209`
- **涉及函数或代码位置**：`get_default_prompt_content()`
- **问题描述**：`get_default_prompt_content()` 查询 `get_active_default_prompt_template()` 获取启用的默认模板。但如果数据库中没有 `enabled` + `is_default` 的模板（例如唯一的默认模板被禁用了），该函数返回空字符串 `""`。然后在 `llm_service.py` 的 `_select_safe_prompt_template()` 中会 fallback 到代码内置的默认 Prompt。这个 fallback 链路是正确的，但如果管理员期望的是使用某个自定义模板，而该模板因误操作被禁用，系统将静默使用内置模板，管理员不会收到任何告警。
- **影响后果**：管理员可能意识不到实际生效的 Prompt 与预期不同
- **修复建议**：当使用代码内置 fallback 时，在检测结果中增加一个标记字段（如 `prompt_source: "fallback"`) 告知用户
- **是否必须立即修复**：否

### 问题 6：embedding_service 使用 hash 伪随机向量，可能导致 RAG 检索精度低

- **严重等级**：中
- **涉及文件**：`backend/app/services/embedding_service.py:15-40`
- **涉及函数或代码位置**：`embed_text()`
- **问题描述**：当前 embedding 实现基于 SHA-256 哈希 + 符号位，生成的是确定性伪随机向量，不具备语义理解能力。这意味着对"苹果手机降价"和"iPhone 价格下调"两个语义相同的查询，会生成完全不同的向量，导致 Chroma 中的相似度检索基本等同于随机召回。代码注释已标注为"replaceable placeholder"。
- **影响后果**：RAG 检索证据的相关性很低，LLM 分析的依据可信度下降，进而影响整个检测链条的有效性
- **修复建议**：接入真实的 embedding 模型（如 DeepSeek Embedding API 或本地 sentence-transformers 模型）。这是课程设计中的已知限制，建议在答辩时明确说明这是当前演示环境的 limitation
- **是否必须立即修复**：否（课程设计答辩可以接受，但需在演示时说明）

### 问题 7：前端 `unwrapApiResponse` 函数重复定义

- **严重等级**：中
- **涉及文件**：`frontend/src/views/DetectView.vue:169-175`、`frontend/src/views/ResultView.vue:214-220`
- **涉及函数或代码位置**：DetectView 和 ResultView 中的 `unwrapApiResponse()`
- **问题描述**：两个 Vue 文件中各自定义了一个功能几乎相同的 `unwrapApiResponse()` 函数，代码重复度 > 90%。如果后端响应格式发生变化，需要同时修改两处（以及未来可能新增的页面）。
- **影响后果**：维护成本增加，可能出现响应解析行为不一致的 Bug
- **修复建议**：将该函数抽取到 `@/utils/request.js` 或新建 `@/utils/response.js`，统一导出
- **是否必须立即修复**：否

### 问题 8：检测接口 `POST /detect/news` 超时时间为 60 秒，但 DeepSeek 调用可能耗时更久

- **严重等级**：中
- **涉及文件**：`frontend/src/api/detect.js:3-4`、`backend/app/services/llm_service.py:25`
- **涉及函数或代码位置**：前端 axios 超时配置、后端 `DEEPSEEK_TIMEOUT_SECONDS`
- **问题描述**：前端 axios 超时设为 60 秒，后端 DeepSeek 超时设置为 30 秒。但 DeepSeek API 在处理长文本 + RAG 证据时，偶尔可能需要更长时间。如果 DeepSeek 返回较慢（接近 30 秒），加上 RAG 检索（10+秒）、规则评分和数据库写入，总耗时可能接近或超过 60 秒，导致前端超时报错但后端实际已检测成功。
- **影响后果**：用户体验差——前端显示"检测失败"但数据库中已有结果
- **修复建议**：将前端超时时间调整为 120 秒，同时在后端增加"异步检测 + 轮询结果"的可选方案
- **是否必须立即修复**：否

---

## 四、轻微问题

### 问题 9：风险等级阈值在多个文件中重复定义

- **严重等级**：低
- **涉及文件**：`backend/app/services/detection_service.py:201-208`、`backend/app/services/llm_service.py:571-579`、`backend/app/utils/high_risk.py:4`
- **涉及函数或代码位置**：`build_final_risk_level()`、`_risk_level_from_score()`、`should_mark_high_risk()`
- **问题描述**：分数→风险等级的映射规则（≥80 可信、≥60 存疑、≥40 疑似、<40 高风险）在三个文件中各自独立定义。如果后续需要调整阈值，容易遗漏某一处。
- **影响后果**：修改阈值时可能产生不一致
- **修复建议**：在 `app/core/config.py` 或新建 `app/core/constants.py` 中统一定义阈值常量和映射函数

### 问题 10：`build_final_risk_level()` 与 `_risk_level_from_score()` 逻辑完全一致但未复用

- **严重等级**：低
- **涉及文件**：`backend/app/services/detection_service.py:201-208`、`backend/app/services/llm_service.py:571-579`
- **涉及函数或代码位置**：同上
- **问题描述**：两个函数实现完全相同的逻辑（基于分数返回风险等级字符串），但属于不同模块。这是典型的代码重复。
- **修复建议**：抽取为公共工具函数

### 问题 11：`embedding_service.py` 中的 `EMBEDDING_DIMENSION = 384` 为硬编码

- **严重等级**：低
- **涉及文件**：`backend/app/services/embedding_service.py:8`
- **问题描述**：向量维度固定为 384，如果将来更换为真实 embedding 模型（可能返回 768、1024 等维度），需要同时修改 Chroma collection 的定义。Chroma 在创建 collection 时并未指定维度，依赖第一次 upsert 时自动推断。
- **修复建议**：将 `EMBEDDING_DIMENSION` 移到配置文件中，与模型选择关联

### 问题 12：`REPORT_DIR` 路径校验过于严格

- **严重等级**：低
- **涉及文件**：`backend/app/core/config.py:76-84`
- **涉及函数或代码位置**：`Settings.report_path`
- **问题描述**：`report_path` 的 property 要求路径必须在 `BASE_DIR` 之外（`is_relative_to` 检查），如果目录不存在会抛出 RuntimeError。在开发环境中，如果忘记创建 `../data/reports` 目录，后端启动就会失败。虽然有清晰的错误提示，但缺乏自动创建目录的容错处理。
- **修复建议**：在检查后自动创建目录，或在 `create_app()` 时提供更友好的启动日志

### 问题 13：前端 `sessionStorage` 缓存检测结果存在数据过期风险

- **严重等级**：低
- **涉及文件**：`frontend/src/views/DetectView.vue:236-244`、`frontend/src/views/ResultView.vue:222-235`
- **问题描述**：检测结果被缓存到 `sessionStorage`，ResultView 优先读取缓存。如果用户直接通过 URL 访问结果页（如从历史记录跳转），缓存中可能没有数据，此时回退请求 API。但如果缓存中有数据而 API 数据已更新（如管理员修改了审核状态），用户看到的将是过时的缓存数据。
- **修复建议**：为缓存设置时间戳，超过一定时间（如 5 分钟）后强制请求 API

---

## 五、前后端接口字段不一致清单

经过对比后端 Schema（`app/schemas/detection.py`）和前端字段读取（`ResultView.vue`、`DetectView.vue`），前端使用了非常多的 fallback 字段名（通过 `pick()` 函数），说明前端作者已经意识到了字段名不一致的问题并做了大量防御性处理。以下列出需要注意的点：

| 页面/模块 | 前端期望字段 | 后端实际返回字段 | 问题 | 修复建议 |
|---|---|---|---|---|
| 结果页 - 综合评分 | `final_score` / `credibility_score` / `score` | `final_score` | 前端兼容了多个 fallback，无实际错误 | 统一使用 `final_score`，清理多余的 fallback |
| 结果页 - 风险等级 | `risk_level` / `riskLevel` | `risk_level` | 前端兼容了 camelCase fallback | 无实际影响，保持现状 |
| 结果页 - 判断结果 | `judgement_result` / `judgment_result` / `conclusion` | `judgement_result` | 拼写变体兼容 | 保持现状 |
| 结果页 - 证据列表 | `evidence_list` / `evidenceList` / `evidences` / `evidence_matches` | `evidence_list` | 前端兼容了多种命名 | API 响应中实际返回 `evidence_list`，`evidence_matches` 是详情接口返回 |
| 结果页 - 风险点 | `risk_points` / `riskPoints` | `risk_points` | 前端通过 `getArray()` 做了数组化处理 | 保持现状 |
| 检测页 - 检测ID | `detection_id` / `id` / `record_id` / `result_id` | `detection_id` | 前端兼容了多个 fallback | 保持现状 |
| 管理员 - 统计概览 | `today_detections` / `total_detections` 等 | 后端返回 key 为 snake_case | 前端通过 `pickMetric()` 做了映射 | 保持现状 |

**总体评价**：前端做了充分（甚至过度）的字段名兼容，当前没有发现会导致页面崩溃的字段缺失问题。

---

## 六、安全风险清单

| 风险点 | 涉及位置 | 风险等级 | 建议 |
|---|---|---|---|
| CORS `allow_credentials=True` + `origins=["*"]` | `backend/app/main.py:24-29` | **高** | 设置 `allow_credentials=False` 或指定具体域名 |
| `should_mark_high_risk()` 兜底值为 100 导致漏报 | `backend/app/utils/high_risk.py:11` | **高** | 异常时默认返回 `True` |
| 默认 CORS 为 `*` 允许任意来源 | `backend/.env.example:4` | **中** | 部署时改为具体前端域名 |
| JWT Token 存储在 localStorage 易受 XSS | `frontend/src/utils/auth.js:5-6` | **中** | 考虑 httpOnly cookie（课程设计可接受） |
| `SECRET_KEY` 默认值为空字符串 | `backend/app/core/config.py:30` | **中** | 有 RuntimeError 检查，但建议在 `.env.example` 中生成随机值示例 |
| 登录/注册接口无频率限制 | `backend/app/api/v1/auth.py:30-69` | **中** | 增加 rate limiting 中间件或依赖 |
| 无 Content-Security-Policy 头 | `backend/app/main.py` | **低** | 建议添加基础 CSP 头 |
| 密码使用 bcrypt 哈希存储 | `backend/app/core/security.py:10-14` | ✅ 安全 | 保持现状 |
| 管理员权限通过 `get_current_admin` 依赖严格校验 | `backend/app/core/deps.py:47-53` | ✅ 安全 | 保持现状 |
| PDF 下载路径有 `is_relative_to` 防穿越 | `backend/app/services/report_service.py:280-288` | ✅ 安全 | 保持现状 |
| Pydantic Schema 使用 `extra="forbid"` 防额外字段注入 | `backend/app/schemas/detection.py:10,41` | ✅ 安全 | 保持现状 |
| SQL 查询使用参数化，无 SQL 注入风险 | 全项目使用 SQLAlchemy ORM | ✅ 安全 | 保持现状 |

---

## 七、建议优先修复顺序

### 1. 必须先修复的问题（答辩前）

1. **CORS 安全配置**：将 `allow_credentials` 改为 `False`，或将 `origins` 改为具体前端域名
2. **`should_mark_high_risk()` 兜底值**：将默认值从 `100.0` 改为安全默认（返回 `True` 或 `score=0`）
3. **知识库删除一致性**：确认答辩演示时不会触发边界情况，或实现软删除方案

### 2. 建议联调前修复的问题

4. LLM 失败时的 `risk_level` 值不在标准四类中 — 统一返回值或在上层拦截
5. embedding 假实现 — 至少在答辩时明确说明这是演示 limitation，如有条件接入真实模型
6. 前端 `unwrapApiResponse` 去重 — 抽取为公共函数

### 3. 可以答辩后优化的问题

7. 风险等级阈值统一管理
8. 评分映射函数去重
9. embedding 维度配置化
10. 前端 sessionStorage 缓存加过期时间
11. 登录接口增加频率限制
12. ECharts 图表组件的 resize/destroy 管理确认

---

## 八、给 Codex 的修复提示词

以下是按优先级排列的可执行修复提示词，每次只修复一个问题：

---

### Fix 1：修复 CORS 不安全的 `allow_credentials` 配置

```
请修改 backend/app/main.py 中的 CORSMiddleware 配置：

1. 将 `allow_credentials=True` 改为 `allow_credentials=False`
2. 如果项目需要携带 Cookie，则保持 `allow_credentials=True`，
   但必须将 backend/.env.example 中的 `BACKEND_CORS_ORIGINS=*`
   改为具体的前端地址（如 `BACKEND_CORS_ORIGINS=http://localhost:5173`）

修改文件：backend/app/main.py（第27行）、backend/.env.example（第4行）
修改原因：`credentials=True` + `origins=["*"]` 浏览器会拒绝跨域请求，
         且存在安全风险。
测试方式：启动后端，从前端发起跨域请求，确认响应头和功能正常。
风险：低。仅修改 CORS 中间件参数。
```

---

### Fix 2：修复 `should_mark_high_risk()` 异常时的安全兜底逻辑

```
请修改 backend/app/utils/high_risk.py 中的 should_mark_high_risk 函数：

当前代码在 final_score 无法解析为 float 时，默认 score = 100.0，
导致异常数据不会被标记为高风险。请将第 11 行：
    score = 100.0
改为：
    score = 0.0
或者直接 return True（数据异常时保守处理）。

修改文件：backend/app/utils/high_risk.py（第 6-13 行）
修改原因：数据异常时应保守标记为高风险，而非默认为安全。
测试方式：编写单元测试，传入 None、"N/A"、"" 等异常值，断言返回 True。
风险：低。仅修改异常处理分支的逻辑。
```

---

### Fix 3：统一风险等级阈值定义为公共常量

```
请在 backend/app/core/ 目录下新建 constants.py 文件，定义以下公共常量：

- RISK_THRESHOLD_TRUSTED = 80（可信新闻最低分）
- RISK_THRESHOLD_SUSPICIOUS = 60（存疑信息最低分）
- RISK_THRESHOLD_RUMOR = 40（疑似谣言最低分）
- HIGH_RISK_THRESHOLD = 40（高风险标记阈值）

然后修改以下三个文件，引用公共常量而非硬编码数字：
1. backend/app/services/detection_service.py → build_final_risk_level()
2. backend/app/services/llm_service.py → _risk_level_from_score()
3. backend/app/utils/high_risk.py → should_mark_high_risk()

修改文件：新建 backend/app/core/constants.py
         修改 backend/app/services/detection_service.py（第 201-208 行）
         修改 backend/app/services/llm_service.py（第 571-579 行）
         修改 backend/app/utils/high_risk.py（第 13 行）
修改原因：消除重复的魔法数字，阈值修改时只需改一处。
测试方式：运行已有单元测试，确认检测结果的风险等级分类不变。
风险：低。仅提取常量，不修改业务逻辑。
```

---

### Fix 4：抽取前端重复的 `unwrapApiResponse` 函数

```
请修改前端代码，将 DetectView.vue 和 ResultView.vue 中重复定义的
unwrapApiResponse 函数抽取到公共工具文件：

1. 在 frontend/src/utils/ 下新建 response.js
2. 将以下函数移到 response.js 并导出：
   - unwrapApiResponse(response)
3. 在 DetectView.vue 和 ResultView.vue 中删除本地定义，改为从 @/utils/response 导入

修改文件：新建 frontend/src/utils/response.js
         修改 frontend/src/views/DetectView.vue（删除第 169-175 行，添加 import）
         修改 frontend/src/views/ResultView.vue（删除第 214-220 行，添加 import）
修改原因：消除重复代码，统一响应解析逻辑。
测试方式：运行前端，测试新闻检测和结果查看功能正常。
风险：低。仅抽取函数，不修改逻辑。
```

---

### Fix 5：知识库删除操作增加事务保护注释和已知限制说明

```
请修改 backend/app/services/knowledge_service.py 中 delete_knowledge_item 函数：

在函数 docstring 中添加已知限制说明：
"Known limitation: Chroma delete is performed before MySQL delete.
 If Chroma succeeds but MySQL fails, the vector restore may also fail,
 leaving the database in an inconsistent state. For production use,
 consider implementing a soft-delete pattern or distributed transaction."

同时考虑在删除失败时，不清除已删除的向量，而是将 MySQL 记录标记为
vector_sync_status="orphaned"，后续由管理员手动处理。

修改文件：backend/app/services/knowledge_service.py（第 181-195 行）
修改原因：明确已知风险，为后续改进提供文档依据（课程设计可接受此限制）。
测试方式：模拟 MySQL 删除失败场景，验证错误信息和状态标记正确。
风险：中。修改删除失败处理逻辑，需要验证正常删除流程不受影响。
```

---

> **审查完成。以上报告未修改任何项目文件，请确认后选择需要修复的问题。**
