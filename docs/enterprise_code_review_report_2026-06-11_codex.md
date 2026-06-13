# 企业级代码审查报告

审查日期：2026-06-11  
审查范围：后端 FastAPI、前端 Vue3 + Element Plus、MySQL/Chroma 数据链路、RAG/DeepSeek 调用、权限安全、测试与文档交付。  
执行边界：本轮为只读审查，未修改业务代码、数据库结构或运行环境。

## 一、项目结构扫描结果

后端结构较清晰，主要目录包括：

- `backend/app/api/v1`：认证、检测、RAG、报告、管理员后台等路由。
- `backend/app/schemas`：Pydantic 请求与响应模型。
- `backend/app/crud`：数据库访问层。
- `backend/app/models`：SQLAlchemy 模型。
- `backend/app/services`：检测、知识库、Chroma、LLM、报告、统计等业务服务。
- `backend/app/core`：配置、安全、依赖、限流、常量。
- `backend/app/db`：数据库初始化与演示数据脚本。
- `backend/tests`：后端测试目录。

前端结构较完整，主要目录包括：

- `frontend/src/views`：用户端页面。
- `frontend/src/views/admin`：管理员端页面。
- `frontend/src/api`：接口封装。
- `frontend/src/components`：通用组件。
- `frontend/src/layouts`：用户端和管理员端布局。
- `frontend/src/stores`：Pinia 用户会话状态。
- `frontend/src/utils`：请求封装、响应解包、格式化、统计图表工具。
- `frontend/src/router`：Vue Router 路由与权限守卫。

核心配置文件：

- `backend/app/core/config.py`
- `backend/.env.example`
- `backend/requirements.txt`
- `frontend/package.json`
- `frontend/vite.config.js`

核心业务模块位置：

- 注册登录与 JWT：`backend/app/api/v1/auth.py`、`backend/app/services/auth_service.py`、`backend/app/core/security.py`、`backend/app/core/deps.py`
- 新闻检测：`backend/app/api/v1/detect.py`、`backend/app/services/detection_service.py`
- RAG 与 Chroma：`backend/app/api/v1/rag.py`、`backend/app/services/knowledge_service.py`、`backend/app/services/chroma_service.py`
- DeepSeek 调用：`backend/app/services/llm_service.py`、`backend/app/services/embedding_service.py`
- PDF 报告：`backend/app/api/v1/report.py`、`backend/app/services/report_service.py`
- 管理员知识库：`backend/app/api/v1/admin_knowledge.py`
- Prompt 模板：`backend/app/api/v1/admin_prompts.py`、`backend/app/services/prompt_service.py`
- 高风险新闻：`backend/app/api/v1/high_risk.py`、`backend/app/api/v1/admin_high_risk.py`
- 统计图表：`backend/app/api/v1/admin_statistics.py`、`backend/app/services/statistics_service.py`

本轮实际重点查看过的文件：

- `backend/app/main.py`
- `backend/app/core/config.py`
- `backend/app/core/security.py`
- `backend/app/core/deps.py`
- `backend/app/core/rate_limit.py`
- `backend/app/api/router.py`
- `backend/app/api/v1/auth.py`
- `backend/app/api/v1/detect.py`
- `backend/app/api/v1/rag.py`
- `backend/app/api/v1/report.py`
- `backend/app/api/v1/admin_knowledge.py`
- `backend/app/api/v1/admin_prompts.py`
- `backend/app/api/v1/admin_users.py`
- `backend/app/api/v1/admin_reports.py`
- `backend/app/api/v1/admin_statistics.py`
- `backend/app/api/v1/admin_high_risk.py`
- `backend/app/services/detection_service.py`
- `backend/app/services/knowledge_service.py`
- `backend/app/services/chroma_service.py`
- `backend/app/services/llm_service.py`
- `backend/app/services/embedding_service.py`
- `backend/app/services/report_service.py`
- `backend/app/services/prompt_service.py`
- `backend/app/db/init_db.py`
- `backend/app/db/seed_demo_data.py`
- `frontend/src/router/index.js`
- `frontend/src/utils/request.js`
- `frontend/src/utils/auth.js`
- `frontend/src/stores/user.js`
- `frontend/src/views/DetectView.vue`
- `frontend/src/views/ResultView.vue`
- `frontend/src/views/admin/AdminKnowledgeView.vue`
- `frontend/src/views/admin/AdminLogsView.vue`

## 二、总体结论

当前项目具备“企业级单体项目雏形”。后端分层、JWT 鉴权、管理员权限依赖、报告下载权限控制、RAG/LLM 调用链路、知识库向量同步状态、测试覆盖等方面已经明显超过普通课程 demo。

项目适合作为简历项目，但答辩前建议优先修复 RAG 质量、演示账号安全、日志审计、接口契约和交付说明。

是否适合进入答辩演示：基本适合，但建议先完成 P1 项的收口，尤其是真实 embedding 与演示账号处理。

当前工程质量等级：B。

当前主要短板：

- 默认 embedding 为 hash 演示兜底，不具备真正语义检索能力。
- 演示账号固定弱口令在脚本和文档中公开，若误用于共享环境风险较高。
- DeepSeek 调用失败会阻断检测保存，答辩时依赖外部 API 稳定性。
- 系统日志后端未落地，管理员日志页只是占位。
- 部分前端页面为了兼容多种响应字段做了过多兜底，接口契约不够硬。

最建议优先修复的 5 个问题：

1. 将默认 RAG embedding 切换到真实语义 embedding，并重建 Chroma 索引。
2. 移除公开固定演示口令，改为环境变量或本地生成。
3. 给登录和注册接口增加限流。
4. 给检测流程增加 LLM 失败降级结果，避免核心流程完全阻断。
5. 补齐系统日志后端接口，或在简历和答辩中明确该模块未完成。

## 三、企业级成熟度评分

| 维度 | 分数/10 | 当前表现 | 主要问题 | 改进建议 |
|---|---:|---|---|---|
| 架构分层 | 8 | FastAPI 单体分层清楚 | 少量 service 函数偏长 | 保持单体，继续细化服务职责 |
| 后端规范 | 8 | schema/crud/service/model/core 完整 | `create_all` 与手动迁移并存 | 引入轻量迁移流程或明确迁移文档 |
| 前端规范 | 7 | api/router/store/component 分层完整 | 响应兼容字段过多 | 固化统一响应契约 |
| 数据库设计 | 7 | 核心表、索引、状态字段较完整 | `system_logs` 文档有但代码未实现 | 补日志模型和接口 |
| RAG 实现 | 6 | Chroma 链路完整 | 默认 hash embedding 非语义 | 答辩前切真实 embedding |
| 大模型调用 | 7 | 超时、JSON 解析、Prompt 校验较好 | LLM 失败直接阻断检测 | 增加降级策略 |
| 安全性 | 7 | bcrypt、JWT、RBAC、PDF 下载防护较好 | 演示弱口令、auth 无独立限流 | 收紧演示配置和认证接口 |
| 前后端一致性 | 7 | 主路径基本一致 | 知识库向量状态筛选不一致 | 后端接收并处理筛选参数 |
| 测试覆盖 | 8 | 后端测试覆盖广 | 前端缺少 lint/单测 | 增加最小前端验证 |
| 文档完整度 | 7 | README 和后端说明较完整 | 演示账号安全叙述需调整 | 避免公开固定口令 |
| 简历展示价值 | 8 | RAG、LLM、后台、报告功能完整 | 需补强安全和真实检索质量 | 强调可替换 embedding、权限和报告链路 |

## 四、必须立即修复的问题

### 问题 1：默认 embedding 为 hash 演示兜底，RAG 语义检索质量不足

- 严重等级：P1
- 证据状态：已确认
- 涉及文件：
  - `backend/app/core/config.py`
  - `backend/app/services/embedding_service.py`
  - `backend/.env.example`
- 涉及函数或配置：
  - `DEFAULT_EMBEDDING_PROVIDER = "hash"`
  - `embed_text`
  - `_hash_embed_text`
- 问题描述：当前默认 provider 为 hash，代码注释也明确说明该向量只保证 Chroma 路径可运行，不编码语义。
- 企业级影响：答辩中如果被追问“RAG 为什么能召回相似新闻”，hash embedding 很难支撑语义相似性说明。
- 推荐修复方案：将答辩环境切换为真实 embedding provider，配置 API Key 后重建 Chroma 知识库索引。
- 是否需要修改数据库：不需要修改表结构，但需要重建向量索引。
- 是否影响现有功能：会影响 RAG 召回结果，需要重新验证检测效果。
- 建议优先级：P1

### 问题 2：演示账号固定弱口令写入代码和文档

- 严重等级：P1
- 证据状态：已确认
- 涉及文件：
  - `backend/app/db/seed_demo_data.py`
  - `README.md`
  - `backend/README.md`
- 涉及函数或配置：
  - `DEMO_PASSWORD`
  - `ensure_demo_users`
- 问题描述：演示账号使用固定弱口令，并在文档中直接说明。课程本地演示可理解，但如果公开仓库或误部署，会显著降低安全印象。
- 企业级影响：面试官会把它视为安全意识不足，尤其管理员账号不应以固定弱口令方式公开。
- 推荐修复方案：改为从环境变量读取演示密码，未设置时本地随机生成并只在本次 seed 输出中展示；文档只说明“运行 seed 后查看控制台输出”。
- 是否需要修改数据库：不需要。
- 是否影响现有功能：会影响演示登录方式，需要更新 README。
- 建议优先级：P1

### 问题 3：DeepSeek 调用失败会阻断新闻检测保存

- 严重等级：P1
- 证据状态：已确认
- 涉及文件：
  - `backend/app/services/detection_service.py`
  - `backend/app/api/v1/detect.py`
- 涉及函数或接口：
  - `detect_news_credibility`
  - `POST /api/detect/news`
- 问题描述：LLM 返回失败结果时，检测服务抛出 `LLMAnalysisFailedError`，接口返回 503，不保存检测记录。
- 企业级影响：答辩现场如果 DeepSeek Key 未配置、网络异常或 API 超时，核心检测链路会失败。
- 推荐修复方案：增加降级检测结果：RAG + 规则评分仍生成记录，明确标记 `llm_failed` 或在 reason/suggestion 中说明模型不可用。
- 是否需要修改数据库：不一定需要，可先用现有字段表达；如需更规范，可后续增加状态字段。
- 是否影响现有功能：会提升稳定性，但需要测试结果页展示。
- 建议优先级：P1

### 问题 4：登录和注册接口缺少频率限制

- 严重等级：P1
- 证据状态：已确认
- 涉及文件：
  - `backend/app/api/v1/auth.py`
  - `backend/app/core/rate_limit.py`
  - `backend/app/api/v1/detect.py`
- 涉及函数或接口：
  - `POST /api/auth/register`
  - `POST /api/auth/login`
  - `InMemoryRateLimiter`
- 问题描述：检测接口已有 IP 级限流，但登录和注册接口未使用限流。
- 企业级影响：存在暴力登录、批量注册和资源滥用风险。
- 推荐修复方案：复用现有 `InMemoryRateLimiter`，为登录和注册分别设置窗口和次数。
- 是否需要修改数据库：不需要。
- 是否影响现有功能：正常用户无影响，测试需补充 429 场景。
- 建议优先级：P1

### 问题 5：系统日志后端未实现

- 严重等级：P1/P2
- 证据状态：已确认
- 涉及文件：
  - `docs/02_database_design.md`
  - `frontend/src/views/admin/AdminLogsView.vue`
- 涉及接口：
  - 预期 `GET /api/admin/logs`
- 问题描述：数据库设计文档包含 `system_logs`，前端管理员日志页也已存在，但页面明确提示后端未注册日志接口。
- 企业级影响：认证、检测、管理员操作缺少审计记录，企业级完整性不足。
- 推荐修复方案：补充最小日志模型、CRUD、管理员查询接口，并在登录、检测、管理员关键操作处记录审计事件。
- 是否需要修改数据库：需要新增日志表或明确暂不实现。
- 是否影响现有功能：新增能力，不影响现有主流程。
- 建议优先级：P1/P2

## 五、建议联调前修复的问题

### 问题 1：知识库向量同步状态筛选前后端不一致

- 严重等级：P2
- 证据状态：已确认
- 涉及文件：
  - `frontend/src/views/admin/AdminKnowledgeView.vue`
  - `backend/app/api/v1/admin_knowledge.py`
  - `backend/app/services/knowledge_service.py`
  - `backend/app/crud/knowledge_crud.py`
- 问题描述：前端会发送 `vector_sync_status` 查询参数，但后端列表接口没有接收该参数，页面实际只在当前页本地过滤。
- 影响后果：分页总数和筛选结果不准确，管理员可能误判知识库同步状态。
- 推荐修复方案：后端列表接口增加 `vector_sync_status` 参数，并在 CRUD 查询中处理。

### 问题 2：`create_all` 与手动迁移并存，迁移体系不完整

- 严重等级：P2
- 证据状态：已确认
- 涉及文件：
  - `backend/app/db/init_db.py`
  - `backend/migrations/20260604_add_high_risk_review_fields.sql`
- 问题描述：初始化依赖 `Base.metadata.create_all`，同时又存在手工 SQL 迁移脚本。
- 影响后果：多人协作或多环境部署时容易出现表结构漂移。
- 推荐修复方案：当前阶段可先完善迁移执行说明；后续引入 Alembic。

### 问题 3：Chroma 检索后逐条查询 MySQL，存在 N+1 风险

- 严重等级：P2
- 证据状态：已确认
- 涉及文件：
  - `backend/app/services/knowledge_service.py`
- 问题描述：`search_similar_knowledge` 对每个 Chroma 命中结果逐条调用 `get_knowledge_item`。
- 影响后果：top_k 增大或并发增加时数据库查询次数明显上升。
- 推荐修复方案：收集 `knowledge_id` 后批量查询，再按原排序组装结果。

### 问题 4：前端响应解包过度兼容，弱化接口契约

- 严重等级：P2
- 证据状态：已确认
- 涉及文件：
  - `frontend/src/stores/user.js`
  - `frontend/src/views/HistoryView.vue`
  - `frontend/src/views/admin/AdminDetectionsView.vue`
  - `frontend/src/views/admin/AdminKnowledgeView.vue`
- 问题描述：前端同时兼容 `score/final_score/credibility_score`、`riskLevel/risk_level` 等多种字段。
- 影响后果：短期容错强，长期会掩盖接口不一致。
- 推荐修复方案：确认统一响应结构后逐步删除历史兼容字段。

### 问题 5：用户表单校验前后端长度规则不一致

- 严重等级：P2
- 证据状态：已确认
- 涉及文件：
  - `backend/app/schemas/user.py`
  - `backend/app/schemas/auth.py`
  - `frontend/src/views/LoginView.vue`
  - `frontend/src/views/RegisterView.vue`
- 问题描述：后端用户名最小长度为 3，前端部分表单为 2；后端密码最大长度为 128，前端为 64。
- 影响后果：用户可能前端校验通过但后端返回 422，体验不一致。
- 推荐修复方案：将前端表单规则与后端 schema 对齐。

### 问题 6：测试输出存在 SQLite 连接 ResourceWarning

- 严重等级：P2
- 证据状态：已确认
- 涉及范围：后端测试运行输出
- 问题描述：后端 208 个测试通过，但输出多处 unclosed database ResourceWarning。
- 影响后果：不阻断当前答辩，但说明部分测试数据库 session/engine 生命周期可以进一步清理。
- 推荐修复方案：检查测试 fixture 中 session close、engine dispose、临时数据库清理。

## 六、可以后续优化的问题

1. JWT 存储在 `localStorage`，当前课程阶段可接受，生产更推荐 httpOnly cookie 或短 access token + refresh token。
2. 前端 `package.json` 缺少 lint 脚本。
3. 前端 ECharts chunk 构建后超过 500KB，后续可进一步异步拆包。
4. 管理员日志页已做“接口待接入”提示，不应作为已完成能力展示。
5. 统计、报告、知识库服务可继续拆分长函数，增强可读性。
6. CORS 默认 `*` 适合本地演示，但部署前必须收紧到前端域名。
7. `backend/.env.example` 中的数据库和密钥字段应继续保持模板化，不允许提交真实值。

## 七、前后端接口一致性检查

| 模块 | 前端请求/字段 | 后端接口/字段 | 是否一致 | 问题 | 修复建议 |
|---|---|---|---|---|---|
| 登录 | `POST /auth/login`，`username/password` | `POST /api/auth/login`，`UserLogin` | 是 | 无独立限流 | 增加登录限流 |
| 注册 | `POST /auth/register`，`username/password/email` | `POST /api/auth/register`，`UserCreate` | 基本一致 | 长度规则不完全一致 | 同步校验规则 |
| 新闻检测 | `POST /detect/news` | `POST /api/detect/news` | 是 | LLM 失败阻断 | 增加降级结果 |
| 历史记录 | `GET /detect/history`，`page/page_size/risk_level/keyword` | 同路径同参数 | 是 | 前端兼容字段过多 | 固化响应字段 |
| 检测详情 | `GET /detect/{id}` | 同路径 | 是 | 无明显问题 | 保持 |
| 报告生成 | `POST /report/generate/{id}` | 同路径 | 是 | 无明显问题 | 保持 |
| 报告下载 | `GET /report/download/{id}` | 同路径 | 是 | 权限校验较好 | 保持 |
| 知识库列表 | `vector_sync_status` | 后端未接收 | 否 | 筛选只作用当前页 | 后端补筛选参数 |
| Prompt 模板 | `/admin/prompts` 系列 | 同路径 | 是 | 无明显问题 | 保持 |
| 高风险新闻 | `/high-risk`、`/admin/high-risk` | 同路径 | 是 | 无明显问题 | 保持 |
| 系统日志 | 预期 `/admin/logs` | 未注册 | 否 | 日志功能未完成 | 补后端日志模块 |

## 八、权限与安全风险清单

| 风险点 | 涉及位置 | 风险等级 | 证据状态 | 企业级要求 | 修复建议 |
|---|---|---|---|---|---|
| 密码安全哈希 | `backend/app/core/security.py` | 低 | 已确认已有 bcrypt | 密码不可明文存储 | 保持 |
| JWT 密钥配置 | `backend/app/core/config.py` | 中 | 已确认有启动校验 | 不能使用占位密钥 | 保持并完善生产说明 |
| 管理员权限校验 | `backend/app/core/deps.py` | 低 | 已确认 | 后端必须强制校验 | 保持 |
| 普通用户访问管理员接口 | `admin_*` 路由 | 低 | 已确认使用 `get_current_admin` | 返回 403 | 保持并继续测试 |
| 用户访问他人检测记录 | `detection_crud._apply_user_scope` | 低 | 已确认 | 必须按用户隔离 | 保持 |
| PDF 路径穿越 | `report_service._resolve_stored_path` | 低 | 已确认有路径和文件名校验 | 只允许下载生成文件 | 保持 |
| 登录/注册刷接口 | `auth.py` | 中高 | 已确认无限流 | 认证接口应限流 | 增加限流 |
| 演示管理员口令 | `seed_demo_data.py`、README | 中高 | 已确认 | 不应公开固定弱口令 | 改为生成或环境变量 |
| CORS 默认 `*` | `.env.example` | 中 | 已确认 | 生产应限定来源 | 部署前收紧 |
| Token 存储在 localStorage | `frontend/src/utils/auth.js` | 低/中 | 已确认 | 高安全场景避免 XSS 窃取 | 后续考虑 httpOnly cookie |

## 九、数据一致性风险清单

| 场景 | 当前流程 | 风险 | 证据状态 | 推荐企业级处理方式 |
|---|---|---|---|---|
| 知识库新增 | MySQL 先提交，再同步 Chroma | 可产生 failed/pending 数据 | 已确认 | 保留状态字段，增加重试和补偿入口 |
| 知识库更新 | 更新和向量同步在同一事务中处理，失败 rollback | 较好 | 已确认 | 保持 |
| 知识库删除 | 先删 Chroma，再删 MySQL，失败尝试恢复向量 | 有补偿但非分布式事务 | 已确认 | 当前阶段可接受，文档说明边界 |
| 报告生成 | 先生成文件，再保存 DB 路径，失败清理文件 | 较好 | 已确认 | 保持 |
| 检测记录保存 | LLM 成功后保存检测记录 | LLM 失败时无记录 | 已确认 | 增加失败/降级记录 |
| 数据库迁移 | create_all + 手工 SQL | 多环境结构漂移 | 已确认 | 明确迁移流程，后续 Alembic |

## 十、RAG 与 LLM 调用风险清单

| 风险点 | 涉及位置 | 当前表现 | 影响 | 修复建议 |
|---|---|---|---|---|
| 默认 hash embedding | `embedding_service.py` | 可跑但非语义 | RAG 质量不足 | 切换真实 embedding |
| Prompt 模板缺失 | `prompt_service.py`、`llm_service.py` | 有 fallback | 较好 | 保持 |
| Prompt 变量校验 | `prompt_template_validator.py` | 校验 title/content/evidence | 较好 | 保持 |
| DeepSeek 非 JSON | `llm_service.py` | 有 JSON 提取和文本兜底 | 较好 | 增加测试样例 |
| DeepSeek 超时/异常 | `llm_service.py`、`detection_service.py` | 服务返回失败结果后检测接口 503 | 答辩不稳定 | 做降级检测 |
| 空 RAG 结果 | `detection_service._build_reason` | 会说明证据不足 | 较好 | 保持 |
| Prompt 注入 | 用户输入进入 prompt | 有系统提示和输出契约，但无专门注入防护 | 中 | 增加输入边界和注入测试 |

## 十一、测试补充清单

本轮已执行验证命令：

```powershell
cd backend
python -m unittest discover -s tests -p "test_*.py"
```

结果：208 个后端测试通过。

```powershell
cd frontend
npm run build -- --outDir <临时目录> --emptyOutDir
```

结果：前端构建通过；存在 ECharts chunk 超过 500KB 的构建警告。

后端必须补充或继续保持的测试：

- 登录/注册限流测试。
- LLM 失败降级检测测试。
- 知识库 `vector_sync_status` 服务端筛选测试。
- 系统日志查询与权限测试。
- 普通用户访问管理员接口 403 测试。
- PDF 下载越权和路径非法测试。
- MySQL/Chroma 同步失败补偿测试。

前端必须验证的页面：

- 登录页、注册页。
- 新闻检测页。
- 检测结果页。
- 历史记录页。
- PDF 报告生成和下载。
- 管理员统计页。
- 知识库管理页。
- Prompt 模板管理页。
- 高风险新闻管理页。
- 系统日志页，如果未实现则不要作为已完成能力展示。

答辩前必须手动跑通的流程：

1. 普通用户登录。
2. 新闻检测。
3. 查看检测结果。
4. 生成并下载 PDF。
5. 查看历史记录。
6. 管理员登录。
7. 进入后台统计。
8. 新增或编辑知识库并向量化。
9. 管理 Prompt 模板。
10. 审核并公开高风险新闻。
11. 普通用户访问管理员接口返回 403。

## 十二、企业级代码质量提升路线图

### 第一阶段：答辩前必须修复

1. 将 RAG embedding 切换到真实语义模型。
2. 移除公开固定演示口令。
3. 给登录和注册增加限流。
4. 给 LLM 调用失败增加降级检测结果。
5. 修复知识库向量状态筛选前后端不一致。

### 第二阶段：简历项目前必须优化

1. 补齐系统日志后端。
2. 明确数据库迁移流程。
3. 统一前端响应解包逻辑。
4. 对齐前后端表单校验规则。
5. 清理后端测试 ResourceWarning。
6. 增加前端 lint 或最小单测。

### 第三阶段：面试加分项

1. RAG embedding 可插拔设计。
2. Prompt 模板变量校验和 fallback 策略。
3. PDF 报告安全下载。
4. MySQL 与 Chroma 最终一致性策略。
5. 统一异常处理和统一响应结构。
6. RBAC 管理员权限控制。
7. 检测接口限流和成本保护。
8. 管理员审计日志。

## 十三、给项目作者的最终建议

这个项目当前最像企业级项目的地方：

- 后端结构清楚，职责分层完整。
- JWT 鉴权和管理员权限依赖集中。
- PDF 下载做了用户权限校验、目录限制和文件名白名单。
- Prompt 校验、LLM 返回解析和知识库同步状态已经有工程意识。
- 后端测试数量和覆盖范围较好。

最不像企业级项目的地方：

- 默认 RAG embedding 仍然是演示级 hash。
- 演示账号固定弱口令公开化。
- 系统日志还没有后端落地。
- 前端存在较多历史兼容字段，接口契约不够硬。

简历中建议突出：

- 基于 FastAPI + Vue3 的新闻可信度评估系统。
- 实现 JWT 鉴权、管理员 RBAC、新闻检测历史、RAG 知识库、Prompt 模板管理、PDF 报告生成、高风险新闻审核、统计图表。
- 使用 Chroma 构建向量检索链路，并设计 MySQL 与向量库同步状态。
- 对 LLM 返回非 JSON、Prompt 模板缺失、报告路径安全等场景做了工程兜底。

面试时解释不足可以这样说：

> 当前项目处于课程答辩和简历展示阶段，重点是把单体应用的业务闭环、权限、安全下载、RAG 链路和管理后台做完整。默认 hash embedding 是本地演示兜底，真实环境会切换到语义 embedding 并重建 Chroma；日志审计和迁移体系是后续企业级增强项，已经在文档和页面中预留方向。

## 十四、逐个修复任务清单

### 任务 1：切换真实语义 embedding

- 修复目标：让 RAG 具备真实语义召回能力。
- 涉及文件：
  - `backend/app/core/config.py`
  - `backend/app/services/embedding_service.py`
  - `backend/.env.example`
  - `README.md`
- 修改要求：
  - 将答辩推荐配置改为真实 embedding provider。
  - 保留 hash 作为本地 fallback，但文档明确其非语义。
  - 提供重建 Chroma 索引说明。
- 禁止事项：
  - 禁止提交真实 API Key。
  - 禁止删除 hash fallback。
- 测试方式：
  - `python -m unittest discover -s tests -p "test_embedding_service.py"`
  - `python -m unittest discover -s tests -p "test_rag_api.py"`
  - `python -m unittest discover -s tests -p "test_knowledge_sync.py"`
- 完成后输出：
  - 说明当前 provider 配置方式。
  - 说明如何重建知识库向量。

### 任务 2：移除公开固定演示口令

- 修复目标：避免演示账号弱口令公开化。
- 涉及文件：
  - `backend/app/db/seed_demo_data.py`
  - `README.md`
  - `backend/README.md`
  - `CLAUDE.md`
- 修改要求：
  - 演示口令从环境变量读取。
  - 未配置时生成本地随机口令并仅在 seed 输出中展示。
  - 文档不再复述固定口令。
- 禁止事项：
  - 禁止在文档中写死任何真实或固定密码。
  - 禁止移除演示账号功能。
- 测试方式：
  - 运行认证相关测试。
  - 搜索文档确认没有固定弱口令。
- 完成后输出：
  - 新的演示账号使用方式。

### 任务 3：为登录和注册接口增加限流

- 修复目标：降低暴力登录和批量注册风险。
- 涉及文件：
  - `backend/app/api/v1/auth.py`
  - `backend/app/core/rate_limit.py`
  - `backend/tests/test_auth_smoke.py` 或新增认证限流测试。
- 修改要求：
  - 复用 `InMemoryRateLimiter`。
  - 登录和注册分别使用独立 key 前缀。
  - 超限返回 429 和统一错误结构。
- 禁止事项：
  - 禁止改变登录成功响应结构。
  - 禁止影响 `get_current_user`。
- 测试方式：
  - 连续请求触发 429。
  - 正常登录仍返回 token。
- 完成后输出：
  - 限流窗口和次数说明。

### 任务 4：为检测流程增加 LLM 失败降级

- 修复目标：DeepSeek 不可用时检测流程仍可演示。
- 涉及文件：
  - `backend/app/services/detection_service.py`
  - `backend/app/schemas/detection.py`
  - `backend/tests/test_detect_api.py`
  - `backend/tests/test_llm_service.py`
- 修改要求：
  - LLM 失败时使用 RAG 证据分和规则分生成降级结果。
  - 响应中明确说明 LLM 不可用。
  - 检测记录仍保存，避免结果页无数据。
- 禁止事项：
  - 禁止伪造 DeepSeek 成功。
  - 禁止吞掉错误原因。
- 测试方式：
  - Mock LLM 失败，确认接口返回 200 或业务可展示响应。
  - 确认记录保存。
- 完成后输出：
  - 降级策略说明。

### 任务 5：补齐知识库向量状态服务端筛选

- 修复目标：修复知识库列表筛选分页不准确。
- 涉及文件：
  - `backend/app/api/v1/admin_knowledge.py`
  - `backend/app/services/knowledge_service.py`
  - `backend/app/crud/knowledge_crud.py`
  - `frontend/src/views/admin/AdminKnowledgeView.vue`
- 修改要求：
  - 后端接收 `vector_sync_status` 查询参数。
  - CRUD 查询按该字段过滤。
  - 前端删除“当前页本地过滤”逻辑或只保留展示兜底。
- 禁止事项：
  - 禁止改变原有分页字段结构。
  - 禁止破坏 category/truth_label/risk_level/keyword 筛选。
- 测试方式：
  - 增加后端筛选测试。
  - 前端构建通过。
- 完成后输出：
  - 说明筛选参数和分页行为。

### 任务 6：实现最小系统日志后端

- 修复目标：让管理员日志页面从占位变为真实可查。
- 涉及文件：
  - `backend/app/models`
  - `backend/app/schemas`
  - `backend/app/crud`
  - `backend/app/services`
  - `backend/app/api/v1`
  - `frontend/src/views/admin/AdminLogsView.vue`
- 修改要求：
  - 新增系统日志模型和查询接口。
  - 记录登录、检测、管理员操作等关键事件。
  - 支持分页和模块筛选。
- 禁止事项：
  - 禁止记录密码、token、API Key、Cookie 等敏感信息。
  - 禁止为了日志功能大规模重构主流程。
- 测试方式：
  - 普通用户访问日志接口返回 403。
  - 管理员可分页查询日志。
  - 登录和检测生成日志。
- 完成后输出：
  - 日志字段说明。
  - 涉及接口说明。
