# 08_phase3_llm_detection_prompts.md

> 项目：智闻辨真：基于 RAG 与大语言模型的新闻可信度评估系统  
> 角色分工：ChatGPT 负责项目规划、需求拆解、技术方案、Prompt 设计、代码审查意见；Codex 负责辅助编码、修复 Bug、补接口、补页面和生成测试。  
> 使用原则：每次只让 Codex 完成一个明确任务，完成后必须说明修改文件、运行方式、测试方式和未完成风险。


# 第三阶段：DeepSeek 接入与新闻检测主流程开发方案

## 一、阶段目标

第三阶段的目标是完成系统最核心的 AI 检测链路：输入新闻标题和正文后，系统自动检索证据、调用 DeepSeek 分析、执行规则评分、计算最终可信度、保存检测记录，并返回结构化检测结果。

本阶段完成后，后端应该已经具备完整新闻检测能力，即使前端还没有完善，也可以通过 Swagger 或 Postman 完整测试。

## 二、技术方案

### 2.1 检测主流程

```text
接收新闻标题和正文
        ↓
文本清洗与基础校验
        ↓
关键词提取
        ↓
调用 RAG 检索 Top10 相似证据
        ↓
取 Top5 证据构造 DeepSeek Prompt
        ↓
调用 DeepSeek 返回结构化 JSON
        ↓
执行风险规则评分
        ↓
计算最终可信度评分
        ↓
生成风险等级
        ↓
保存检测记录和证据匹配记录
        ↓
返回检测结果
```

### 2.2 评分公式

```text
最终可信度 = 检索证据相关度评分 × 40%
          + 大模型判断评分 × 40%
          + 来源 / 风险规则评分 × 20%
```

等级划分：

```text
80-100：可信新闻
60-79：存疑信息
40-59：疑似谣言
0-39：高风险谣言
```

### 2.3 DeepSeek 返回格式

要求模型尽量返回 JSON：

```json
{
  "llm_score": 72,
  "risk_level": "存疑信息",
  "reason": "该新闻缺少明确来源，且与知识库中的相似事件存在表述差异。",
  "risk_points": ["来源不明确", "存在夸张表述"],
  "keywords": ["关键词1", "关键词2"],
  "suggestion": "建议进一步核查官方通报或权威媒体。"
}
```

代码中必须考虑模型返回非标准 JSON 的情况，不能因为解析失败导致系统崩溃。

## 三、本阶段开发提示词 1：接入 DeepSeek API 服务

```text
你现在负责开发“智闻辨真”项目第三阶段的 DeepSeek 大模型调用服务。请先阅读 docs/01_project_design.md、docs/03_api_design.md、docs/07_phase2_knowledge_rag_prompts.md。

本次任务只实现 DeepSeek 调用封装，不实现新闻检测主流程，不修改前端。

要求：
1. 新建 services/llm_service.py；
2. 从环境变量读取 DeepSeek API Key、Base URL 和模型名称；
3. 不允许把 API Key 写死在代码里；
4. 封装 analyze_news_credibility 函数；
5. 输入参数包括 title、content、evidence_list、prompt_template；
6. 输出尽量解析为结构化 JSON；
7. 如果模型返回非 JSON，要有兜底解析；
8. 如果 API 调用失败，要返回可理解的错误信息；
9. 不要影响已有 RAG 检索接口。

返回结构字段：
- llm_score
- risk_level
- reason
- risk_points
- keywords
- suggestion

完成后请说明：
1. 环境变量如何配置；
2. 调用函数如何使用；
3. 失败时如何处理；
4. Swagger 中是否新增测试接口，如有请说明。
```

## 四、本阶段开发提示词 2：设计 DeepSeek 检测 Prompt

```text
请为新闻可信度评估设计一个可用于 DeepSeek 的 Prompt 模板，并封装到代码中，后续支持从 Prompt 模板表读取。

Prompt 要求：
1. 明确系统是“新闻可信度辅助评估工具”，不能绝对替代人工事实核查；
2. 输入包括新闻标题、新闻正文、Top5 检索证据；
3. 要求模型基于证据分析，而不是凭空判断；
4. 要求模型输出 JSON；
5. JSON 字段包括 llm_score、risk_level、reason、risk_points、keywords、suggestion；
6. 风险等级只能从以下四类中选择：可信新闻、存疑信息、疑似谣言、高风险谣言；
7. 不允许输出 Markdown 代码块，避免 JSON 解析困难；
8. 如果证据不足，应输出“存疑信息”或“疑似谣言”，不要强行判断真假。

请输出：
1. Prompt 模板文本；
2. 模板变量说明；
3. 在代码中如何调用；
4. 后续如何接入 Prompt 模板管理表。
```

## 五、本阶段开发提示词 3：实现规则评分服务

```text
请实现新闻风险规则评分服务。

本次任务只实现 rule_score，不调用 DeepSeek，不修改 RAG 检索。

要求：
1. 新建 services/rule_score_service.py；
2. 输入新闻标题、正文、source_name 可选字段、evidence_list；
3. 输出 rule_score，范围 0-100；
4. 同时输出命中的规则列表 hit_rules；
5. 规则包括：
   - 是否包含夸张词，如“震惊、疯传、惊天秘密、必看、紧急扩散”；
   - 是否缺少明确来源；
   - 是否包含强情绪化表达；
   - 是否包含绝对化表述，如“百分百、一定、所有人、绝对”；
   - 是否与知识库证据存在明显冲突；
6. 规则评分越高表示越可信，越低表示风险越高；
7. 代码要简单清晰，适合课程设计解释；
8. 不要做复杂机器学习算法。

完成后请给出：
1. 规则列表；
2. 扣分逻辑；
3. 示例输入输出；
4. 后续如何优化。
```

## 六、本阶段开发提示词 4：实现检测记录与证据匹配表

```text
请实现新闻检测记录和证据匹配记录的数据模型与 CRUD。

要求：
1. 创建 detection_records 表对应 Model；
2. 创建 evidence_matches 表对应 Model；
3. 创建对应 Pydantic Schema；
4. 检测记录字段至少包括：user_id、input_title、input_content、category、keywords、final_score、evidence_score、llm_score、rule_score、risk_level、judgement_result、reason、risk_points、suggestion、is_high_risk、report_url、created_at；
5. 证据匹配字段至少包括：detection_id、knowledge_id、title、summary、source_name、similarity_score、rank_order、created_at；
6. 实现检测记录保存函数；
7. 实现根据用户查询历史记录函数；
8. 实现根据 detection_id 查询详情函数；
9. 普通用户只能看自己的记录，管理员可以看全部记录。

完成后请说明：
1. 数据表关系；
2. 权限控制方式；
3. 如何测试保存和查询。
```

## 七、本阶段开发提示词 5：实现新闻检测主接口

```text
请实现新闻检测主接口 POST /api/detect/news。

检测流程必须按以下顺序执行：
1. 接收新闻标题和正文；
2. 校验标题和正文不能为空；
3. 清洗文本；
4. 调用关键词提取；
5. 调用 Chroma 检索 Top10 证据；
6. 取 Top5 证据构造 Prompt；
7. 调用 DeepSeek 进行可信度分析；
8. 调用规则评分服务；
9. 计算 evidence_score、llm_score、rule_score、final_score；
10. 根据 final_score 生成最终 risk_level；
11. 保存 detection_records；
12. 保存 evidence_matches；
13. 返回完整检测结果。

评分公式：
最终可信度 = 检索证据相关度评分 × 40% + 大模型判断评分 × 40% + 来源/风险规则评分 × 20%

返回字段必须包括：
- detection_id
- final_score
- evidence_score
- llm_score
- rule_score
- risk_level
- judgement_result
- reason
- risk_points
- keywords
- evidence_list
- similar_news
- suggestion
- agent_steps
- disclaimer

agent_steps 固定展示：
1. 关键词提取完成
2. 知识库证据检索完成
3. 大模型可信度分析完成
4. 风险规则评分完成
5. 检测结果生成完成

注意：
- 如果 DeepSeek 调用失败，系统应返回错误提示，不要假装检测成功；
- 如果 RAG 没有检索到证据，也应允许继续分析，但要在 reason 中说明证据不足；
- 不要在本次任务中实现 PDF 报告。

完成后请给出 Swagger 测试示例。
```

## 八、本阶段开发提示词 6：实现检测历史接口

```text
请实现新闻检测历史相关接口。

接口包括：
1. GET /api/detect/history：当前登录用户查看自己的检测历史；
2. GET /api/detect/{id}：查看单条检测详情；
3. GET /api/admin/detections：管理员查看全部检测记录；
4. GET /api/admin/detections/{id}：管理员查看任意检测详情；
5. DELETE /api/admin/detections/{id}：管理员删除异常检测记录。

要求：
- 普通用户不能查看其他用户记录；
- 管理员可以按 risk_level、keyword、date_range、user_id 筛选；
- 列表接口要支持分页；
- 详情接口要返回 evidence_matches；
- 不要实现前端页面。

完成后请说明权限规则和测试方法。
```

## 九、本阶段验收标准

```text
1. Swagger 可以调用 /api/detect/news；
2. 输入新闻后能返回完整 JSON 检测结果；
3. 检测过程能调用 RAG Top10；
4. 检测过程能调用 DeepSeek；
5. final_score 按公式计算；
6. risk_level 与分数区间一致；
7. 检测记录能保存到 MySQL；
8. 证据匹配记录能保存到 MySQL；
9. 普通用户只能查看自己的历史；
10. 管理员能查看所有检测记录。
```

## 十、代码审查提示词

```text
请作为代码审查员，检查第三阶段 DeepSeek 接入与新闻检测主流程代码。

重点检查：
1. DeepSeek API Key 是否硬编码；
2. 模型返回非 JSON 时是否会导致系统崩溃；
3. final_score 是否严格按公式计算；
4. risk_level 是否被大模型结果覆盖而不是根据 final_score 生成；
5. 检测记录是否完整保存；
6. 普通用户是否可能看到别人的检测历史；
7. RAG 检索失败时是否有合理处理；
8. DeepSeek 调用失败时是否明确返回失败；
9. 路由层是否过于臃肿；
10. 是否影响第一、第二阶段已有功能。

请输出审查报告，不要直接修改代码。
```
