# 新闻页面识别与链接提取优化方案

## 目标

链接识别采用“先识别页面类型，再选择抽取策略，再返回可恢复状态”的流程，避免把动态渲染、登录墙、反爬校验和普通静态新闻混成同一种失败。

## 主流方法参考

- 结构化数据优先：新闻页常使用 `Article`、`NewsArticle`、`BlogPosting` 结构化数据。Google Search Central 建议用这些类型描述新闻、博客和体育文章，并使用 `headline`、`datePublished` 等属性；Schema.org 也定义了 `NewsArticle` 为报道新闻或提供背景材料的文章类型。
- Reader/Readability 思路：Mozilla Readability 的核心方式是基于 DOM 文档解析主正文，并提供 `isProbablyReaderable` 作为是否值得进入正文解析的前置判断。
- 多策略抽取：Trafilatura 的文档说明其正文抽取会尝试脚本/属性中的 JSON、`article` 标签、正文段落、描述字段和整页文本等多种来源。
- 浏览器渲染兜底：Playwright 支持等待 `load`、`domcontentloaded` 等页面状态；它也提示 `networkidle` 不推荐作为测试就绪条件。当前项目暂不引入浏览器运行时，先把这类页面识别为 `dynamic_render_required`。

参考来源：

- https://developers.google.com/search/docs/appearance/structured-data/article
- https://schema.org/NewsArticle
- https://github.com/mozilla/readability
- https://trafilatura.readthedocs.io/en/latest/corefunctions.html
- https://playwright.dev/python/docs/api/class-page#page-wait-for-load-state

## 页面类型模型

`PageRecognizer` 输出统一识别结果：

| 字段 | 含义 |
| --- | --- |
| `status` | `ok`、`login_required`、`blocked_by_anti_bot`、`dynamic_render_required` |
| `page_type` | `static_article`、`structured_article`、`login_wall`、`anti_bot_wall`、`client_rendered_shell`、`unknown` |
| `recommended_method` | `html`、`structured_data`、`authenticated_retry`、`manual_input`、`browser_render` |
| `confidence` | 页面识别置信度，范围 0-1 |
| `signals` | 命中的识别信号，如 `json_ld_present`、`password_form`、`client_render_marker` |
| `recovery_action` | 前端恢复动作：无、登录后重试、手动输入 |
| `login_url` | 登录墙场景下可跳转的登录地址 |

## 策略顺序

1. 登录墙识别：短正文 + 登录提示、密码表单或登录标题，返回 `login_required`，前端提示打开登录页并登录后再获取。
2. 反爬/校验识别：短正文 + Cloudflare、人机验证、验证码、访问过频等信号，返回 `blocked_by_anti_bot`，引导用户手动输入正文。
3. 结构化正文识别：如果正文来自 JSON-LD、`__NEXT_DATA__` 或脚本内结构化数据，优先判为 `structured_article`。
4. 动态渲染壳页识别：HTML 只有 `#root`、`#__next`、脚本和启用 JavaScript 提示，且没有结构化正文时，返回 `dynamic_render_required`。
5. 静态新闻识别：有 `article`、`main`、多段落和足够正文长度时，判为 `static_article`。
6. 未知页面：保留 `unknown`，由原有标题/正文校验决定是否返回普通提取失败。

## 当前实现范围

- 已新增 `backend/app/services/web/page_recognizer.py`，把页面识别从抓取器中拆出。
- `WebContentFetcher.fetch_article()` 已接入识别结果，成功响应增加 `page_type`、`recognition_confidence`、`recognition_signals`、`recommended_extraction_method`。
- 可恢复失败统一返回机器可读状态，登录墙保持 `open_login_then_retry`。
- 暂不自动绕过登录墙和反爬；不复用用户登录态，不存 Cookie，不模拟验证码。

## 后续扩展

浏览器渲染服务可以作为独立策略接在 `recommended_method == "browser_render"` 后面。建议放在独立 worker 中，设置域名安全校验、资源大小上限、超时、并发限制、无持久 Cookie 上下文和审计日志，避免 URL 抓取能力扩大为 SSRF 或资源消耗风险。
