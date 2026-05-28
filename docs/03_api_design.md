# 03 后端接口设计文档

# 智闻辨真：API 接口设计说明

> 本文档用于指导 FastAPI 后端接口开发。  
> 后续使用 Codex 开发时，应严格按照本文档中的接口路径、请求方式、功能说明和返回结构进行实现。  
> FastAPI 默认提供 Swagger 文档，因此开发完成后应能通过 `/docs` 查看接口说明。

---

## 1. API 设计原则

### 1.1 路径规范

统一使用 `/api` 作为接口前缀。

示例：

```text
/api/auth/login
/api/detect/news
/api/admin/knowledge
```

### 1.2 返回格式规范

所有接口建议使用统一返回格式：

```json
{
  "code": 200,
  "message": "success",
  "data": {}
}
```

错误示例：

```json
{
  "code": 400,
  "message": "请求参数错误",
  "data": null
}
```

### 1.3 权限规范

系统角色包括：

- user：普通用户；
- admin：管理员。

权限规则：

| 功能 | 游客 | 普通用户 | 管理员 |
|---|---|---|---|
| 注册登录 | 可访问 | 可访问 | 可访问 |
| 新闻检测 | 可访问，但不保存个人历史 | 可访问 | 可访问 |
| 查看个人历史 | 不可访问 | 可访问 | 可访问 |
| 管理知识库 | 不可访问 | 不可访问 | 可访问 |
| 管理 Prompt | 不可访问 | 不可访问 | 可访问 |
| 查看后台统计 | 不可访问 | 不可访问 | 可访问 |

### 1.4 认证方式

使用 JWT 认证。

请求头格式：

```text
Authorization: Bearer <token>
```

---

## 2. 认证模块

---

### 2.1 用户注册

```http
POST /api/auth/register
```

#### 功能说明

注册普通用户。

#### 请求参数

```json
{
  "username": "test_user",
  "password": "123456",
  "email": "test@example.com"
}
```

#### 返回示例

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

---

### 2.2 用户登录

```http
POST /api/auth/login
```

#### 功能说明

用户登录，返回 JWT Token。

#### 请求参数

```json
{
  "username": "test_user",
  "password": "123456"
}
```

#### 返回示例

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

---

### 2.3 获取当前用户

```http
GET /api/auth/me
```

#### 功能说明

根据 Token 获取当前登录用户信息。

#### 请求头

```text
Authorization: Bearer <token>
```

#### 返回示例

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

---

## 3. 新闻检测模块

---

### 3.1 提交新闻检测

```http
POST /api/detect/news
```

#### 功能说明

用户输入新闻标题和正文，系统执行 RAG 检索、大模型分析、规则评分和报告生成。

#### 权限

- 游客可访问；
- 登录用户可访问；
- 登录用户的检测记录需要绑定 user_id；
- 游客检测可以不绑定 user_id。

#### 请求参数

```json
{
  "title": "某地发生紧急事件，网传消息引发关注",
  "content": "这里是新闻正文内容……",
  "category": "社会",
  "source_name": "网络来源"
}
```

#### 后端处理流程

```text
1. 接收标题和正文
2. 文本预处理
3. 提取关键词
4. 调用 Chroma 检索 Top10 证据
5. 取 Top5 证据构造 RAG Prompt
6. 调用 DeepSeek 进行分析
7. 执行规则评分
8. 计算最终可信度评分
9. 生成风险等级
10. 保存检测记录
11. 保存证据匹配结果
12. 生成 HTML / PDF 报告
13. 返回检测结果
```

#### 返回示例

```json
{
  "code": 200,
  "message": "检测完成",
  "data": {
    "detection_id": 1001,
    "final_score": 68.5,
    "evidence_score": 72.0,
    "llm_score": 65.0,
    "rule_score": 70.0,
    "risk_level": "存疑信息",
    "judgement_result": "该新闻存在一定风险，建议进一步核查。",
    "reason": "该新闻缺少明确权威来源，且部分表述存在夸张倾向。",
    "risk_points": [
      "来源不明确",
      "标题存在情绪化表达",
      "部分内容缺少证据支持"
    ],
    "keywords": [
      "紧急事件",
      "网传消息",
      "官方回应"
    ],
    "evidence_list": [
      {
        "knowledge_id": 1,
        "title": "相关事件官方通报",
        "summary": "官方曾对类似事件进行说明。",
        "source_name": "官方媒体",
        "similarity_score": 0.8321,
        "rank_order": 1
      }
    ],
    "similar_news": [
      {
        "title": "类似新闻标题",
        "risk_level": "存疑信息"
      }
    ],
    "suggestion": "建议查看官方通报或权威媒体报道，不要直接转发未经证实的信息。",
    "agent_steps": [
      "关键词提取完成",
      "知识库证据检索完成",
      "大模型可信度分析完成",
      "风险规则评分完成",
      "检测报告生成完成"
    ],
    "report_url": "/api/report/download/1"
  }
}
```

---

### 3.2 获取个人检测历史

```http
GET /api/detect/history
```

#### 功能说明

获取当前用户的历史检测记录。

#### 权限

登录用户。

#### 查询参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| page | int | 否 | 页码 |
| page_size | int | 否 | 每页数量 |
| risk_level | string | 否 | 风险等级筛选 |

#### 返回示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "total": 1,
    "items": [
      {
        "id": 1001,
        "input_title": "某地发生紧急事件",
        "final_score": 68.5,
        "risk_level": "存疑信息",
        "is_high_risk": false,
        "created_at": "2026-05-25 10:00:00"
      }
    ]
  }
}
```

---

### 3.3 获取检测详情

```http
GET /api/detect/{id}
```

#### 功能说明

获取单条检测记录详情，包括证据匹配结果和报告信息。

#### 权限

- 普通用户只能查看自己的检测记录；
- 管理员可以查看全部记录。

---

## 4. RAG 检索模块

---

### 4.1 相似证据检索

```http
POST /api/rag/search
```

#### 功能说明

根据输入文本在 Chroma 中检索 Top10 相似证据。

#### 请求参数

```json
{
  "query": "输入的新闻标题和正文",
  "top_k": 10
}
```

#### 返回示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [
      {
        "knowledge_id": 1,
        "title": "相关新闻标题",
        "summary": "相关证据摘要",
        "source_name": "官方媒体",
        "similarity_score": 0.8321,
        "rank_order": 1
      }
    ]
  }
}
```

---

### 4.2 重建向量索引

```http
POST /api/rag/rebuild-index
```

#### 功能说明

管理员重新将 MySQL 中的知识库数据写入 Chroma。

#### 权限

管理员。

#### 返回示例

```json
{
  "code": 200,
  "message": "向量索引重建完成",
  "data": {
    "total": 100,
    "success": 98,
    "failed": 2
  }
}
```

---

## 5. 管理员知识库模块

---

### 5.1 获取知识库列表

```http
GET /api/admin/knowledge
```

#### 权限

管理员。

#### 查询参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| page | int | 否 | 页码 |
| page_size | int | 否 | 每页数量 |
| category | string | 否 | 类别筛选 |
| truth_label | string | 否 | 标签筛选 |
| keyword | string | 否 | 标题关键词 |

---

### 5.2 新增知识库数据

```http
POST /api/admin/knowledge
```

#### 请求参数

```json
{
  "title": "新闻标题",
  "content": "新闻正文",
  "category": "社会",
  "truth_label": "可信",
  "source_name": "官方媒体",
  "source_url": "https://example.com/news/1",
  "publish_time": "2026-05-25 10:00:00",
  "summary": "新闻摘要",
  "keywords": "关键词1,关键词2",
  "debunking_explanation": "辟谣说明",
  "risk_level": "可信新闻",
  "admin_note": "管理员备注"
}
```

#### 处理逻辑

```text
1. 保存原始数据到 MySQL
2. 生成文本向量
3. 写入 Chroma
4. 更新 MySQL 中的 vector_id
```

---

### 5.3 更新知识库数据

```http
PUT /api/admin/knowledge/{id}
```

#### 功能说明

更新知识库数据。  
如果更新了标题、正文、摘要或关键词，需要重新生成向量。

---

### 5.4 删除知识库数据

```http
DELETE /api/admin/knowledge/{id}
```

#### 功能说明

删除 MySQL 中知识库数据，并尝试删除 Chroma 中对应向量。

---

### 5.5 单条知识库向量化

```http
POST /api/admin/knowledge/{id}/vectorize
```

#### 功能说明

对某一条知识库数据重新生成向量并写入 Chroma。

---

## 6. Prompt 模板模块

---

### 6.1 获取 Prompt 模板列表

```http
GET /api/admin/prompts
```

#### 权限

管理员。

---

### 6.2 新增 Prompt 模板

```http
POST /api/admin/prompts
```

#### 请求参数

```json
{
  "name": "新闻可信度分析模板",
  "type": "credibility_analysis",
  "content": "你是新闻可信度分析助手……",
  "is_default": true,
  "status": "enabled"
}
```

---

### 6.3 编辑 Prompt 模板

```http
PUT /api/admin/prompts/{id}
```

---

### 6.4 删除 Prompt 模板

```http
DELETE /api/admin/prompts/{id}
```

---

### 6.5 启用 Prompt 模板

```http
POST /api/admin/prompts/{id}/enable
```

---

### 6.6 停用 Prompt 模板

```http
POST /api/admin/prompts/{id}/disable
```

---

### 6.7 设为默认 Prompt 模板

```http
POST /api/admin/prompts/{id}/set-default
```

#### 逻辑说明

同一 `type` 下只能有一个默认模板。  
设置当前模板为默认时，需要将同类型其他模板的 `is_default` 设为 0。

---

## 7. 高风险新闻模块

---

### 7.1 前台获取高风险新闻

```http
GET /api/high-risk
```

#### 功能说明

普通用户查看已审核并公开展示的高风险新闻案例。

#### 查询参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| page | int | 否 | 页码 |
| page_size | int | 否 | 每页数量 |
| category | string | 否 | 类别筛选 |
| keyword | string | 否 | 关键词搜索 |

---

### 7.2 管理员获取高风险新闻

```http
GET /api/admin/high-risk
```

#### 权限

管理员。

---

### 7.3 审核高风险新闻

```http
POST /api/admin/high-risk/{id}/review
```

#### 请求参数

```json
{
  "review_status": "approved",
  "is_public": true,
  "admin_note": "该案例可作为高风险样例展示。"
}
```

---

### 7.4 编辑高风险新闻

```http
PUT /api/admin/high-risk/{id}
```

---

## 8. 数据统计模块

---

### 8.1 后台统计总览

```http
GET /api/admin/statistics/overview
```

#### 返回示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "total_users": 120,
    "total_detections": 860,
    "total_knowledge": 100,
    "total_high_risk": 45,
    "today_detections": 20
  }
}
```

---

### 8.2 检测趋势

```http
GET /api/admin/statistics/trend
```

#### 返回示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "dates": ["2026-05-20", "2026-05-21"],
    "counts": [12, 18]
  }
}
```

---

### 8.3 风险等级分布

```http
GET /api/admin/statistics/risk-distribution
```

#### 返回示例

```json
{
  "code": 200,
  "message": "success",
  "data": [
    {"name": "可信新闻", "value": 100},
    {"name": "存疑信息", "value": 80},
    {"name": "疑似谣言", "value": 40},
    {"name": "高风险谣言", "value": 20}
  ]
}
```

---

### 8.4 新闻类别分布

```http
GET /api/admin/statistics/category-distribution
```

---

### 8.5 高频关键词

```http
GET /api/admin/statistics/keywords
```

---

## 9. 报告模块

---

### 9.1 生成检测报告

```http
POST /api/report/generate/{detection_id}
```

#### 功能说明

根据检测记录生成 HTML 和 PDF 报告。

#### 权限

- 普通用户只能生成自己的报告；
- 管理员可以生成任意检测记录的报告。

---

### 9.2 下载检测报告

```http
GET /api/report/download/{report_id}
```

#### 功能说明

下载 PDF 检测报告。

---

## 10. 管理员检测记录模块

---

### 10.1 获取全部检测记录

```http
GET /api/admin/detections
```

#### 权限

管理员。

#### 查询参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| page | int | 否 | 页码 |
| page_size | int | 否 | 每页数量 |
| risk_level | string | 否 | 风险等级 |
| keyword | string | 否 | 标题关键词 |
| user_id | int | 否 | 用户ID |

---

### 10.2 删除检测记录

```http
DELETE /api/admin/detections/{id}
```

---

## 11. 用户管理模块

---

### 11.1 获取用户列表

```http
GET /api/admin/users
```

#### 权限

管理员。

---

### 11.2 启用用户

```http
POST /api/admin/users/{id}/enable
```

---

### 11.3 禁用用户

```http
POST /api/admin/users/{id}/disable
```

---

## 12. 系统日志模块

---

### 12.1 获取系统日志

```http
GET /api/admin/logs
```

#### 权限

管理员。

#### 查询参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| page | int | 否 | 页码 |
| page_size | int | 否 | 每页数量 |
| module | string | 否 | 模块 |
| action | string | 否 | 操作 |
| user_id | int | 否 | 用户ID |

---

## 13. 健康检查接口

```http
GET /api/health
```

#### 功能说明

用于检查后端服务是否正常运行。

#### 返回示例

```json
{
  "code": 200,
  "message": "service is running",
  "data": {
    "service": "zhiyun-bianzhen-backend",
    "status": "ok"
  }
}
```

---

## 14. DeepSeek 返回 JSON 规范

调用 DeepSeek 时，要求模型尽量返回以下结构：

```json
{
  "llm_score": 70,
  "risk_level": "存疑信息",
  "judgement_result": "该新闻存在一定风险，建议进一步核查。",
  "reason": "该新闻缺少明确来源，且部分表述与知识库证据不完全一致。",
  "risk_points": [
    "来源不明确",
    "缺少权威证据",
    "存在情绪化表达"
  ],
  "keywords": [
    "网传",
    "官方回应",
    "风险提示"
  ],
  "suggestion": "建议核查权威媒体报道或官方通报，不要直接转发未经证实的信息。"
}
```

如果模型返回非 JSON 文本，后端需要做容错处理：

1. 尝试提取 JSON；
2. 提取失败时返回默认结构；
3. 在 reason 中说明模型返回格式异常；
4. 不允许后端程序直接崩溃。

---

## 15. Codex 开发要求

使用 Codex 开发接口时，必须遵守：

1. 路径以本文档为准；
2. 请求字段和返回字段以本文档为准；
3. 每个接口必须有 Pydantic Schema；
4. 不要把业务逻辑全部写在路由函数中；
5. 路由层只负责接收请求和返回响应；
6. 业务逻辑放到 service 层；
7. 数据库操作放到 crud 层；
8. DeepSeek 调用放到 llm_service.py；
9. Chroma 检索放到 chroma_service.py；
10. 报告生成放到 report_service.py；
11. 权限校验统一放到依赖函数中；
12. 每个模块完成后必须能在 Swagger 中测试。
