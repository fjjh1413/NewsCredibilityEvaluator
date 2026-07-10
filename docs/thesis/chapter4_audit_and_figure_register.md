# 第4章项目核查、图表与边界检查报告

## 一、项目事实核查结果

- 实际架构：Vue 3/Vite浏览器前端，FastAPI后端，MySQL业务数据库，Chroma向量索引，HTML/PDF报告目录；外部调用包括DeepSeek、DashScope Embedding、博查搜索和新闻网页。
- 后端分层：`app/api`、`app/schemas`、`app/services`、`app/crud`、`app/models`及`app/core`，另有`app/services/web`承载搜索、抓取和采集逻辑。
- 真实功能模块：认证与个人中心、新闻可信度评估、检测记录与报告、知识库与定时采集、管理员业务管理、统计与日志。
- 真实关系表：`users`、`knowledge_items`、`detection_records`、`evidence_matches`、`prompt_templates`、`reports`、`system_logs`、`crawl_tasks`。
- Chroma事实：集合名`knowledge_items`，余弦空间；文档ID为`knowledge:<id>`；正式配置为DashScope `text-embedding-v4`、1024维；Chroma元数据不存`vector_sync_status`，检索后由MySQL回查补充。
- 评分事实：证据质量分为`0.6×覆盖度+0.4×一致性`；有有效证据时为`0.5×LLM分+0.3×证据质量分+0.2×规则分`；无有效证据时为`0.6×LLM分+0.4×规则分`；模型失败时仅取规则分。
- 风险阈值：`[80,100]`可信新闻，`[60,80)`存疑信息，`[40,60)`疑似谣言，`[0,40)`高风险谣言。
- 联网补充事实：仅在用户启用且系统开关允许时判断；无本地证据、Top-1低于0.45，或Top-1低于0.60且相似度不低于0.30的候选少于3条时触发。
- 权限事实：游客可检测和查看公开高风险信息；登录用户可访问个人历史、详情、重评、RAG与报告；管理员接口统一使用管理员依赖。`crawl_tasks`没有前端页面，也没有REST接口。
- 一致性事实：知识新增失败标记`failed`；更新采用MySQL暂不提交与向量失败回滚；删除先删向量，MySQL失败后恢复向量并标记`delete_failed`；支持单条向量化与全量重建。该机制不是分布式事务。

## 二、图表设计登记表

| 图号 | 图名 | 对应章节 | 主要事实来源 | 关键内容 | 工具与输出 |
|---|---|---|---|---|---|
| 图4-1 | 系统总体架构图 | 4.2.1 | main、router、services、config | 系统边界、前后端、数据与外部服务 | Graphviz；同名DOT/SVG/EMF/PNG |
| 图4-2 | 后端分层架构图 | 4.2.3 | backend/app目录 | API、Schema、Service、CRUD、Model、Core | Graphviz；同名DOT/SVG/EMF/PNG |
| 图4-3 | 系统功能模块图 | 4.3 | 前后端路由与服务 | 六个真实功能模块 | Graphviz；同名DOT/SVG/EMF/PNG |
| 图4-4 | 新闻可信度评估总体流程图 | 4.4 | detection_service | 输入、检索、仲裁、评分、保存及降级 | Graphviz；同名DOT/SVG/EMF/PNG |
| 图4-5 | 本地检索与联网补充流程图 | 4.4.2—4.4.4 | chroma_service、web_search_service | Top-10、触发阈值、合并与来源中立顺序 | Graphviz；同名DOT/SVG/EMF/PNG |
| 图4-6 | 可信度评分与风险分级流程图 | 4.4.5—4.4.6 | detection_service、risk_level | 三种分支公式与四级阈值 | Graphviz；同名DOT/SVG/EMF/PNG |
| 图4-7 | 数据库ER图 | 4.5.2 | SQLAlchemy模型与迁移 | 八张真实表、主外键与基数 | Graphviz；同名DOT/SVG/EMF/PNG |
| 图4-8 | MySQL与Chroma协同关系图 | 4.5.4—4.5.5 | knowledge_service、chroma_service | 向量派生、回查与补偿边界 | Graphviz；同名DOT/SVG/EMF/PNG |
| 图4-9 | 用户端页面结构图 | 4.8.1 | Vue Router | 公开、guestOnly和登录路由 | Graphviz；同名DOT/SVG/EMF/PNG |
| 图4-10 | 管理员端页面结构图 | 4.8.2 | Vue Router | 九个真实管理页面 | Graphviz；同名DOT/SVG/EMF/PNG |

图形统一使用白底、深灰线、浅灰填充和一种低饱和蓝色，引用SimSun字体；无渐变、阴影和装饰图标。SVG为正式矢量文件，DOT为可编辑源文件，EMF用于Word矢量插入，PNG仅用于视觉复核。

## 三、正文与图表一致性检查

- 4.2中的架构节点均可由前后端目录、配置或服务代码证明；未加入消息队列、缓存集群或不存在的微服务。
- 图4-4、图4-5和图4-6前后衔接：候选证据池进入证据仲裁，有效证据决定评分分支，外部服务异常进入明确降级路径。
- 图4-7表名、主键、外键、可空关系和一对一/一对多关系与SQLAlchemy模型一致。
- 图4-8只描述已实现的应用层补偿，并明确不是MySQL与Chroma的分布式事务。
- 图4-9和图4-10与`frontend/src/router/index.js`一致；未虚构采集任务页面。
- 表4-1至表4-5分别覆盖角色权限、功能模块、核心数据表、接口分类及安全可靠性，均按三线表要求在Word中排版。

## 四、章节边界检查

- 与第3章：不重复解释框架版本、安装步骤和一般技术优点，只说明已选技术在系统中的职责与协作。
- 与第5章：不粘贴函数代码、完整Prompt或完整JSON，只保留总体流程、字段契约和设计公式。
- 与第6章：不写测试数量、通过率、性能结果或结论，只描述设计目标和异常路径。

## 五、待人工确认事项

- 当前代码与本机配置可以证明正式Embedding为DashScope，但部署到其他环境时仍需确认`.env`未切换到演示用`hash`或其他适配器。
- `crawl_tasks`已存在模型和调度写入逻辑，但没有前端页面/API；若后续项目新增入口，应同步更新图4-10、表4-4和4.3.4。
- 旧章节若仍写固定公式`0.4×检索证据分+0.4×LLM分+0.2×规则分`，与当前主流程不一致，应以本章分支式公式为准并在全文统一修订。
- 游客结果页可以展示当次返回数据，但持久化详情与报告接口要求登录；最终答辩演示应按这一权限边界说明。

## 六、文件变更清单

- 新增`docs/thesis/chapter4_system_design.md`。
- 新增`docs/thesis/chapter4_audit_and_figure_register.md`。
- 新增`docs/thesis/figures/chapter4/`下10组DOT、SVG、EMF和PNG文件。
- 新增`scripts/generate_chapter4_figures.py`，可重复生成全部图形。
- 最终Word文档由第3章规范修订版复制并插入本章，不覆盖用户原文件。
