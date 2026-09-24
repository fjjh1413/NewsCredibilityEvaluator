# ADR-002：检索分数语义与跨存储证据版本

状态：已实现；不代表阈值已经通过质量基准校准。

## 问题

旧 v2 把 RRF / 加权融合分写入 `similarity_score`，联网路由却把该值当作
cosine 使用。重排后的第一条也未必具有最高 cosine。与此同时，联网合并会
重建有限字段的字典，丢失 v2 的 chunks、supporting_spans、检索查询和索引版本。
异步索引更新期间，Chroma 还可能保存 MySQL 已删除或已修改的父文档。

## 决策

1. `raw_cosine_score` 表示真实向量 cosine（-1 至 1）；仅词项命中的候选为 null。
   `similarity_score` 是兼容 v1 的非负截断别名，不能承载融合或重排分。
   `fusion_score` 独立记录当前融合阶段的分数；`rerank_score` 独立记录重排分。
   `score_components` 保留各阶段诊断信息。
2. 联网路由只使用本地候选中的最大 cosine 和达到 cosine 阈值的候选数。
   缺少新字段的 v1 仍读取其旧 similarity；缺少新字段的 v2 不猜测分数语义，
   按无可靠相似度处理。原有 0.45 / 0.60 / 0.30 阈值保持不变，后续由独立
   评测校准。分数语义一致并不等于阈值已经证明有效。
3. 多查询融合保留最大原始 cosine，并单独写入融合分。联网合并深拷贝完整
   本地候选，只覆盖来源、规范化文本、候选 ID 等归一化字段；不会丢失片段。
4. 每个新写入的 v2 chunk 携带 `parent_revision`：对标题、正文、摘要、
   关键词、核验说明、分类、标签、来源、URL、发布时间和风险级别做确定性哈希。
   不包含同步状态和 `updated_at`，避免同步操作本身改变版本。
5. dense 检索后批量查询当前 MySQL 父记录；仅保留存在、已同步、版本一致且
   仍符合元数据过滤条件的结果，使用当前数据库字段更新父元数据。
   当前 MySQL 的词项检索仍可独立返回新内容，不能把旧 chunk 附加给它。
6. hybrid 的 v1 回退显式排除 v2 chunk，以及当前已经由 v2 管理的父记录，
   防止从同一个 Chroma collection 重新取回已被版本校验拒绝的内容。

## 升级现有索引

旧 v2 chunk 没有 `parent_revision`，部署后不会作为 dense 证据返回。它们不会
被自动删除；需要以管理员身份通过现有知识库“重建索引”功能（
`POST /api/admin/knowledge/rebuild-index`）排队重建，等待索引任务完成并确认
知识记录 `vector_sync_status=synced`。重建会替换当前索引，应在维护窗口执行。
也可逐条调用 `POST /api/admin/knowledge/{id}/vectorize` 分批更新。

`GET /api/rag/audit` 将缺失或不匹配的版本报告为 `stale_parent_revision`。
审计默认抽样，不能把样本通过等同于完整索引全部通过。
本次代码改造没有连接或重建用户现有的生产数据。

## 取舍与边界

- 旧索引须重建，换取不把无法确认版本的内容交给 LLM。重建前仍可使用当前
  MySQL 词项候选或已授权的联网补证；没有证据时由检测状态表示无法判断。
- 检索增加一次按父 ID 批量数据库查询和内容指纹计算；没有声称延迟收益。
- MySQL 与 Chroma 仍非分布式事务；校验保证读到的候选与本次数据库读取一致，
  不承诺跨系统线性一致性，也不修复索引队列的租约/崩溃恢复问题。
- RRF、规则重排分和 cosine 不等于事实正确概率，不应用于准确率宣传。

## 回归验证

`test_rag_evidence_integrity.py` 使用真实临时 SQLite 父记录和模拟向量 I/O，
覆盖删除、修改、待同步、旧索引、过滤条件、hybrid 回退以及
v2 检索→多查询融合→联网路由→合并的组合路径。
`test_web_search_service.py` 检查高融合分不能掩盖低 cosine、重排顺序不影响
路由、非有限分数保守处理及合并后嵌套对象互不修改。

2026-09-19 定向运行 RAG、知识同步、Web 合并与 RAG API 共 11 个测试模块：
109 项通过（unittest，1.373 秒）。环境使用临时 SQLite、hash embedding，
禁用 dotenv、Redis 与真实联网；该结果验证执行行为，不代表语义检索质量。
