from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Iterable

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt


ROOT = Path(__file__).resolve().parents[2]
SOURCE_DOCX = Path(os.environ.get("CHAPTER5_SOURCE_DOCX", ROOT / ".artifacts" / "docs" / "智闻辨真_第二章需求分析优化版.docx"))
OUT_ROOT = ROOT / ".artifacts" / "docs" / "chapter5"
FIG_DIR = OUT_ROOT / "chapter5_figures"
OUT_DOCX = OUT_ROOT / "智闻辨真_第五章系统详细设计与实现完成版.docx"
NOTE_MD = OUT_ROOT / "第五章撰写说明.md"
RUN_JSON = OUT_ROOT / "chapter5_run.json"

BODY_SIZE = Pt(10.5)
CODE_SIZE = Pt(9)


class Writer:
    def __init__(self, doc: Document, ref_paragraph):
        self.doc = doc
        self.ref = ref_paragraph
        self.paragraph_count = 0
        self.table_count = 0
        self.figure_count = 0
        self.screenshot_count = 0
        self.code_count = 0

    def _font_run(self, run, size=BODY_SIZE, east_asia="宋体", latin="Times New Roman"):
        run.font.size = size
        run.font.name = latin
        run._element.rPr.rFonts.set(qn("w:eastAsia"), east_asia)

    def paragraph(self, text: str = "", style: str | None = None, align=None):
        p = self.ref.insert_paragraph_before(text, style=style)
        if align is not None:
            p.alignment = align
        for run in p.runs:
            self._font_run(run)
        self.paragraph_count += 1
        return p

    def heading(self, text: str, level: int):
        style = f"Heading {level}"
        try:
            p = self.paragraph(text, style=style)
        except KeyError:
            p = self.paragraph(text)
            p.style = self.doc.styles["Normal"]
        return p

    def code(self, title: str, lines: str):
        self.paragraph(title, align=WD_ALIGN_PARAGRAPH.CENTER)
        for raw in lines.strip("\n").splitlines():
            p = self.paragraph(raw)
            p.paragraph_format.left_indent = Inches(0.25)
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            for run in p.runs:
                self._font_run(run, size=CODE_SIZE, east_asia="Consolas", latin="Consolas")
        self.code_count += 1

    def formula(self, formula: str, number: str):
        p = self.paragraph(f"{formula}                                      {number}", align=WD_ALIGN_PARAGRAPH.CENTER)
        for run in p.runs:
            self._font_run(run, east_asia="Cambria Math", latin="Cambria Math")

    def table(self, caption: str, headers: list[str], rows: Iterable[Iterable[str]]):
        self.paragraph(caption, align=WD_ALIGN_PARAGRAPH.CENTER)
        table = self.doc.add_table(rows=1, cols=len(headers))
        try:
            table.style = "Table Grid"
        except KeyError:
            table.style = self.doc.styles["Normal Table"]
        for i, header in enumerate(headers):
            table.rows[0].cells[i].text = header
        for row in rows:
            cells = table.add_row().cells
            for i, value in enumerate(row):
                cells[i].text = str(value)
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    for run in p.runs:
                        self._font_run(run)
        self.ref._p.addprevious(table._element)
        self.table_count += 1
        return table

    def figure(self, image_name: str, caption: str, screenshot: bool = False, width: float = 5.9):
        path = FIG_DIR / image_name
        p = self.ref.insert_paragraph_before()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run()
        run.add_picture(str(path), width=Inches(width))
        self.paragraph(caption, align=WD_ALIGN_PARAGRAPH.CENTER)
        self.figure_count += 1
        if screenshot:
            self.screenshot_count += 1


def set_default_styles(doc: Document) -> None:
    for style_name in ("Normal", "Normal (Web)"):
        if style_name in [s.name for s in doc.styles]:
            style = doc.styles[style_name]
            style.font.name = "Times New Roman"
            style._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
            style.font.size = BODY_SIZE


def find_reference_paragraph(doc: Document):
    for p in reversed(doc.paragraphs):
        if p.text.strip().startswith("参考文献"):
            return p
    return doc.add_paragraph()


def add_core_content(w: Writer) -> None:
    w.heading("第5章 系统详细设计与实现", 1)
    w.paragraph("本章在前四章需求、技术选型和总体架构的基础上，对智闻辨真系统的核心实现进行说明。撰写过程以当前项目代码、配置、数据库模型、迁移、接口、测试和真实运行页面为事实来源，重点描述新闻输入、RAG证据检索、联网补充、候选证据组织、大语言模型证据仲裁、分支式评分、持久化以及异常降级之间的完整调用链。")
    w.paragraph("需要说明的是，本章讨论的是系统功能和工程实现是否落地，不给出准确率、召回率、F1值、压力测试或模型对比结论；这些内容属于后续系统测试与实验分析章节。")

    w.heading("5.1 系统实现概述", 2)
    w.heading("5.1.1 项目代码组织", 3)
    w.paragraph("后端采用FastAPI、SQLAlchemy、Alembic和服务层编排结构，前端采用Vue3、Pinia、Vue Router、Element Plus和Axios。与第五章实现直接相关的目录如下：")
    w.code("代码5-1 项目主要目录职责", r"""
backend/app/
├── api/        接口路由、权限依赖和后台接口
├── models/     MySQL ORM模型
├── schemas/    Pydantic请求、响应和契约结构
├── crud/       数据访问与持久化封装
├── services/   检测、RAG、LLM、报告和外部服务编排
├── core/       配置、安全、JWT、依赖注入和限流
└── templates/  PDF报告HTML模板

frontend/src/
├── api/        前端接口封装
├── views/      检测、结果、历史、后台等页面
├── components/ 证据、评分、状态等复用组件
├── stores/     登录用户和全局状态
└── router/     页面路由与权限守卫
""")

    w.heading("5.1.2 核心业务调用链", 3)
    w.paragraph("新闻可信度评估入口位于前端DetectView页面和后端`POST /api/detect/news`接口。接口进入`detect_news_credibility`服务后，先完成文本清洗和关键词抽取，再调用知识库语义检索；当本地证据不足且用户允许联网时调用Bocha搜索进行补充。候选证据统一后交给DeepSeek兼容接口生成结构化判断，服务端再执行证据仲裁契约校验、证据质量重算、规则评分和分支式综合评分，最后将检测记录、有效证据和分析过程数据写入MySQL。图5-1展示了该调用链。")
    w.figure("fig5-1-call-chain.png", "图5-1 新闻可信度评估核心实现调用链", width=6.2)

    w.heading("5.1.3 设计与实现映射", 3)
    w.paragraph("第4章给出了总体架构和方法流程，第5章将其落到具体模块、数据表和页面状态上。表5-1列出核心设计点和实现载体。")
    w.table(
        "表5-1 设计与实现映射",
        ["第4章设计内容", "第5章实现位置", "主要实现载体", "关键状态或数据"],
        [
            ["URL提取", "5.3", "WebContentFetcher、ExtractPreviewRequest、DetectView", "title、content、source_url、publish_time_precision"],
            ["本地语义检索", "5.4", "knowledge_service、chroma_service", "knowledge_id、similarity_score、Top-10"],
            ["联网证据补充", "5.5", "web_search_service、BochaClient", "web_search_enabled、web候选、source_type"],
            ["候选证据组织", "5.5", "merge_evidence、_ensure_candidate_ids", "candidate_id、source_type、rank_order"],
            ["模型证据仲裁", "5.6", "llm_service、validate_and_apply_llm_ranking", "ranked_evidence、rejected_evidence"],
            ["契约校验", "5.6", "detection_service", "arbitration_status、quality_status、analysis_contract_version"],
            ["分支评分", "5.7", "detection_service、rule_score_service", "S_L、S_E、S_R、final_score"],
            ["结果持久化", "5.8", "DetectionRecord、EvidenceMatch", "analysis_payload、risk_level、review_status"],
            ["跨存储恢复", "5.9", "knowledge_service、AdminKnowledgeView", "vector_sync_status、vector_sync_error"],
            ["报告生成", "5.10", "report_service、Report模型、ResultView", "pdf_path、report_url、download_url"],
        ],
    )

    w.heading("5.2 用户认证与权限控制实现", 2)
    w.heading("5.2.1 用户注册与密码安全", 3)
    w.paragraph("注册接口位于`api/v1/auth.py`，请求进入服务层前由Pydantic校验用户名、邮箱和密码字段。`AuthService.register`会分别检查用户名和邮箱是否已存在，重复时返回明确错误；创建用户时将密码交给`passlib`的bcrypt上下文生成哈希值，数据库只保存`password_hash`，不会保存明文密码。注册和登录接口还通过内存限流器限制同一IP在窗口期内的频繁请求。")
    w.heading("5.2.2 登录认证与JWT令牌", 3)
    w.paragraph("登录时服务端根据用户名查找用户、校验bcrypt哈希并确认账号状态为`active`，随后使用`create_access_token`生成包含`sub`、`exp`和角色信息的JWT。前端登录成功后将令牌保存到`localStorage`，Axios请求拦截器自动写入`Authorization: Bearer`头；后端`get_current_user`依赖负责解析令牌、查库加载用户并处理过期、伪造或用户不存在等情况。")
    w.heading("5.2.3 角色权限与资源归属校验", 3)
    w.paragraph("系统区分普通用户、管理员和游客。游客可提交检测或URL预览，但不能查询历史和下载报告；普通用户只能读取本人检测记录；管理员可进入后台知识库、Prompt、高风险复核、统计和日志页面。历史记录、检测详情和报告下载均进行资源归属校验，其中报告下载还会校验PDF路径必须位于配置的报告根目录内。")
    w.code("代码5-2 当前用户加载与管理员权限依赖", r"""
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    payload = decode_token(token)
    user_id = payload.get("sub") if payload else None
    if not user_id:
        raise HTTPException(status_code=401, detail="invalid token")
    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None or user.status != "active":
        raise HTTPException(status_code=401, detail="inactive or missing user")
    return user

def get_current_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="admin required")
    return current_user
""")

    w.heading("5.3 新闻输入与网页内容提取实现", 2)
    w.heading("5.3.1 手工新闻输入与参数校验", 3)
    w.paragraph("手工检测请求由`DetectNewsRequest`承载。标题最长255字符，业务校验要求清洗后不少于4个字符；正文至少20个字符，后端进入服务层后将正文清洗并限制到12000字符，前端表单同时以5000字符作为输入提示上限。类别、来源名称、来源URL、发布时间和是否启用联网搜索为可选字段，空字符串会被转换为`None`，避免将无效空值写入数据库。")
    w.paragraph("Pydantic负责字段类型、长度和空白文本校验，`detect_news_credibility`负责语义层的文本清洗、关键词抽取和后续检测编排。前端DetectView通过Element Plus表单规则给出即时提示，后端错误则通过统一响应中的`message`显示在页面。")
    w.heading("5.3.2 新闻URL内容提取", 3)
    w.paragraph("URL提取采用“预览—确认—检测”两阶段。用户在DetectView粘贴链接后，前端调用`POST /api/detect/extract-preview`；后端只抓取网页并返回标题、正文、来源、URL和发布时间，不创建检测记录。用户可以在页面回填结果基础上继续修改，确认后再提交`/api/detect/news`进入完整检测链路。真实运行时的URL提取回填状态见图5-7。")
    w.heading("5.3.3 发布时间与来源信息规范化", 3)
    w.paragraph("网页解析服务会优先从Open Graph、Twitter Card、JSON-LD、`time`标签和正文附近的时间表达中提取发布时间，并区分`date`与`datetime`两种精度。响应模型要求日期格式为`YYYY-MM-DD`，日期时间格式可由`datetime.fromisoformat`解析；无法识别时返回空值并允许用户手工填写。来源名称默认取网页元信息或最终URL主机名，`source_url`使用安全校验后的最终访问地址。")
    w.heading("5.3.4 SSRF防护与请求限制", 3)
    w.paragraph("URL抓取属于直接访问外部地址的高风险入口，因此`WebContentFetcher`先执行协议白名单和主机校验，再进行DNS解析。实现拒绝本机、私有、链路本地和保留网段地址；每次重定向后都会重新校验目标主机，最多允许3次重定向。HTTP请求超时为10秒，读取体上限为2MB，内容类型限定为HTML、XHTML或纯文本。异常统一返回422，不写入检测记录。图5-2给出了时序。")
    w.figure("fig5-2-url-ssrf.png", "图5-2 新闻URL提取与安全校验时序图", width=5.8)
    w.code("代码5-3 URL协议、地址和重定向安全校验", r"""
ALLOWED_SCHEMES = {"http", "https"}
FETCH_TIMEOUT = 10.0
MAX_FETCH_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 3

def _normalise_url(url):
    parsed = urlparse(url.strip())
    if parsed.scheme not in ALLOWED_SCHEMES or not parsed.hostname:
        raise SSRFBlockedError("unsupported or missing host")
    return urlunparse(parsed._replace(fragment=""))

for hop in range(MAX_REDIRECTS + 1):
    self._assert_safe_url(current_url)
    response = opener.open(current_url, timeout=self._timeout)
    if response.status in REDIRECT_STATUS:
        current_url = urljoin(current_url, response.headers["Location"])
        continue
""")

    w.heading("5.4 新闻知识库与本地语义检索实现", 2)
    w.heading("5.4.1 知识文本组织与向量化", 3)
    w.paragraph("知识条目由`KnowledgeItem`模型保存，Embedding文本不是单独使用正文，而是将标题、正文、类别、摘要、关键词、真实性标签和辟谣说明按标签拼接，最大长度限制为8000字符。当前配置使用DashScope兼容接口，模型为`text-embedding-v4`，维度为1024；项目也保留`hash` provider作为本地演示兜底，但正式RAG检索以DashScope语义向量为准。")
    w.heading("5.4.2 Chroma向量写入与Top-K检索", 3)
    w.paragraph("Chroma集合名为`knowledge_items`，元数据指定`hnsw:space=cosine`。知识向量ID采用`knowledge:<id>`，向量元数据包含知识库ID、标题、类别、真实性标签、来源和风险等级。检测时查询文本由新闻标题和正文构成，`RAG_TOP_K=10`，Chroma返回距离后由服务端转换为`max(0,1-distance)`形式的相似度。图5-3展示了本地检索和业务回查过程。")
    w.figure("fig5-3-local-rag.png", "图5-3 本地语义检索与业务数据回查流程", width=5.8)
    w.heading("5.4.3 检索结果业务数据回查", 3)
    w.paragraph("向量库只作为召回索引，不作为业务事实源。`search_similar_knowledge`从Chroma结果的metadata读取`knowledge_id`后回查MySQL；若数据库记录不存在则跳过该向量，若存在则使用MySQL中的当前标题、摘要、分类、真实性标签、来源和同步状态覆盖向量库元数据。这样可以避免旧向量元数据直接进入业务响应。")
    w.code("代码5-4 向量检索与MySQL回查核心逻辑", r"""
vector_results = search_knowledge_vectors(query_text, top_k=top_k)
items = []
for result in vector_results:
    metadata = result.get("metadata") or {}
    knowledge_id = int(metadata.get("knowledge_id") or 0)
    item = db.query(KnowledgeItem).filter(KnowledgeItem.id == knowledge_id).first()
    if item is None:
        continue
    result["knowledge_id"] = item.id
    result["title"] = item.title
    result["summary"] = item.summary
    result["truth_label"] = item.truth_label
    result["vector_sync_status"] = item.vector_sync_status
    items.append(result)
""")
    w.heading("5.4.4 向量同步状态与索引重建", 3)
    w.paragraph("知识库表包含`vector_sync_status`和`vector_sync_error`字段，取值包括`synced`、`pending`、`failed`和`delete_failed`。管理员后台展示同步状态，并提供单条重新向量化和全量重建入口。模型或维度变更后，应通过全量重建重置Chroma集合并逐条同步MySQL知识条目。真实后台中演示知识条目的`synced`状态见图5-12。")

    w.heading("5.5 多源候选证据获取与组织实现", 2)
    w.heading("5.5.1 联网补充的动态触发", 3)
    w.paragraph("系统不会无条件联网。`should_trigger_web_search`首先要求用户请求中的`enable_web_search=True`且系统配置`WEB_SEARCH_ENABLED=true`。随后根据本地RAG结果判断：本地无候选时触发；Top-1相似度低于0.45时触发；Top-1低于0.60且相似度不低于0.30的有效候选少于3条时触发。上述阈值是当前初始工程配置，用于召回补充判断，不表示经过实验优化的最优参数。")
    w.heading("5.5.2 网络搜索结果标准化", 3)
    w.paragraph("联网搜索由`BochaClient`调用Bocha Web Search接口，最大重试2次；认证失败和限流不重试，超时、5xx和网络异常按指数退避重试。搜索结果会被转换为与本地证据兼容的结构，包括标题、摘要、来源站点、URL、发布时间、相似度、`source_type=web_search`和`source_label=网络检索`，使后续候选组织和Prompt构造可以统一处理。")
    w.heading("5.5.3 候选证据去重与稳定标识", 3)
    w.paragraph("本地证据优先按`knowledge_id`去重，网络证据优先按规范化URL去重；缺少URL时，使用标题、来源和发布时间组成的键去重。合并时本地候选最多保留5条、网络候选最多保留5条，Prompt输入最多10条。候选标识方面，本地知识条目使用`kb:<knowledge_id>`，缺少知识ID的本地召回使用`kb:rag:<序号>`，网络候选使用`web:<序号>`，冲突时追加后缀。")
    w.table(
        "表5-2 候选证据统一数据结构",
        ["字段", "数据来源", "含义", "是否参与模型输入"],
        [
            ["candidate_id", "服务端生成", "模型只能引用的稳定候选标识", "是"],
            ["source_type", "本地或联网", "knowledge_base或web_search", "是"],
            ["title", "知识库/搜索结果", "候选新闻或核查条目标题", "是"],
            ["summary", "知识库/搜索结果", "证据摘要或网页片段", "是"],
            ["source_name", "知识库/搜索结果", "来源名称或站点", "是"],
            ["source_url", "知识库/搜索结果", "网络证据URL；部分本地有效证据持久化表未保存", "部分"],
            ["similarity_score", "Chroma/搜索得分", "仅用于召回、触发联网和展示", "否"],
            ["truth_label", "知识库", "历史核查真实性标签", "是"],
            ["risk_level", "知识库", "历史风险等级", "是"],
            ["rank_order", "服务端", "召回或仲裁排序", "否"],
        ],
    )
    w.heading("5.5.4 基于输入种子的稳定候选排序", 3)
    w.paragraph("候选合并后不直接按来源固定排列，而是使用新闻标题和正文作为种子，对`seed:candidate_id`计算SHA-256散列并排序。同一输入下候选顺序可复现，不同输入下本地和网络来源的位置会自然变化，从而减少固定来源位置给模型带来的偏置。该方法不能完全消除模型对来源、表述或上下文的偏好，因此后续仍需契约校验和人工复核机制配合。")
    w.figure("fig5-4-candidates.png", "图5-4 多源候选证据标准化与组织流程", width=5.8)
    w.code("代码5-5 candidate_id生成与稳定排序", r"""
def _ensure_candidate_ids(evidence_list):
    used = set()
    for idx, item in enumerate(evidence_list, start=1):
        if item.get("candidate_id"):
            base = item["candidate_id"]
        elif item.get("knowledge_id"):
            base = f"kb:{item['knowledge_id']}"
        else:
            base = f"kb:rag:{idx}"
        item["candidate_id"] = _dedupe(base, used)

def build_neutral_candidate_order(candidates, seed_material):
    return sorted(candidates, key=lambda item:
        sha256(f"{seed_material}:{item['candidate_id']}".encode()).hexdigest())
""")

    w.heading("5.6 大语言模型分析与证据仲裁实现", 2)
    w.heading("5.6.1 RAG Prompt构造", 3)
    w.paragraph("Prompt由系统任务、新闻内容、候选证据、输出格式和证据仲裁约束组成。`llm_service`会将新闻标题和正文放入明确边界中，并要求模型把新闻和候选证据都视为待分析数据，不执行其中的指令；候选证据输入前还会移除检索相似度、原始排序等辅助字段，避免模型直接把召回分当作事实结论。")
    w.paragraph("输出契约要求模型以固定JSON结构返回总体判断、风险点、关键词、建议、`evidence_arbitration`、`evidence_quality`和`similar_news`。证据仲裁约束包括：只能引用给定`candidate_id`，所有候选必须被划分为有效或排除，不能新增候选，不能重复划分。论文中不粘贴完整Prompt，避免模板噪声影响实现说明。")
    w.heading("5.6.2 结构化模型调用与结果解析", 3)
    w.paragraph("模型调用使用OpenAI兼容Chat Completions接口，当前运行配置中模型为`deepseek-v4-pro`，请求超时由配置控制。返回文本先尝试整体JSON解析，再从文本中提取JSON对象；字段缺失或类型异常时由解析器补默认值或记录错误。`_parse_evidence_quality`会从覆盖度和一致性重新计算`score=0.6*coverage+0.4*consistency`，避免直接信任模型给出的总分算术。")
    w.heading("5.6.3 有效证据与排除证据划分", 3)
    w.paragraph("模型仲裁输出分为`ranked_evidence`和`rejected_evidence`。有效证据包含`candidate_id`、相关性分、质量分、立场和理由；排除证据包含`candidate_id`和排除理由。通过契约校验的有效证据才参与证据质量和最终评分；排除证据仅用于解释候选被剔除的原因。运行页面中有效证据和排除证据的展示效果见图5-9，联网候选被排除时的来源标签见图5-10。")
    w.heading("5.6.4 输出契约校验与聚焦重试", 3)
    w.paragraph("证据仲裁契约校验在服务端完成，它验证的是结构、范围和候选完整性，不能单独证明模型语义判断的事实正确性。首次校验失败时，系统最多进行一次聚焦重试，重试Prompt只要求修复证据仲裁、证据质量和相似新闻结构；若仍失败，则该批候选不参与证据质量和最终评分，并在`analysis_payload`中保存异常摘要。")
    w.table(
        "表5-3 证据仲裁输出契约校验规则",
        ["校验项", "合法要求", "异常处理"],
        [
            ["candidate_id合法性", "必须来自本次候选集合", "记录错误并触发聚焦重试"],
            ["候选完整覆盖", "每个候选必须出现在有效或排除列表之一", "重试；仍失败则不使用仲裁结果"],
            ["不重复划分", "同一candidate_id不能重复或跨列表出现", "重试并记录重复ID"],
            ["分数范围", "相关性和质量分为0到100数字", "重试；非法项不落入有效证据"],
            ["立场枚举", "support、contradict、neutral之一", "重试并记录枚举错误"],
            ["必需字段", "有效证据含分数、立场和理由；排除证据含理由", "重试或标记retry_exhausted"],
            ["理由文本", "非空字符串", "缺失时视为契约失败"],
        ],
    )
    w.figure("fig5-5-llm-contract.png", "图5-5 模型证据仲裁、契约校验与聚焦重试流程", width=5.8)
    w.code("代码5-6 证据仲裁契约校验核心逻辑", r"""
ranked = arbitration.get("ranked_evidence")
rejected = arbitration.get("rejected_evidence")
candidate_ids = {c["candidate_id"] for c in candidates}
seen = set()
for item in ranked:
    cid = item.get("candidate_id")
    if cid not in candidate_ids or cid in seen:
        errors.append("invalid or duplicated candidate_id")
    if item.get("stance") not in {"support", "contradict", "neutral"}:
        errors.append("invalid stance")
    _check_score(item.get("relevance_score"))
    _check_score(item.get("quality_score"))
    seen.add(cid)
for item in rejected:
    cid = item.get("candidate_id")
    if cid not in candidate_ids or cid in seen:
        errors.append("invalid rejected candidate")
missing = candidate_ids - seen
""")

    w.heading("5.7 可信度评分与风险分类实现", 2)
    w.heading("5.7.1 大语言模型语义分处理", 3)
    w.paragraph("模型语义分记为`S_L`，来源于解析后的`llm_score`字段。服务端将其归一化到0到100之间，缺失或非数字时按0处理。若`_is_llm_failure`识别到模型整体失败，系统会构造降级结果并使最终评分仅依赖规则分。")
    w.heading("5.7.2 证据质量分计算", 3)
    w.paragraph("证据质量分记为`S_E`，由覆盖度`C`和一致性`K`计算。服务端重新计算总分而不是直接采用模型返回的证据质量总分，保证算术和范围一致；但这只能保证公式计算正确，不能证明模型给出的`C`和`K`绝对正确。")
    w.formula("S_E=0.6C+0.4K", "（5-1）")
    w.heading("5.7.3 确定性规则评分", 3)
    w.paragraph("规则分`S_R`由`rule_score_service`计算，初始为100分，并根据来源完整性、表达风险、证据冲突和事实可信度线索扣分。规则项不是直接判定新闻虚假，而是为综合评分提供可解释的风险信号。")
    w.table(
        "表5-4 确定性规则评分",
        ["规则项", "触发条件", "分值变化", "反映的风险"],
        [
            ["来源完整性", "缺少来源名称且标题正文无官方机构线索", "-20", "来源不可追溯"],
            ["夸张表达", "出现“震惊”“疯传”“必看”等传播型词语", "-15", "标题党或诱导传播"],
            ["情绪化表达", "出现强烈情绪词", "-15", "表述可能偏离中性新闻风格"],
            ["绝对化表达", "出现“百分百”“一定”“所有人”等绝对词", "-15", "过度承诺或泛化"],
            ["证据冲突", "有效证据Top5含不实、谣言等负向线索且相似度较高", "-25", "与历史核查证据冲突"],
        ],
    )
    w.heading("5.7.4 分支式综合评分", 3)
    w.paragraph("综合评分根据模型可用性和有效证据是否存在分为三支。模型不可用时，系统只使用规则分，避免使用失效模型分；模型可用但没有有效证据时，使用语义分和规则分；存在有效证据时，引入证据质量分。")
    w.formula("S=S_R, 模型服务不可用", "（5-2）")
    w.formula("S=0.6S_L+0.4S_R, 模型可用但无有效证据", "（5-3）")
    w.formula("S=0.5S_L+0.3S_E+0.2S_R, 模型可用且存在有效证据", "（5-4）")
    w.code("算法5-1 新闻可信度分支式评分算法", r"""
输入：S_L、S_R、evidence_quality、effective_evidence、llm_status
如果 llm_status == failure:
    S = S_R
否则如果 effective_evidence 为空:
    S = 0.6 * S_L + 0.4 * S_R
否则:
    C = evidence_quality.coverage
    K = evidence_quality.consistency
    S_E = 0.6 * C + 0.4 * K
    S = 0.5 * S_L + 0.3 * S_E + 0.2 * S_R
S = clamp(round(S, 2), 0, 100)
返回 S 与风险等级
""")
    w.heading("5.7.5 风险等级映射与降级状态", 3)
    w.paragraph("风险等级由最终分数映射：80分及以上为可信新闻，60到79.99分为存疑信息，40到59.99分为疑似谣言，低于40分为高风险谣言。页面会区分正常评估、证据不足、模型降级和仲裁不完整状态。图5-8展示正常模型可用、证据质量可用时的总览；图5-14展示模型服务异常导致证据仲裁暂不可用时的降级状态。")

    w.heading("5.8 检测结果持久化与查询实现", 2)
    w.heading("5.8.1 检测记录与证据保存", 3)
    w.paragraph("检测完成后，`save_detection_record`创建`DetectionRecord`并关联`EvidenceMatch`。记录保存新闻标题、正文、类别、关键词、最终分数、证据召回展示分、模型分、规则分、风险等级、判断结论、判断理由、风险点、建议、高风险标记和报告URL。有效证据表保存`knowledge_id`、标题、摘要、来源名称、相似度和排序。当前ORM模型没有保存网络证据URL和来源类型到`EvidenceMatch`，这些内容主要保留在`analysis_payload`中。")
    w.heading("5.8.2 评估过程数据持久化", 3)
    w.paragraph("`analysis_payload`以JSON字符串保存过程数据，包括发布时间、来源名称、来源URL、是否允许联网、原始候选列表、排除证据、相似新闻、证据质量、仲裁状态、质量状态、仲裁错误、重试次数、契约版本、本地证据是否命中和网络证据是否命中等。这样详情页和后续复核可以还原模型仲裁和降级原因。")
    w.heading("5.8.3 历史记录、详情与重新评估", 3)
    w.paragraph("登录用户可通过`GET /api/detect/history`查询本人历史记录，管理员可在后台按条件查看全量记录。`GET /api/detect/{id}`会先按当前用户角色和资源归属过滤，再返回详情。重新评估接口不会覆盖原记录，而是基于原输入重新执行检索、模型和评分，生成新的检测记录，保留历史审计链路。历史记录与PDF报告状态见图5-11。")
    w.heading("5.8.4 高风险记录与复核状态", 3)
    w.paragraph("当最终分数低于40或风险等级为高风险谣言时，系统将`is_high_risk`置为真。高风险后台支持待审核、审核通过和驳回状态，并可控制是否公开。未审核或驳回记录不会进入用户端公开高风险列表。管理员复核列表见图5-13。")

    w.heading("5.9 知识库跨存储一致性与恢复实现", 2)
    w.heading("5.9.1 知识条目新增与向量同步", 3)
    w.paragraph("系统以MySQL中的`KnowledgeItem`作为业务事实源，Chroma只作为派生索引。新增知识条目时，服务先提交MySQL记录，再调用`_sync_knowledge_vector`生成Embedding并写入Chroma；若向量生成或写入失败，知识条目仍保留，状态标记为`failed`并记录错误，供管理员后台重试。")
    w.heading("5.9.2 知识条目修改与向量替换", 3)
    w.paragraph("修改知识条目时，服务在同一数据库会话中先更新MySQL对象并flush，再调用Chroma upsert替换旧向量。若向量同步失败，服务抛出`KnowledgeVectorSyncError`并回滚本次数据库修改，避免业务字段已更新但向量仍对应旧文本。")
    w.heading("5.9.3 知识条目删除与补偿处理", 3)
    w.paragraph("删除流程先删除Chroma向量，成功后再删除MySQL记录。若向量删除失败，系统不删除MySQL并标记同步失败；若向量删除成功但数据库删除失败，服务尝试恢复向量并将状态标记为`delete_failed`。该补偿降低跨存储不一致概率，但不能彻底消除进程硬崩溃、断电或强制终止形成的中间状态。")
    w.code("代码5-7 知识库删除的跨存储补偿", r"""
item = get_knowledge_item(db, item_id)
try:
    delete_knowledge_vector(item)
except Exception as exc:
    mark_vector_failed(db, item, str(exc))
    raise KnowledgeVectorSyncError(str(exc))
try:
    db.delete(item)
    db.commit()
except Exception:
    db.rollback()
    try:
        upsert_knowledge_item_vector(item, build_embedding_text(item))
    except Exception as restore_exc:
        mark_delete_failed(db, item_id, str(restore_exc))
    raise
""")
    w.heading("5.9.4 同步重试与全量索引重建", 3)
    w.paragraph("管理员可以对单条失败知识执行重新向量化，也可以触发全量索引重建。全量重建会重置Chroma集合，然后遍历MySQL知识条目逐条同步并统计成功、失败和失败ID。当前实现以重置集合的方式消除孤立旧向量，不包含独立后台定时孤立向量扫描任务。图5-6总结跨存储同步、补偿和恢复流程。")
    w.figure("fig5-6-cross-store.png", "图5-6 MySQL与Chroma跨存储同步、补偿和恢复实现流程", width=5.8)

    w.heading("5.10 检测报告生成与文件管理实现", 2)
    w.heading("5.10.1 报告模板渲染", 3)
    w.paragraph("报告服务读取检测详情和有效证据，将标题、正文摘要、分数、风险等级、判断理由、风险点、建议、证据项、生成时间和用户信息组织为Jinja2模板上下文。模板文件位于`backend/app/templates/reports/detection_report.html`，生成的HTML作为PDF转换输入。")
    w.heading("5.10.2 PDF文件生成", 3)
    w.paragraph("PDF生成由`xhtml2pdf`完成。报告根目录来自`REPORT_DIR`配置，当前配置位于后端源码目录之外的`../data/reports`。文件名使用`report_<uuid32>.pdf`和对应HTML文件，按`detection_<id>`子目录保存，降低不同检测记录之间的文件冲突。")
    w.heading("5.10.3 报告记录与文件一致性", 3)
    w.paragraph("PDF转换成功后，`save_generated_report`创建或更新`Report`记录，并同步更新检测记录的`report_url`。下载前，服务校验报告记录存在、当前用户拥有该检测记录或为管理员、PDF路径位于报告根目录内、文件名符合生成规则且文件实际存在。")
    w.heading("5.10.4 生成失败与孤儿文件处理", 3)
    w.paragraph("若HTML写入、PDF转换或数据库保存失败，`generate_detection_report`会删除本次新生成的HTML和PDF文件，避免失败产物残留。报告重新生成成功后，服务会清理旧报告文件。当前代码未实现独立的定时孤儿文件扫描机制；后台报告列表可以识别数据库记录存在但PDF文件缺失的`missing`状态，PDF失败不影响原检测结果。")
    w.code("代码5-8 报告生成失败清理路径", r"""
created_files = []
try:
    html_path.write_text(rendered_html, encoding="utf-8")
    created_files.append(html_path)
    pisa_status = pisa.CreatePDF(rendered_html, dest=pdf_file)
    if pisa_status.err:
        raise ReportServiceError("PDF生成失败")
    created_files.append(pdf_path)
    report = save_generated_report(db, detection, html_path, pdf_path)
except Exception:
    for file_path in created_files:
        if file_path.exists():
            file_path.unlink()
    raise
""")

    w.heading("5.11 前端主要功能实现", 2)
    w.heading("5.11.1 新闻检测与URL预览页面", 3)
    w.paragraph("前端检测页提供手工输入、示例填充、URL提取、发布时间填写和联网搜索开关。URL预览成功后，页面将标题、正文、来源和发布时间回填到同一表单，用户仍可编辑。提交检测时，前端将响应写入临时缓存并跳转结果页。")
    w.heading("5.11.2 结果解释与证据展示页面", 3)
    w.paragraph("结果页按综合评分、证据质量、大模型判断和规则评分展示检测结论，并显示判断理由、风险点、关键词、有效证据、排除证据、相似新闻、处理步骤和免责声明。当`arbitration_status`为`provider_error`、`retry_exhausted`或`unavailable`时，页面显示证据仲裁暂不可用提示，并支持登录用户重新评估。")
    w.heading("5.11.3 历史记录与报告页面", 3)
    w.paragraph("历史页要求登录后访问，只展示当前用户记录。页面支持关键词和风险等级筛选，并展示报告状态；有报告的记录可以通过授权下载PDF。ResultView中也提供生成、重新生成和下载报告按钮，未登录用户会被引导登录。")
    w.heading("5.11.4 管理员后台与数据可视化", 3)
    w.paragraph("管理员后台包含用户管理、检测记录、知识库、Prompt模板、高风险新闻、统计、报告和系统日志页面。知识库页展示向量同步状态并提供重建入口；Prompt页支持默认模板管理；高风险页支持复核和公开控制；日志页展示登录、检测、知识库、Prompt和复核等关键操作。")
    w.table(
        "表5-6 前端页面、接口与主要状态",
        ["页面", "主要接口", "关键状态", "实现说明"],
        [
            ["新闻检测", "/detect/extract-preview、/detect/news", "extracting、submitting、enable_web_search", "URL回填和手工检测入口"],
            ["结果详情", "/detect/{id}、/report/generate/{id}", "qualityState、arbitrationUnavailable、reportBusy", "评分、证据、降级和报告"],
            ["历史记录", "/detect/history", "筛选条件、report_url", "仅本人记录和报告下载"],
            ["知识库后台", "/admin/knowledge", "vector_sync_status、vector_sync_error", "向量状态与重建"],
            ["高风险后台", "/admin/high-risk", "review_status、is_public", "复核和公开控制"],
            ["系统日志", "/admin/logs", "module、action、keyword", "关键操作审计"],
        ],
    )
    w.paragraph("图5-7至图5-14为本章运行验证阶段通过Playwright从真实前后端服务采集的系统页面截图，演示账号与演示数据均记录在《第五章撰写说明.md》中。")
    w.figure("fig5-7-detect-url-preview.png", "图5-7 新闻检测页面与URL提取回填状态", screenshot=True, width=5.9)
    w.figure("fig5-8-result-overview.png", "图5-8 检测结果总览、评分与报告按钮", screenshot=True, width=5.9)
    w.figure("fig5-9-result-evidence.png", "图5-9 有效证据与排除证据展示区域", screenshot=True, width=5.9)
    w.figure("fig5-10-web-excluded-evidence.png", "图5-10 联网候选证据与排除证据区域", screenshot=True, width=5.9)
    w.figure("fig5-11-history-report.png", "图5-11 历史记录与PDF报告状态", screenshot=True, width=5.9)
    w.figure("fig5-12-admin-knowledge.png", "图5-12 管理员知识库与向量同步状态", screenshot=True, width=5.9)
    w.figure("fig5-13-admin-high-risk.png", "图5-13 高风险记录复核列表", screenshot=True, width=5.9)
    w.figure("fig5-14-degraded-result.png", "图5-14 模型异常或仲裁不可用降级展示", screenshot=True, width=5.9)

    w.heading("5.12 异常处理、系统日志与运行保障", 2)
    w.heading("5.12.1 统一异常响应", 3)
    w.paragraph("后端在`main.py`注册HTTP异常、Pydantic校验异常和SQLAlchemy异常处理器。接口层将业务异常转换为统一`code/message/data`响应，前端通过Axios拦截器统一处理401并清除本地登录态。")
    w.heading("5.12.2 外部服务故障与降级处理", 3)
    w.paragraph("外部服务故障不会全部导致检测流程中断。URL提取失败只影响预览；联网搜索失败会记录日志并使用本地证据继续；模型整体失败时系统进入规则评分降级；证据仲裁重试失败时，候选不参与证据质量和最终证据分支。Chroma检索失败属于RAG基础能力不可用，检测接口返回503。")
    w.table(
        "表5-5 系统异常与降级处理",
        ["故障位置", "系统处理", "用户提示", "是否保存记录", "日志状态"],
        [
            ["URL提取失败", "返回422，不进入检测链路", "链接提取失败或安全拦截", "否", "接口日志"],
            ["Embedding失败", "知识同步标记failed或检测检索失败", "知识库显示错误或检测503", "视场景而定", "服务日志"],
            ["Chroma不可用", "检测抛出KnowledgeRetrievalFailedError", "证据检索失败", "否", "服务日志"],
            ["联网搜索失败", "捕获BochaServiceError，使用本地证据继续", "通常不阻断页面", "是", "warning日志"],
            ["模型返回异常", "解析失败后默认字段或进入契约校验失败", "结果显示降级或重试提示", "是", "服务日志"],
            ["聚焦重试失败", "arbitration_status=retry_exhausted", "证据仲裁暂不可用", "是", "analysis_payload保存摘要"],
            ["模型整体失败", "最终分数使用规则分", "模型调用失败/降级提示", "是", "risk_points记录"],
            ["数据库提交失败", "事务回滚并返回500", "服务器异常", "否或部分回滚", "SQLAlchemy异常处理"],
            ["向量同步失败", "状态failed，保留MySQL事实记录", "后台显示向量错误", "是", "vector_sync_error"],
            ["PDF生成失败", "删除本次文件，不影响检测记录", "报告生成失败", "检测记录保留", "服务异常"],
        ],
    )
    w.heading("5.12.3 关键操作日志", 3)
    w.paragraph("系统日志覆盖注册、登录成功、登录失败、新闻检测、重新评估、知识库新增/修改/删除/向量化/重建、Prompt模板操作、高风险复核和公开状态调整等。日志记录用户ID、模块、动作、描述、IP和时间，不记录密码、完整令牌、JWT密钥、API密钥或不必要的完整敏感正文。")
    w.heading("5.12.4 配置管理与敏感信息保护", 3)
    w.paragraph("配置由`backend/.env`读取，包含数据库、JWT密钥、DashScope、DeepSeek、Bocha、Chroma路径、报告目录、限流和CORS等设置。`Settings`会拒绝缺失或占位的`SECRET_KEY`，并将报告目录解析到后端源码目录之外。实际运行截图中未展示任何密钥、令牌或数据库密码。")

    w.heading("5.13 本章小结", 2)
    w.paragraph("本章基于当前项目真实实现，说明了第4章提出的总体架构如何落到前后端模块、数据模型、服务调用和页面状态中。系统以MySQL为业务事实源，以Chroma作为派生语义索引，以DeepSeek模型完成证据约束下的结构化分析和仲裁，并通过分支式评分在正常、证据不足、模型失败和仲裁失败等状态下保持可解释输出。")
    w.paragraph("运行验证表明，新闻输入、URL预览、本地RAG检索、模型仲裁、评分、历史查询、PDF报告、知识库向量状态和高风险复核等功能均已在当前系统中落地。对于尚未实现的独立孤儿文件扫描、EvidenceMatch网络来源字段持久化等改进点，本章没有作为已完成功能写入正文，而是在撰写说明中单独列出。")


def build_notes(stats: dict) -> str:
    run = json.loads(RUN_JSON.read_text(encoding="utf-8"))
    return f"""# 第五章撰写说明

## 1. 第五章最终目录

第5章系统详细设计与实现；5.1系统实现概述；5.2用户认证与权限控制实现；5.3新闻输入与网页内容提取实现；5.4新闻知识库与本地语义检索实现；5.5多源候选证据获取与组织实现；5.6大语言模型分析与证据仲裁实现；5.7可信度评分与风险分类实现；5.8检测结果持久化与查询实现；5.9知识库跨存储一致性与恢复实现；5.10检测报告生成与文件管理实现；5.11前端主要功能实现；5.12异常处理、系统日志与运行保障；5.13本章小结。

## 2. 核验过的项目事实

- codebase-memory：用户要求使用，但当前工具上下文中未暴露`search_graph`、`trace_path`、`get_code_snippet`等工具；`tool_search`未检索到codebase-memory工具，可安装插件列表也无匹配项。因此本章改用当前代码、配置、模型、迁移、测试和真实运行页面核验，并将该限制记录于此。
- 后端目录：`backend/app/api`、`models`、`schemas`、`crud`、`services`、`core`、`templates`。
- 前端目录：`frontend/src/api`、`views`、`components`、`stores`、`router`、`utils`。
- 检测入口：`POST /api/detect/news`进入`detect_news_credibility`。
- URL预览入口：`POST /api/detect/extract-preview`，只回填预览，不写检测记录。
- SSRF：协议白名单http/https；拒绝本机、私有、链路本地和保留地址；重定向复检；10秒超时；2MB读取上限；最多3次重定向。
- Embedding：当前配置`EMBEDDING_PROVIDER=dashscope`、`DASHSCOPE_EMBEDDING_MODEL=text-embedding-v4`、`EMBEDDING_DIMENSION=1024`。
- Chroma：collection=`knowledge_items`，cosine空间，向量ID=`knowledge:<id>`。
- RAG Top-K：`RAG_TOP_K=10`，Prompt候选上限10；联网合并本地最多5条、网络最多5条。
- 联网触发：本地无候选；Top1<0.45；Top1<0.60且相似度>=0.30的有效候选少于3；且用户和系统均允许联网。
- 证据仲裁契约：candidate_id合法、候选完整覆盖、不重复、分数0-100、stance枚举、理由非空。
- 聚焦重试：首次契约失败后最多重试1次。
- 证据质量：`S_E=0.6C+0.4K`由服务端解析器重算。
- 综合评分：模型失败使用`S_R`；无有效证据使用`0.6S_L+0.4S_R`；存在有效证据使用`0.5S_L+0.3S_E+0.2S_R`。
- 风险阈值：>=80可信新闻；>=60存疑信息；>=40疑似谣言；<40高风险谣言。
- MySQL事实源：知识库业务数据以MySQL为准，Chroma为派生索引。
- 报告：Jinja2渲染HTML，xhtml2pdf生成PDF，报告目录来自`REPORT_DIR`。

## 3. 第4章设计与第5章实现映射

已写入正文表5-1，覆盖URL提取、本地语义检索、联网证据补充、候选证据组织、模型仲裁、契约校验、分支评分、结果持久化、跨存储恢复和报告生成。

## 4. 使用的核心代码位置

- `backend/app/api/v1/detect.py`
- `backend/app/services/detection_service.py`
- `backend/app/services/llm_service.py`
- `backend/app/services/chroma_service.py`
- `backend/app/services/knowledge_service.py`
- `backend/app/services/web/web_search_service.py`
- `backend/app/services/web/bocha_client.py`
- `backend/app/services/web/web_content_fetcher.py`
- `backend/app/services/rule_score_service.py`
- `backend/app/services/report_service.py`
- `backend/app/core/security.py`
- `backend/app/core/deps.py`
- `frontend/src/views/DetectView.vue`
- `frontend/src/views/ResultView.vue`
- `frontend/src/views/HistoryView.vue`
- `frontend/src/views/admin/AdminKnowledgeView.vue`
- `frontend/src/views/admin/AdminHighRiskView.vue`

## 5. 新增图表清单

- 流程图：图5-1至图5-6，共6幅。
- 系统截图：图5-7至图5-14，共8张。
- 表格：表5-1至表5-6，共6张。
- 代码或算法：代码5-1至代码5-8及算法5-1，共9段。

## 6. 页面截图清单

- 图5-7 新闻检测页面与URL提取回填状态。
- 图5-8 检测结果总览、评分与报告按钮。
- 图5-9 有效证据与排除证据展示区域。
- 图5-10 联网候选证据与排除证据区域。
- 图5-11 历史记录与PDF报告状态。
- 图5-12 管理员知识库与向量同步状态。
- 图5-13 高风险记录复核列表。
- 图5-14 模型异常或仲裁不可用降级展示。

## 7. 截图所用演示数据说明

- 演示用户：`chapter5_user`；演示管理员：`chapter5_admin`。
- 演示知识条目：ID 163-166，标题均以“第五章演示”开头，向量状态均为`synced`。
- 主流程检测：ID {run.get("detection_id")}，标题“网传喝柠檬水三天清除血管垃圾并替代降脂药”，仲裁状态`{run.get("detection", {}).get("data", {}).get("arbitration_status")}`，质量状态`{run.get("detection", {}).get("data", {}).get("quality_status")}`。
- 联网补充页面证明：使用管理员访问已有记录ID 58，该记录包含5条`web_search`候选并且仲裁状态为`ok`。
- 降级页面证明：使用管理员访问已有记录ID 59，`arbitration_status=provider_error`，用于展示模型服务异常降级状态。

## 8. 运行验证结果摘要

- 后端测试：`python -m unittest discover -s tests -p "test_*.py"`，392个测试通过。
- 前端测试：`npm test`，14个测试通过。
- 前端构建：`npm run build`成功；Vite提示部分chunk超过500KB，属于构建警告。
- 数据库迁移：`python -m app.db.migrate`成功，Alembic current/head均为`0007_analysis_payload`。
- 前后端启动：后端`http://127.0.0.1:8000/docs`返回200，前端`http://127.0.0.1:5173/`返回200。
- URL预览：`https://www.gov.cn/`提取成功并回填页面。
- 主检测流程：检测ID {run.get("detection_id")}生成成功，PDF报告生成状态`{run.get("report", {}).get("status")}`。
- 管理员知识库：第五章演示知识条目可查询且向量状态为`synced`。
- 高风险复核：后台列表可展示待审核、审核通过和公开状态。
- 系统日志：后台日志页可展示登录、检测等关键操作。

## 9. 未写入正文的功能

- 未写入任何准确率、召回率、F1、混淆矩阵、压力测试、消融实验或模型对比结论。
- 未写入Redis、消息队列、微服务、知识图谱、重排序模型、模型训练或Kubernetes等项目不存在功能。

## 10. 无法确认的事实

- 当前环境未提供codebase-memory MCP工具，无法通过知识图谱接口核验调用链。
- Word目录域未在脚本中刷新；请在Microsoft Word中右键目录，选择“更新域—更新整个目录”。

## 11. 项目尚未实现的建议项

- `EvidenceMatch` ORM当前没有持久化`source_type`和`source_url`，虽然迁移文件曾增加相关字段；建议统一模型、迁移和CRUD。
- 检测详情接口当前主要从`analysis_payload`恢复候选和排除证据，但`web_search_triggered`没有稳定持久化到详情响应；建议补齐。
- 报告服务当前没有独立定时孤儿文件扫描；建议增加管理命令或后台任务。
- codebase-memory工具未接入当前会话；建议在后续环境中启用以提高代码发现效率。

## 12. 与前四章一致性检查

- 第1章方法中的RAG、LLM证据约束、证据质量和分支评分均已在第五章对应实现说明。
- 第2章需求编号覆盖的用户检测、URL提取、历史、报告、后台知识库、Prompt、高风险复核、系统日志和安全要求均已映射。
- 第3章技术选型与实际依赖一致：FastAPI、SQLAlchemy、Alembic、Vue3、Element Plus、Chroma、DashScope、DeepSeek、Jinja2、xhtml2pdf。
- 第4章总体设计与第五章实现映射已写入表5-1。

## 13. Word格式检查

- 未修改源文件前四章正文，而是复制源docx后在参考文献前插入第五章。
- 未新增分页符和分节符。
- 正文采用五号宋体为主，英文、数字按Times New Roman；代码为等宽字体。
- 表格无颜色填充；图题位于图下，表题位于表上。
- 公式以可编辑文本形式写入并编号。

## 14. 仍需作者人工确认的内容

- 在Microsoft Word中更新目录域。
- 检查学校模板对代码字体、图表跨页和公式排版是否有额外要求。
- 如第6章需要实验指标，应单独补充数据集、评价方法和测试结果，不应复用本章功能运行结论替代。

## 15. 输出统计

- 段落数：{stats["paragraphs"]}
- 代码或算法段数：{stats["code"]}
- 新增表格数：{stats["tables"]}
- 新增流程图数：6
- 插入系统截图数：{stats["screenshots"]}
- 公式和参数：已核验
- 是否修改前四章：否
- 输出Word：`{OUT_DOCX}`
"""


def main() -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SOURCE_DOCX, OUT_DOCX)
    doc = Document(str(OUT_DOCX))
    set_default_styles(doc)
    ref = find_reference_paragraph(doc)
    writer = Writer(doc, ref)
    add_core_content(writer)
    doc.save(str(OUT_DOCX))
    stats = {
        "paragraphs": writer.paragraph_count,
        "code": writer.code_count,
        "tables": writer.table_count,
        "figures": writer.figure_count,
        "screenshots": writer.screenshot_count,
    }
    NOTE_MD.write_text(build_notes(stats), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    print(OUT_DOCX)
    print(NOTE_MD)


if __name__ == "__main__":
    main()
