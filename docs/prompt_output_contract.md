# Prompt 输出契约

`contracts/prompt_output_contract.json` 是新闻可信度分析 Prompt 输出结构的唯一机器可读契约源。

这份契约统一驱动：

- 后端默认 Prompt 和强制追加的输出契约渲染。
- 后端 LLM JSON 解析时的字段别名、必需字段、风险等级和证据仲裁校验。
- 前端风险等级标签、首页等级说明和筛选项。
- 契约相关单元测试。

## 演进规则

1. 新增、删除或重命名输出字段时，先修改 `contracts/prompt_output_contract.json`。
2. 语义兼容的文案或别名调整可以保持当前 `version`。
3. 影响模型输出结构、前后端字段解释或历史解析兼容性的变更必须升级 `version`。
4. 后端归一化字段可以比模型要求字段更多，例如 `evidence_quality.score` 由后端统一计算，不要求模型返回。
5. 不要在 Prompt、解析逻辑或前端组件里手写第二份风险等级/字段清单；需要展示时从 contract 派生。

## 当前版本

当前契约版本：`2.1`

顶层字段：

`llm_score`、`risk_level`、`reason`、`evidence_quality`、`evidence_arbitration`、`similar_news`、`risk_points`、`keywords`、`suggestion`

风险等级：

`可信新闻`、`存疑信息`、`疑似谣言`、`高风险谣言`
