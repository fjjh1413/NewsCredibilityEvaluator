# 07_phase2_knowledge_rag_prompts.md

> 项目：智闻辨真：基于 RAG 与大语言模型的新闻可信度评估系统  
> 角色分工：ChatGPT 负责项目规划、需求拆解、技术方案、Prompt 设计、代码审查意见；Codex 负责辅助编码、修复 Bug、补接口、补页面和生成测试。  
> 使用原则：每次只让 Codex 完成一个明确任务，完成后必须说明修改文件、运行方式、测试方式和未完成风险。


# 第二阶段：知识库管理与 RAG 检索开发方案

## 一、阶段目标

第二阶段的目标是完成系统的“知识库底座”和“RAG 检索能力”。本阶段不急于接入 DeepSeek，也不急于做完整新闻检测，而是先保证新闻知识库可以被管理员维护，并且知识库内容能够向量化写入 Chroma，支持根据新闻标题和正文召回 Top10 相似证据。

完成本阶段后，系统应具备以下能力：

1. 管理员可以新增、编辑、删除、查询新闻知识库数据；
2. MySQL 保存知识库原始结构化数据；
3. Chroma 保存知识库文本向量；
4. 后端提供 RAG 检索接口；
5. 输入新闻标题和正文后，系统可以返回 Top10 相似新闻或辟谣证据；
6. 后端逻辑分层清晰，接口层不直接写向量库逻辑。

## 二、技术方案

### 2.1 后端模块拆分

建议在 `backend/app/` 下保持如下结构：

```text
app/
├── api/
│   └── v1/
│       ├── admin_knowledge.py
│       └── rag.py
├── crud/
│   └── knowledge_crud.py
├── models/
│   └── knowledge.py
├── schemas/
│   ├── knowledge_schema.py
│   └── rag_schema.py
├── services/
│   ├── embedding_service.py
│   ├── chroma_service.py
│   └── knowledge_service.py
└── utils/
    └── text_cleaner.py
```

### 2.2 MySQL 与 Chroma 分工

MySQL 负责保存结构化业务数据：

- 标题
- 正文
- 类别
- 真实性标签
- 来源名称
- 来源链接
- 发布时间
- 摘要
- 关键词
- 辟谣说明
- 风险等级
- 管理员备注
- Chroma 中的向量 ID

Chroma 负责保存语义向量和检索元数据：

- vector_id
- title
- summary
- category
- truth_label
- source_name
- knowledge_id

不要把 MySQL 当作向量检索工具，也不要把 Chroma 当作完整业务数据库。

向量同步状态字段建议：

```sql
vector_sync_status VARCHAR(20) NOT NULL DEFAULT 'pending',
vector_sync_error TEXT NULL
```

### 2.3 向量文本拼接策略

写入 Chroma 时，不建议只向量化正文。建议将多字段拼接成检索文本：

```text
title: 新闻标题
category: 新闻类别
content: 新闻正文
summary: 新闻摘要
keywords: 关键词
truth_label: 真实性标签
debunking_explanation: 辟谣说明
```

这样用户输入相似标题、正文、关键词或谣言描述时，都更容易召回相关证据。

### 2.4 Top-K 检索策略

课程阶段固定为：

```text
检索 Top10
页面展示 Top10
后续 Prompt 使用 Top5
```

本阶段默认返回 Top10，不负责大模型分析。接口参数 `top_k` 默认值为 10，允许范围为 1 到 50，超过范围应返回参数校验错误。

## 三、本阶段开发提示词 1：实现知识库 MySQL 管理

```text
你现在负责开发“智闻辨真”项目第二阶段的知识库管理模块。请先阅读 docs/01_project_design.md、docs/02_database_design.md、docs/03_api_design.md、docs/05_project_structure.md。

本次任务只实现 MySQL 层面的新闻知识库管理，不接入 Chroma，不接入 DeepSeek，不实现新闻检测主流程。

技术栈：
后端：Python + FastAPI
数据库：MySQL
ORM：SQLAlchemy
认证：JWT

请完成以下内容：
1. 创建 knowledge_items 表对应的 SQLAlchemy Model；
2. 创建知识库相关 Pydantic Schema；
3. 创建 knowledge_crud.py，封装增删改查；
4. 创建 admin_knowledge.py 路由文件；
5. 实现以下接口：
   - GET /api/admin/knowledge
   - GET /api/admin/knowledge/{id}
   - POST /api/admin/knowledge
   - PUT /api/admin/knowledge/{id}
   - DELETE /api/admin/knowledge/{id}
6. 只有 admin 角色可以访问这些接口；
7. 支持按 category、truth_label、risk_level、keyword 查询；
8. 不要修改已有用户认证逻辑；
9. 不要把业务逻辑堆到路由函数里。

字段至少包括：
title、content、category、truth_label、source_name、source_url、publish_time、summary、keywords、debunking_explanation、risk_level、admin_note、vector_id、created_at、updated_at。

完成后请输出：
1. 修改了哪些文件；
2. 每个文件的作用；
3. 数据库迁移或建表方式；
4. Swagger 中如何测试接口；
5. 管理员权限如何验证；
6. 当前未完成内容。
```

## 四、本阶段开发提示词 2：封装文本清洗与向量文本构造

```text
请为知识库模块新增文本清洗和向量文本构造功能。

本次任务只处理文本工具函数，不接入 Chroma，不调用 DeepSeek。

要求：
1. 在 utils/text_cleaner.py 中实现基础文本清洗函数；
2. 清洗内容包括：去除多余空格、去除连续换行、限制超长文本、处理 None 值；
3. 在 services/knowledge_service.py 中实现 build_knowledge_embedding_text 函数；
4. 该函数将 title、content、category、summary、keywords、truth_label、debunking_explanation 拼接为适合向量化的文本；
5. 保证字段缺失时不会报错；
6. 为核心函数写简单单元测试或提供测试示例。

完成后请说明：
1. 向量文本拼接格式；
2. 如何手动测试；
3. 是否影响已有知识库接口。
```

## 五、本阶段开发提示词 3：接入 Chroma 向量数据库

```text
请在知识库模块基础上接入 Chroma 向量数据库。

本次任务只实现知识库向量化与相似检索，不接入 DeepSeek，不实现最终检测接口。

要求：
1. 新建 services/chroma_service.py；
2. 新建 services/embedding_service.py；
3. 使用 Chroma 保存知识库向量；
4. MySQL 保存原始知识库数据，Chroma 保存向量数据；
5. 向量库本地保存路径从环境变量读取，例如 CHROMA_PERSIST_DIR；
6. 新增或更新知识库数据时，可以同步写入或更新 Chroma；
7. 删除知识库数据时，同步删除 Chroma 中对应向量；
8. Chroma metadata 至少包含 knowledge_id、title、category、truth_label、source_name、risk_level；
9. 不要把 Chroma 逻辑写在路由层。

如果当前项目还没有确定 embedding 模型，请先使用一个可替换的 embedding_service 封装层，并在代码中预留后续更换模型的位置。

完成后请输出：
1. Chroma 保存目录；
2. 向量写入流程；
3. 向量更新流程；
4. 向量删除流程；
5. 如何测试 Chroma 是否写入成功。
```

## 六、本阶段开发提示词 4：实现 RAG Top10 检索接口

```text
请实现 RAG 相似证据检索接口。

接口要求：
POST /api/rag/search

请求参数：
{
  "title": "新闻标题",
  "content": "新闻正文",
  "top_k": 10
}

返回结果：
{
  "query": "拼接后的检索文本摘要",
  "top_k": 10,
  "results": [
    {
      "id": 1,
      "title": "相似新闻标题",
      "summary": "摘要",
      "category": "社会",
      "truth_label": "谣言",
      "source_name": "示例来源",
      "similarity_score": 0.87,
      "vector_sync_status": "synced"
    }
  ]
}

兼容说明：
- 推荐请求使用 `title`、`content`、`top_k`；
- 可兼容旧输入 `query`、`top_k`；
- 同时传入 `query` 和 `title/content` 时，以 `title/content` 拼接后的文本为准；
- 响应体必须包含 `query`、`top_k`、`results` 字段，`results` 为空时返回空数组。

示例响应可以额外包含 `total`：

{
  "query": "拼接后的检索文本摘要",
  "top_k": 10,
  "results": [
    {
      "id": 1,
      "title": "相似新闻标题",
      "summary": "摘要",
      "category": "社会",
      "truth_label": "谣言",
      "source_name": "示例来源",
      "similarity_score": 0.87,
      "vector_sync_status": "synced"
    }
  ],
  "total": 1
}

要求：
1. 默认 top_k=10；
2. 最大 top_k 不超过 50；
3. 输入为空时返回明确错误；
4. 检索不到结果时返回空列表，不要报 500；
5. 该接口后续会被新闻检测主流程调用；
6. 不要在本次任务中调用 DeepSeek。

完成后请给出：
1. Swagger 测试方式；
2. 示例请求；
3. 示例响应；
4. 可能的错误返回；
5. 下一阶段如何复用该接口。
```

## 七、本阶段验收标准

完成第二阶段后，必须能验证以下内容：

```text
1. 管理员能新增一条知识库新闻；
2. MySQL 中能看到该知识库记录；
3. Chroma 中能写入对应向量；
4. 调用 /api/rag/search 能返回 Top10 相似证据；
5. 删除知识库记录后，对应 Chroma 向量也能删除；
6. 普通用户不能访问 /api/admin/knowledge；
7. Swagger 文档中能看到所有接口。
```

## 八、代码审查提示词

```text
请作为代码审查员，检查第二阶段知识库与 RAG 检索代码。

重点检查：
1. 是否把 Chroma 逻辑写进路由层；
2. MySQL 和 Chroma 数据是否可能不一致；
3. 删除知识库时是否同步删除向量；
4. 管理员权限是否严格生效；
5. top_k 是否有限制，避免过大请求；
6. 输入为空、检索为空、Chroma 异常时是否有合理错误处理；
7. 是否存在硬编码路径；
8. 是否影响第一阶段登录注册功能。

请输出：
- 严重问题；
- 一般问题；
- 可优化点；
- 建议修改方案；
- 不要直接改代码，先给审查报告。
```
