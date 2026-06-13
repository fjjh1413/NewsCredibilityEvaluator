# DeepSeek Embedding 接入报告

> **日期**：2026-06-11  
> **分支**：main  
> **状态**：历史记录。当前正式推荐配置已切换为 DashScope `text-embedding-v4`，DeepSeek embedding 仅保留为兼容 provider。

---

## 1. 背景与动机

### 1.1 问题

项目自初版起，`embedding_service.py` 默认使用 **hash 向量**（SHA-256 哈希 + 余弦归一化）作为 Chroma 向量库的 embedding 实现。

```python
# hash embedding 的问题
- 不编码语义：token 被哈希到固定维度桶位，语义相似的文本可能产生完全不同的向量
- 相似度不可靠：cosine similarity 只反映哈希碰撞概率，不反映新闻内容相关性
- RAG 检索质量低：Top-K 召回的证据与输入新闻没有语义关联
```

`embedding_service.py` 第 24 行及 `EMBEDDING_PROVIDER` 的注释明确标注此为**演示回退**，`deepseek` 和 `local` 两个 provider 仅作为预留桩存在，调用即抛 `EmbeddingProviderNotConfiguredError`。

### 1.2 目标

将 `deepseek` provider 从预留桩改为**生产可用的语义 embedding 实现**，通过 DeepSeek Embeddings API 生成真实语义向量，提升 RAG 检索质量。

---

## 2. 变更概览

| 文件 | 操作 | 行数变化 | 说明 |
|------|------|----------|------|
| [backend/app/services/embedding_service.py](backend/app/services/embedding_service.py) | 重写 | +257 | 实现 DeepSeek embeddings API 客户端 |
| [backend/app/core/config.py](backend/app/core/config.py) | 修改 | +3 | 新增 `deepseek_embedding_model` 配置项 |
| [backend/.env.example](backend/.env.example) | 修改 | +17 | 新增环境变量文档 |
| [backend/tests/test_embedding_service.py](backend/tests/test_embedding_service.py) | 重写 | +168 | 新增 5 个 DeepSeek provider 测试 |

---

## 3. 架构设计

### 3.1 Embedding Provider 体系

```
embedding_service.py
├── hash provider (保留，演示/开发用)
│   └── SHA-256 哈希 + L2 归一化，确定性输出
├── deepseek provider (本次实现，生产用) 🆕
│   └── 调用 DeepSeek Embeddings API (/v1/embeddings)
│   └── OpenAI 兼容协议，批量嵌入支持
└── local provider (预留，未来本地模型)
```

### 3.2 DeepSeek Provider 数据流

```
embed_text / embed_texts
        │
        ▼
_deepseek_embed_batch(texts)
        │
        ├─ _load_deepseek_embedding_config()
        │   ├─ DEEPSEEK_API_KEY (环境变量，与 LLM 服务共用)
        │   ├─ DEEPSEEK_BASE_URL (默认 https://api.deepseek.com)
        │   ├─ DEEPSEEK_EMBEDDING_MODEL (默认 deepseek-embedding-v1)
        │   └─ DEEPSEEK_EMBEDDING_TIMEOUT_SECONDS (默认 30)
        │
        ├─ _build_embeddings_url(base_url)
        │   └─ 组合为 {base_url}/v1/embeddings
        │
        ├─ POST /v1/embeddings
        │   Headers: Authorization: Bearer {api_key}
        │   Body: {"model": "...", "input": [...], "encoding_format": "float"}
        │
        └─ _parse_embeddings_response()
            └─ 从 data[].embedding 提取浮点向量列表
```

### 3.3 批量嵌入优化

**改动前**：`embed_texts()` 逐条调用 `embed_text()`，N 条文本 = N 次 API 调用

```python
# 旧实现
def embed_texts(texts, dimension=None):
    return [embed_text(text, dimension=dimension) for text in texts]
```

**改动后**：`embed_texts()` 一次性发送全部文本，N 条文本 = 1 次 API 调用

```python
# 新实现 — hash provider 保持逐条，deepseek provider 使用批量
if provider == DEEPSEEK_EMBEDDING_PROVIDER:
    return _deepseek_embed_batch(texts)
```

### 3.4 异常类型层次

```
RuntimeError
├── EmbeddingProviderNotConfiguredError   (provider 不支持)
└── DeepSeekEmbeddingError 🆕             (API 调用失败)
    ├── API Key 未配置
    ├── HTTP 4xx/5xx 错误
    ├── 网络连接异常
    ├── 请求超时
    └── JSON 解析失败
```

所有错误消息均为中文，与项目现有 `llm_service.py` 的 DeepSeek 错误处理风格一致。

---

## 4. 各文件变更详情

### 4.1 `backend/app/core/config.py`

新增 `Settings` 类属性：

```python
self.deepseek_embedding_model = os.getenv(
    "DEEPSEEK_EMBEDDING_MODEL", "deepseek-embedding-v1"
).strip()
```

读取优先级：环境变量 `DEEPSEEK_EMBEDDING_MODEL` → 默认 `deepseek-embedding-v1`。

该值在 `embedding_service.py` 中通过 `get_settings().deepseek_embedding_model` 访问，作为 API 调用 `model` 参数的兜底值（环境变量 `DEEPSEEK_EMBEDDING_MODEL` 仍可直接在 `embedding_service.py` 中读取，保持与现有 `llm_service.py` 一致的配置读取模式）。

### 4.2 `backend/app/services/embedding_service.py`

| 模块 | 变更类型 | 说明 |
|------|----------|------|
| 导入区 | 新增 | `json`, `logging`, `os`, `socket`, `urllib.error`, `urllib.request` |
| 常量 | 变更 | `RESERVED_EMBEDDING_PROVIDERS` 从 `{"deepseek", "local"}` 变为 `{"local"}` |
| 常量 | 新增 | API URL 构建、模型名、超时等 DeepSeek 配置常量 |
| `_hash_embed_text()` | 保留 | 无变更 |
| `_deepseek_embed_batch()` | 🆕 新增 | 核心实现：配置读取 → URL 构建 → API 调用 → 响应解析 |
| `_load_deepseek_embedding_config()` | 🆕 新增 | 从环境变量读取 API key、base URL、model、timeout |
| `_build_embeddings_url()` | 🆕 新增 | 基于 `DEEPSEEK_BASE_URL` 构建 `/v1/embeddings` 端点 |
| `_parse_embeddings_response()` | 🆕 新增 | 从 OpenAI 兼容响应中提取 embedding 向量数组 |
| `_extract_deepseek_error_message()` | 🆕 新增 | 从 API 错误响应中提取人类可读的错误信息 |
| `embed_text()` | 变更 | 新增 `deepseek` provider 分支 |
| `embed_texts()` | 变更 | 新增 `deepseek` provider 批量调用分支 |

**API 调用关键参数**：

| 参数 | 值 | 来源 |
|------|-----|------|
| `model` | `deepseek-embedding-v1` | `DEEPSEEK_EMBEDDING_MODEL` |
| `input` | `list[str]` | 调用方传入 |
| `encoding_format` | `"float"` | 固定值 |
| `Authorization` | `Bearer {key}` | `DEEPSEEK_API_KEY` |
| 超时 | 30s | `DEEPSEEK_EMBEDDING_TIMEOUT_SECONDS` |

### 4.3 `backend/.env.example`

新增配置块：

```bash
# DeepSeek embedding model name. Only used when EMBEDDING_PROVIDER=deepseek.
# deepseek-embedding-v1 outputs 1024-dim vectors; keep EMBEDDING_DIMENSION in sync.
DEEPSEEK_EMBEDDING_MODEL=deepseek-embedding-v1
# DeepSeek embedding API timeout in seconds (default: 30).
DEEPSEEK_EMBEDDING_TIMEOUT_SECONDS=30
```

同步更新了 `EMBEDDING_PROVIDER` 和 `EMBEDDING_DIMENSION` 的注释，说明三种 provider 的用途及切换时的注意事项。

### 4.4 `backend/tests/test_embedding_service.py`

| 测试用例 | 类型 | 说明 |
|----------|------|------|
| `test_deepseek_single_text_embedding` | 🆕 新增 | Mock API 返回 1024 维向量，验证单文本嵌入 |
| `test_deepseek_batch_embedding` | 🆕 新增 | Mock API 返回 3 条向量，验证批量嵌入 |
| `test_deepseek_handles_api_error` | 🆕 新增 | Mock HTTP 401 错误，验证 `DeepSeekEmbeddingError` |
| `test_deepseek_provider_without_api_key_raises` | 🆕 新增 | 不设 API key，验证 `DeepSeekEmbeddingError` |
| `test_settings_reads_deepseek_embedding_model` | 🆕 新增 | 验证 `Settings.deepseek_embedding_model` 读取 |
| `test_default_settings_use_dashscope_embedding_provider` | 修改 | 默认配置验证为 `dashscope` / `1024` |
| `test_reserved_provider_does_not_silently_use_hash_fallback` | 修改 | 测试对象从 `deepseek` 改为 `local` |

测试采用 `unittest.mock.patch` 策略：
- **环境变量注入**：`patch.dict(os.environ, {...}, clear=True)`
- **HTTP 拦截**：`patch.object(embedding_service.urllib.request, "urlopen", ...)`
- **辅助类**：`FakeResponse` 模拟 `urlopen` 返回的文件对象

---

## 5. 配置指南

### 5.1 基本配置（`backend/.env`）

```bash
# 当前正式推荐设置为 dashscope 才能启用语义嵌入
EMBEDDING_PROVIDER=dashscope

# 必须与模型输出维度一致（text-embedding-v4 推荐 1024）
EMBEDDING_DIMENSION=1024

# DashScope API 密钥
DASHSCOPE_API_KEY=sk-your-actual-api-key

# 以下为可选配置（有默认值）
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_EMBEDDING_MODEL=text-embedding-v4
DASHSCOPE_EMBEDDING_TIMEOUT_SECONDS=30
```

### 5.2 配置项对照表

| 环境变量 | 必填 | 默认值 | 生效条件 |
|----------|------|--------|----------|
| `EMBEDDING_PROVIDER` | 是 | `dashscope` | 始终；hash 仅用于本地演示 fallback |
| `EMBEDDING_DIMENSION` | 是 | `1024` | hash：控制输出；dashscope：必须与模型匹配 |
| `DASHSCOPE_API_KEY` | 是 | — | 默认 `EMBEDDING_PROVIDER=dashscope` 时必填 |
| `DASHSCOPE_BASE_URL` | 否 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `EMBEDDING_PROVIDER=dashscope` |
| `DASHSCOPE_EMBEDDING_MODEL` | 否 | `text-embedding-v4` | `EMBEDDING_PROVIDER=dashscope` |
| `DASHSCOPE_EMBEDDING_TIMEOUT_SECONDS` | 否 | `30` | `EMBEDDING_PROVIDER=dashscope` |

---

## 6. 迁移指南：hash → dashscope

### ⚠️ 注意

从 hash（384 维）切换到 dashscope/text-embedding-v4（1024 维）属于**不兼容变更**——Chroma 集合固定维度，插入不同维度的向量将报错。

### 迁移步骤

```bash
# 步骤 1：更新 .env
EMBEDDING_PROVIDER=dashscope
EMBEDDING_DIMENSION=1024
DASHSCOPE_API_KEY=sk-your-key

# 步骤 2：重建 Chroma 知识库向量索引
# 可用管理员账号调用 POST /api/admin/knowledge/rebuild-index
# 或删除旧 CHROMA_PATH 数据后重新执行 python -m app.db.seed_demo_data

# 步骤 4：验证
# 调用 RAG 检索接口，检查返回的 Top-K 证据是否与查询新闻语义相关
```

### 回退方案

```bash
# 切回 hash provider 并恢复维度设置
EMBEDDING_PROVIDER=hash
EMBEDDING_DIMENSION=384
# 同样需要重建 Chroma 索引。hash 只用于本地演示 fallback，不作为正式 RAG 方案
```

---

## 7. 测试结果

```
tests/test_embedding_service.py - 15 tests

✅ test_deepseek_single_text_embedding        Mock API 返回 1024 维向量
✅ test_deepseek_batch_embedding              Mock API 批量返回 3 条向量
✅ test_deepseek_handles_api_error            Mock HTTP 401 错误
✅ test_deepseek_provider_without_api_key_raises  未配置 API key 报错
✅ test_settings_reads_deepseek_embedding_model    配置读取验证
✅ test_default_settings_use_dashscope_embedding_provider
✅ test_embed_text_is_deterministic_and_normalized
✅ test_embed_empty_text_returns_zero_vector
✅ test_embed_text_rejects_non_positive_dimension
✅ test_embed_texts_handles_multiple_inputs
✅ test_hash_provider_runs_with_explicit_default_dimension
✅ test_hash_provider_uses_configured_dimension_by_default
✅ test_reserved_provider_does_not_silently_use_hash_fallback  (local)
✅ test_embedding_dimension_constant_reads_settings_on_import
✅ test_settings_reads_explicit_embedding_dimension

全项目：208 passed, 0 failed
```

---

## 8. 兼容性说明

| 场景 | 影响 |
|------|------|
| 现有 hash 用户 | **需显式配置**——设置 `EMBEDDING_PROVIDER=hash`、`EMBEDDING_DIMENSION=384` 后仍可作为本地演示 fallback |
| Chroma 调用方 (`chroma_service.py`) | **无影响**——`embed_text()` 签名和返回值格式不变 |
| `embed_texts()` 调用方 | **增强**——deepseek 模式下使用批量 API 调用，性能更好 |
| `DEEPSEEK_API_KEY` 复用 | **共用**——embedding 和 LLM analysis 读取同一环境变量 |

---

## 9. 后续建议

1. **本地模型支持**：`local` provider 目前仍为预留桩，可接入 `sentence-transformers` 或 `text2vec` 等本地 embedding 模型，实现离线推理

2. **模型维度自动检测**：当前维度需手动配置，未来可在首次 API 调用后自动读取返回向量的实际维度并校验配置一致性

3. **请求重试与熔断**：可参考 `chroma_service.py` 的重试模式，为 embedding API 调用增加指数退避重试

4. **向量缓存**：对高频查询文本（如热门新闻标题）的 embedding 结果进行 LRU 缓存，减少 API 调用成本

---

## 10. 变更记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-06-11 | 初版：实现 DeepSeek Embeddings API 客户端，完成测试覆盖 |
