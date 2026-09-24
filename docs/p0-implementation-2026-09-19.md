# P0 实施与验收记录

日期：2026-09-19。对应《项目代码审计与求职定位》第10节的六项P0。

本次完成代码改造和本机可执行验证。**P0-3至P0-6达到本轮验收目标；P0-1尚缺真正的干净Git checkout / Docker运行验收，P0-2尚缺项目四级风险与应用片段相关性的真人独立复核。** 不把待办写成已验证能力。

## 1. 逐项交付

| 项目 | 本次实现 | 验证与边界 |
|---|---|---|
| P0-1 干净环境可复现 | Docker构建上下文改为仓库根，backend/worker/frontend包含共享contracts；补入API实际依赖的evaluation.ai_engineering；补测试依赖、worker健康检查、先迁移再启动、镜像与日志CI；提供独立目录复现及源码指纹脚本 | 新虚拟环境安装依赖，pip check通过；无.env/旧node_modules的目录中API/worker导入、契约读取、npm ci、生产构建、真实API /health及/ready通过。当前工作区仍含未提交实现；未执行远端CI或本机Docker，不能称干净checkout/容器已通过 |
| P0-2 无泄漏真实Benchmark | 隔离旧80条泄漏样本；冻结120条官方CFEVER原始主张、上游标签和页证据；共享证据页连通分组、固定split及SHA；数据质量/人工评审门禁；实际执行标题检索基线并保存逐例失败分析 | 82/22/16划分；474个页标题的独立封闭词项基线可复现。官方三分类有上游人工标签；项目四级gold及两人review字段没有伪造。应用知识/片段相关性与四级风险真人评审仍待补，端到端RAG/LLM质量未验收 |
| P0-3 RAG证据与分数一致 | raw_cosine_score、fusion_score、rerank_score分离；联网路由使用真实cosine；合并保留chunks/spans/query/version；v2写父记录指纹，读取批量校验父记录存在、同步状态、版本、过滤条件；阻止hybrid回退重新引入旧v2 | RAG定向109项通过，包含真实临时关系数据库+模拟向量I/O的删除、更新、待同步、旧索引和v2+web组合。完整后端测试还执行了真实Chroma增查删。旧v2索引需重建 |
| P0-4 降级语义可信 | 独立assessment_status/reason与nullable final_score；provider失败、非法模型分数、仲裁耗尽、无有效证据/仅中性背景均不出综合分；前端、数据库、报告、trace、审计与评测传播一致 | 明确completed / insufficient_evidence / degraded / legacy。API仍可200表示请求处理完成，但业务状态与日志不再冒充完整分析；弃权不标高风险。历史迁移和旧缓存兼容已测 |
| P0-5 报告提交边界 | 移除commit后清理边界内的refresh；提交前失败清理新文件，提交结果不确定保留文件，成功后才清理旧文件；缓存报告携带分析状态标记，禁止下载与弃权状态冲突的旧评分报告 | 注入提交成功后确认丢失、refresh不可用、flush失败、PDF转换失败及重生成，验证数据库引用与文件存在性。提交不确定可能留下待核对孤儿文件，未宣称分布式事务 |
| P0-6 关键组合回归 | 新增真实状态图→模型解析/校验→Pydantic→临时SQLite→详情/报告组合；覆盖本地命中、v2联网、仲裁修复/耗尽、provider失败、无证据、非法分数、报告替换与API审计 | 新P0组合/状态/迁移三个模块20项通过，已包含在后端565项内。保存请求、模型fixture生成的响应、Prompt、持久化详情与报告状态；无证据报告使用真实PDF转换器，其他故障用例按边界注入故障 |

## 2. 最终执行结果

| 验证 | 实际结果 | 本机证据 |
|---|---|---|
| 完整后端 unittest discover | **565 tests，OK，41.212s**；无skip | `.artifacts/p0/backend-tests-final.log` |
| 按CI的隔离环境重跑后端 | 同一套**565 tests，OK，39.778s**；不重复计数 | `.artifacts/p0/backend-ci-environment.log` |
| 完整评测 pytest | **146 passed，11.52s**；4项历史实验fixture引起的sklearn类别warning | `.artifacts/p0/evaluation-tests-final.log` |
| 前端 node --test | **26 passed，0 failed，0 skipped** | `.artifacts/p0/frontend-tests-final.log` |
| P0组合/状态/迁移定向验证 | **20 tests，OK，10.292s**；是565项的子集，不能重复相加 | `.artifacts/p0/pipeline-tests-final.log` |
| 独立目录API导入、契约、npm ci、Vite build及HTTP启动 | **退出码0**；最后两行UI修改后，重新在全新前端目录执行安装、26项测试及生产构建；后端快照和最新前端共225个源文件匹配 | `.artifacts/p0/build-verification.json`、`.artifacts/p0/clean-package-final.log`、`.artifacts/p0/clean-package-final-ui/` |
| 真实Chroma临时库upsert/search/delete | 通过，已纳入最终完整后端 | `.artifacts/p0/chroma-windows-runtime.json` |
| Docker镜像构建、Compose服务运行、MySQL实际迁移 | **本机未运行**；相关检查已写入CI | `.github/workflows/ci.yml` |
| 四级风险真人双人复核与端到端模型效果 | **未完成，默认发布门禁拒绝** | `evaluation/datasets/human_review_pending.csv` |

环境：Python 3.12.14，Node 24.19.0，npm 11.5.2；Python完整安装版本存于`.artifacts/p0/installed-packages.txt`。Windows新环境一度缺MSVCP140.dll；仅在虚拟环境的Chroma绑定旁补入机器已有、Microsoft有效签名的运行库后通过，未改系统目录或降级Chroma。重建Windows环境需要兼容MSVC运行库，DLL没有加入仓库。

测试使用临时SQLite、hash embedding及外部模型/联网transport fixtures，避免读开发者.env和访问现有业务数据。**hash embedding测试通过不代表语义召回质量；fixture集成不是实际供应商端到端准确率。** 本机未调用付费LLM/Embedding或搜索服务。

测试发生于分支`evaluation/real-metrics`，基础HEAD为`0a2a0f464af3fc335e647926913a1f573ff30b09`。工作区已有改动及未跟踪文件，本次未代为提交；基础HEAD不包含全部被测代码。当前选定371个运行、测试、评测和构建文件的指纹为：

`41612e83eed936fcc720ef6f4c9ee856d58a45b181223f61e8b7a8acd2086a84`

逐文件SHA-256见`.artifacts/p0/source-manifest.json`，可用`scripts/ci/write_source_manifest.py`重建。CI也会上传源码指纹、后端测试日志及组合场景文件。`.artifacts/`是本机输出目录，未加入Git；可复现脚本、测试和正式基线位于项目源码中。

## 3. 关键行为约定

| 状态 | 综合分 | 风险显示 | 业务含义 |
|---|---|---|---|
| completed | 0至100的数值 | 四级风险 | 主分析、仲裁和质量校验完成，存在非中性、正相关性/质量的有效证据且coverage>0 |
| insufficient_evidence | null | 无法判断 | 无有效证据、coverage=0或只有中性背景 |
| degraded | null | 无法判断 | 模型服务失败、输出无效、校验/修复未完整完成 |
| legacy | 保留历史字段 | 兼容历史结果 | 缺少足够历史诊断，不能宣称经过新版完整校验 |

只有completed使用`0.5 × llm_score + 0.3 × evidence_quality_score + 0.2 × rule_score`。诊断分可以保留用于排查，但不会替代综合分。模型原始分数必须为有限JSON数值且位于0至100，布尔、数值字符串、NaN、无穷和越界值不能通过归一化伪装成合法结果。

历史数据迁移根据已保存仲裁/质量状态、证据关系和coverage保守回填；可确认的弃权清空综合分、取消公开/高风险标记。已有NULL综合分时，downgrade明确拒绝恢复NOT NULL，避免凭空填分。

cosine是相似度，不是事实正确概率。RRF、规则重排和cosine阈值尚未通过本项目真实语义检索基准校准。父记录校验保证证据与本次数据库读取一致，不提供跨MySQL/Chroma的线性一致性。

## 4. 代码入口

- 构建：`backend/Dockerfile`、`frontend/Dockerfile`、`.dockerignore`、`docker-compose.yml`、`.github/workflows/ci.yml`、`scripts/ci/check_clean_package.py`。
- 数据门禁：`evaluation/dataset_quality.py`、`evaluation/run_evaluation.py`、`evaluation/metrics.py`、`evaluation/run_title_retrieval_baseline.py`。
- RAG：`backend/app/services/rag/contracts.py`、`retrieval.py`、`vector_index.py`、`fusion.py`、`backend/app/services/web/web_search_service.py`；详细决策见[ADR-002](decisions/ADR-002-rag-evidence-integrity.md)。
- 弃权：`backend/app/core/assessment.py`、`backend/app/services/detection_service.py`、`llm_service.py`、`detection_detail_service.py`、`backend/app/schemas/detection.py`、`frontend/src/utils/assessmentState.js`。
- 报告：`backend/app/crud/report_crud.py`、`backend/app/services/report_service.py`、`backend/app/templates/reports/detection_report.html`。
- 回归：`backend/tests/test_p0_pipeline_regressions.py`、`test_assessment_migration.py`、`test_assessment_state.py`、`test_rag_evidence_integrity.py`；前端`assessmentState.test.js`。

## 5. 部署到已有数据前

1. 在目标环境备份数据库、报告目录和Chroma；本次没有改动现有业务数据库或索引。
2. 部署新代码前，在相同目标配置下从`backend/`执行`python -m app.db.migrate`，升级到`0012_detection_assessment`。本轮对新迁移做了真实SQLite操作测试，MySQL部署验收仍需目标环境/CI执行。
3. 对旧v2索引，通过管理员知识库“重建索引”或分批vectorize更新`parent_revision`；旧索引不会自动删除，但不再作为可信dense证据返回。等待任务synced，再查看RAG audit。抽样audit不能宣称全库一致。
4. 旧评分报告与当前弃权状态冲突时，下载会要求重新生成；新报告显示“无法判断”，不显示综合数值。
5. 将本次需交付的源码、已有图/trace实现、测试、contracts及配置一并纳入受审阅提交，然后在干净checkout执行CI。当前未提交工作区的成功不能替代此项。

## 6. 最短复现方法

在不含真实密钥的测试环境中安装：`python -m pip install -r backend/requirements-test.txt`。从根目录设置`PYTHON_DOTENV_DISABLED=1`、`DATABASE_URL=sqlite:///:memory:`、测试用`SECRET_KEY`、`EMBEDDING_PROVIDER=hash`、`REDIS_ENABLED=false`、`CRAWL_ENABLED=false`、`KNOWLEDGE_INDEX_JOB_ENABLED=false`；这些是测试配置，不要用于生产。

```text
python -m unittest discover -s backend/tests -t backend -p "test_*.py"
python -m pytest evaluation/tests -q
npm --prefix frontend ci
npm --prefix frontend test
npm --prefix frontend run build
python -m evaluation.run_title_retrieval_baseline
python scripts/ci/write_source_manifest.py --output .artifacts/p0/source-manifest.json
```

设置`P0_ARTIFACT_DIR`为输出目录后，P0回归会保存场景请求、响应、持久化详情及脱离真实业务的fixture Prompt。`no-evidence.report.pdf`是真实转换器生成的示例报告。仓库内不保存真实用户Prompt或密钥。

独立目录打包复现：`python scripts/ci/check_clean_package.py --output-dir <全新目录> --node <node路径> --npm-cli <npm-cli.js路径>`；脚本拒绝复用旧目录，执行复制、导入、npm ci/build和API启动后停止测试进程。它补充而不替代Docker验证。

## 7. 评测能够和不能够证明的内容

官方CFEVER子集是百科事实核验主张，不是自然新闻分布。独立标题基线的test有16条，其中15条具备官方相关页；在474标题封闭语料上Hit@10和Recall@10为0.9333，MRR为0.8。原始结果见`evaluation/baselines/cfever-title-v1/`，这些数字**不能写成生产RAG召回率或LLM准确率**。

要完成P0-2严格验收，还需两名真人独立检查项目四级标签及应用知识/片段相关性，仲裁分歧、冻结新数据版本，再运行真实Embedding/知识库/LLM评测。现有发布门禁会阻止未合格gold计算正式分类指标；research-only也不能绕过已检测出的输入泄漏。评测脚本无法证明填表人的真实身份，不能替代人工流程。
