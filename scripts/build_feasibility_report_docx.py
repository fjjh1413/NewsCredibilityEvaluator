from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = Path(r"E:\nan\《基于 RAG 与大语言模型的网络新闻真伪鉴别系统设计》\开发管理")
OUTPUT_PATH = OUTPUT_DIR / "01_《基于 RAG 与大语言模型的网络新闻真伪鉴别系统设计》可行性研究报告.docx"

ARCH_IMAGE = PROJECT_ROOT / "docs/thesis/figures/chapter4/fig4-1-system-architecture.png"
FLOW_IMAGE = PROJECT_ROOT / "docs/thesis/figures/chapter4/fig4-4-detection-overall-flow.png"
STORE_IMAGE = PROJECT_ROOT / "docs/thesis/figures/chapter4/fig4-8-mysql-chroma-collaboration.png"

PROJECT_TITLE = "基于 RAG 与大语言模型的网络新闻真伪鉴别系统设计"
DOC_TITLE = "可行性研究报告"
DOC_NO = "NCE-FS-001"
VERSION = "V1.0"
DATE_TEXT = "2026年6月20日"

NAVY = "183B56"
BLUE = "176B87"
TEAL = "2A9D8F"
PALE_BLUE = "EEF6F8"
PALE_TEAL = "EAF8F5"
PALE_GOLD = "FFF8E8"
PALE_RED = "FFF0F0"
GOLD = "C58A18"
RED = "B42318"
GREEN = "187A5A"
GRAY = "667085"
LIGHT_GRAY = "F6F8FA"
WHITE = "FFFFFF"


def set_run_font(
    run,
    east_asia: str = "宋体",
    latin: str = "Times New Roman",
    size: float = 12,
    bold: bool | None = None,
    color: str | None = None,
) -> None:
    run.font.name = latin
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), east_asia)
    run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if color:
        run.font.color.rgb = RGBColor.from_string(color)


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, top: int = 90, start: int = 115, bottom: int = 90, end: int = 115) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for margin, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{margin}"))
        if node is None:
            node = OxmlElement(f"w:{margin}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_repeat_table_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def set_row_cant_split(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    cant_split = OxmlElement("w:cantSplit")
    tr_pr.append(cant_split)


def add_field(paragraph, instruction: str, placeholder: str = "") -> None:
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = instruction
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    text = OxmlElement("w:t")
    text.text = placeholder
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.extend((begin, instr, separate, text, end))


def set_page_number_format(section, fmt: str, start: int = 1) -> None:
    sect_pr = section._sectPr
    pg_num_type = sect_pr.find(qn("w:pgNumType"))
    if pg_num_type is None:
        pg_num_type = OxmlElement("w:pgNumType")
        sect_pr.append(pg_num_type)
    pg_num_type.set(qn("w:fmt"), fmt)
    pg_num_type.set(qn("w:start"), str(start))


def configure_section(section, *, header_footer: bool, page_format: str = "decimal") -> None:
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.45)
    section.bottom_margin = Cm(2.35)
    section.left_margin = Cm(2.85)
    section.right_margin = Cm(2.35)
    section.header_distance = Cm(1.05)
    section.footer_distance = Cm(1.05)
    if not header_footer:
        return

    section.header.is_linked_to_previous = False
    header_p = section.header.paragraphs[0]
    header_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    header_p.paragraph_format.space_after = Pt(2)
    run = header_p.add_run(f"{DOC_NO}  |  {DOC_TITLE}")
    set_run_font(run, size=8.5, color=GRAY)

    section.footer.is_linked_to_previous = False
    footer_p = section.footer.paragraphs[0]
    footer_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r1 = footer_p.add_run("内部资料    •    ")
    set_run_font(r1, size=8.5, color=GRAY)
    add_field(footer_p, "PAGE", "1")
    set_page_number_format(section, page_format, 1)


def configure_styles(doc: Document) -> None:
    normal = doc.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), "宋体")
    normal.font.size = Pt(12)
    normal.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    normal.paragraph_format.space_after = Pt(5)
    normal.paragraph_format.first_line_indent = Cm(0.85)

    title = doc.styles["Title"]
    title.font.name = "Arial"
    title._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), "黑体")
    title.font.size = Pt(22)
    title.font.bold = True
    title.font.color.rgb = RGBColor.from_string(NAVY)
    title.paragraph_format.space_after = Pt(14)
    title.paragraph_format.keep_with_next = True

    for style_name, size, color, before, after in (
        ("Heading 1", 16, NAVY, 18, 10),
        ("Heading 2", 14, BLUE, 14, 7),
        ("Heading 3", 12, "24556B", 10, 5),
        ("Heading 4", 11, "365F70", 8, 4),
    ):
        style = doc.styles[style_name]
        style.font.name = "Arial"
        style._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), "黑体")
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor.from_string(color)
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.keep_with_next = True
        style.paragraph_format.first_line_indent = Cm(0)

    for style_name in ("List Bullet", "List Number"):
        style = doc.styles[style_name]
        style.font.name = "Times New Roman"
        style._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), "宋体")
        style.font.size = Pt(11.5)
        style.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
        style.paragraph_format.space_after = Pt(3)


def add_body(doc: Document, text: str, *, indent: bool = True, bold_prefix: str | None = None) -> None:
    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.first_line_indent = Cm(0.85) if indent else Cm(0)
    paragraph.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    if bold_prefix and text.startswith(bold_prefix):
        r1 = paragraph.add_run(bold_prefix)
        set_run_font(r1, east_asia="黑体", size=12, bold=True, color=NAVY)
        r2 = paragraph.add_run(text[len(bold_prefix):])
        set_run_font(r2)
    else:
        run = paragraph.add_run(text)
        set_run_font(run)


def add_bullets(doc: Document, items: list[str]) -> None:
    for text in items:
        paragraph = doc.add_paragraph(style="List Bullet")
        paragraph.paragraph_format.left_indent = Cm(0.8)
        paragraph.paragraph_format.first_line_indent = Cm(-0.3)
        run = paragraph.add_run(text)
        set_run_font(run, size=11.5)


def add_numbered(doc: Document, items: list[str]) -> None:
    for index, text in enumerate(items, 1):
        paragraph = doc.add_paragraph()
        paragraph.paragraph_format.left_indent = Cm(0.8)
        paragraph.paragraph_format.first_line_indent = Cm(-0.35)
        paragraph.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
        paragraph.paragraph_format.space_after = Pt(3)
        run = paragraph.add_run(f"{index}. {text}")
        set_run_font(run, size=11.5)


def add_note(doc: Document, title: str, text: str, *, kind: str = "info") -> None:
    fill, accent = {
        "info": (PALE_BLUE, BLUE),
        "success": (PALE_TEAL, GREEN),
        "warning": (PALE_GOLD, GOLD),
        "danger": (PALE_RED, RED),
    }[kind]
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = table.cell(0, 0)
    set_cell_shading(cell, fill)
    set_cell_margins(cell, top=140, start=180, bottom=140, end=180)
    paragraph = cell.paragraphs[0]
    paragraph.paragraph_format.first_line_indent = Cm(0)
    paragraph.paragraph_format.space_after = Pt(0)
    r1 = paragraph.add_run(f"{title}｜")
    set_run_font(r1, east_asia="黑体", size=10.5, bold=True, color=accent)
    r2 = paragraph.add_run(text)
    set_run_font(r2, size=10.5, color="344054")
    spacer = doc.add_paragraph()
    spacer.paragraph_format.space_after = Pt(0)


def add_table(
    doc: Document,
    headers: list[str],
    rows: list[list[str]],
    widths: list[float] | None = None,
    *,
    header_fill: str = BLUE,
    font_size: float = 9.5,
) -> None:
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    header_row = table.rows[0]
    set_repeat_table_header(header_row)
    set_row_cant_split(header_row)
    for index, header in enumerate(headers):
        cell = header_row.cells[index]
        set_cell_shading(cell, header_fill)
        set_cell_margins(cell)
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        paragraph = cell.paragraphs[0]
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.paragraph_format.first_line_indent = Cm(0)
        run = paragraph.add_run(header)
        set_run_font(run, east_asia="黑体", size=font_size, bold=True, color=WHITE)
        if widths:
            cell.width = Cm(widths[index])

    for row_index, values in enumerate(rows):
        row = table.add_row()
        set_row_cant_split(row)
        if row_index % 2 == 1:
            for cell in row.cells:
                set_cell_shading(cell, LIGHT_GRAY)
        for index, value in enumerate(values):
            cell = row.cells[index]
            set_cell_margins(cell)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            paragraph = cell.paragraphs[0]
            paragraph.paragraph_format.first_line_indent = Cm(0)
            paragraph.paragraph_format.line_spacing = 1.15
            run = paragraph.add_run(str(value))
            set_run_font(run, size=font_size)
            if widths:
                cell.width = Cm(widths[index])
    spacer = doc.add_paragraph()
    spacer.paragraph_format.space_after = Pt(0)


def add_figure(doc: Document, image_path: Path, caption: str, *, width_inches: float) -> None:
    if not image_path.exists():
        raise FileNotFoundError(image_path)
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.first_line_indent = Cm(0)
    paragraph.paragraph_format.space_before = Pt(5)
    paragraph.paragraph_format.space_after = Pt(3)
    paragraph.add_run().add_picture(str(image_path), width=Inches(width_inches))
    caption_p = doc.add_paragraph()
    caption_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    caption_p.paragraph_format.first_line_indent = Cm(0)
    caption_p.paragraph_format.space_after = Pt(8)
    run = caption_p.add_run(caption)
    set_run_font(run, size=9.5, color=GRAY)


def page_break(doc: Document) -> None:
    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.space_after = Pt(0)
    paragraph.add_run().add_break(WD_BREAK.PAGE)


def add_center_title(doc: Document, text: str, size: float = 22, color: str = NAVY) -> None:
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.first_line_indent = Cm(0)
    run = paragraph.add_run(text)
    set_run_font(run, east_asia="黑体", latin="Arial", size=size, bold=True, color=color)


def build_cover(doc: Document) -> None:
    accent = doc.add_table(rows=1, cols=2)
    accent.alignment = WD_TABLE_ALIGNMENT.CENTER
    accent.autofit = False
    accent.cell(0, 0).width = Cm(10.5)
    accent.cell(0, 1).width = Cm(5.0)
    set_cell_shading(accent.cell(0, 0), NAVY)
    set_cell_shading(accent.cell(0, 1), TEAL)
    for cell in accent.rows[0].cells:
        cell.height = Cm(0.22)
        cell.text = ""

    for _ in range(4):
        doc.add_paragraph()

    label = doc.add_paragraph()
    label.alignment = WD_ALIGN_PARAGRAPH.CENTER
    label.paragraph_format.first_line_indent = Cm(0)
    r = label.add_run("SOFTWARE ENGINEERING DOCUMENT")
    set_run_font(r, east_asia="Arial", latin="Arial", size=10, bold=True, color=TEAL)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = Cm(0)
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(10)
    r = p.add_run(f"《{PROJECT_TITLE}》")
    set_run_font(r, east_asia="黑体", size=24, bold=True, color=NAVY)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = Cm(0)
    r = p.add_run("可 行 性 研 究 报 告")
    set_run_font(r, east_asia="黑体", size=28, bold=True, color=BLUE)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = Cm(0)
    r = p.add_run("Feasibility Study Report")
    set_run_font(r, east_asia="Arial", latin="Arial", size=13, bold=True, color=GRAY)

    for _ in range(3):
        doc.add_paragraph()

    info = [
        ("文档编号", DOC_NO),
        ("版本号", VERSION),
        ("文档状态", "正式版"),
        ("密级", "内部资料"),
        ("编制日期", DATE_TEXT),
    ]
    table = doc.add_table(rows=len(info), cols=2)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    for row, (key, value) in zip(table.rows, info):
        row.cells[0].width = Cm(4.2)
        row.cells[1].width = Cm(8.1)
        set_cell_shading(row.cells[0], PALE_BLUE)
        for cell in row.cells:
            set_cell_margins(cell, top=145, start=180, bottom=145, end=180)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            cell.paragraphs[0].paragraph_format.first_line_indent = Cm(0)
        r1 = row.cells[0].paragraphs[0].add_run(key)
        set_run_font(r1, east_asia="黑体", size=10.5, bold=True, color=NAVY)
        r2 = row.cells[1].paragraphs[0].add_run(value)
        set_run_font(r2, size=10.5)

    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = Cm(0)
    r = p.add_run("项目组")
    set_run_font(r, east_asia="黑体", size=12, bold=True, color=NAVY)


def build_document_control(doc: Document) -> None:
    add_center_title(doc, "文档控制信息", 20)
    add_table(
        doc,
        ["项目", "内容"],
        [
            ["文档名称", f"《{PROJECT_TITLE}》{DOC_TITLE}"],
            ["编制依据", "GB/T 8567—2006《计算机软件文档编制规范》"],
            ["适用阶段", "立项决策、开发复核、验收准备及后续部署决策"],
            ["评估基线", "2026年6月20日工作区源码、项目设计资料、知识图谱快照及验证结果"],
            ["分发范围", "项目负责人、开发人员、测试人员、指导教师/验收人员"],
        ],
        widths=[3.5, 13.0],
    )

    doc.add_heading("修订记录", level=2)
    add_table(
        doc,
        ["版本", "日期", "修订说明", "编制/修订"],
        [[VERSION, DATE_TEXT, "首次正式编制；形成完整可行性研究结论", "项目组"]],
        widths=[2.2, 3.3, 8.2, 2.8],
    )

    doc.add_heading("审核与批准", level=2)
    add_table(
        doc,
        ["角色", "姓名", "意见", "签字", "日期"],
        [
            ["编制", "", "", "", ""],
            ["审核", "", "", "", ""],
            ["批准", "", "", "", ""],
        ],
        widths=[2.4, 3.0, 5.5, 2.8, 2.8],
    )
    add_note(doc, "使用说明", "签字栏供项目提交或验收时填写；电子流转时可使用受控电子签名。", kind="info")


def build_abstract(doc: Document) -> None:
    page_break(doc)
    add_center_title(doc, "摘要", 20)
    add_body(
        doc,
        "本报告依据GB/T 8567—2006规定的可行性研究报告内容组织，对“基于RAG与大语言模型的网络新闻真伪鉴别系统”进行技术、经济、运行、进度、法律与社会因素综合论证。系统面向游客、注册用户和管理员，利用本地知识库向量检索、证据不足时的联网补充、规则评分和大语言模型结构化分析，形成可信度分数、风险等级、判断理由、风险点、有效证据、审核状态和PDF报告。",
    )
    add_body(
        doc,
        "评估以当前可运行原型为证据基线。代码知识图谱包含3,073个节点、8,131条关系和250个文件节点，识别出FastAPI后端、Vue前端、MySQL业务库、Chroma向量库及外部智能服务之间的主要依赖；检测主流程调用链已追踪至文本清洗、RAG检索、联网证据、规则评分、LLM分析、风险分级和持久化。2026年6月20日执行的后端392项测试、前端14项测试全部通过，前端生产构建成功。",
    )
    add_body(
        doc,
        "综合分析表明：现有技术栈成熟、原型闭环完整、开发与运行资源可获得，采用“RAG＋大语言模型＋规则评分＋人工复核”的推荐方案具备明显可实施性。系统仍受知识覆盖、外部API稳定性、模型幻觉、隐私与版权合规、跨存储一致性以及生产环境性能验证不足等因素约束。因此，本报告结论为“有条件可行”：可继续进入加固、验收和受控部署阶段，但不得把自动评分表述为权威事实认定；对外部署前须完成隐私告知、内容授权与最小化采集、备份恢复、生产安全配置、人工复核和性能容量验证。",
    )
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Cm(0)
    r1 = p.add_run("关键词：")
    set_run_font(r1, east_asia="黑体", size=11.5, bold=True, color=NAVY)
    r2 = p.add_run("新闻真伪鉴别；检索增强生成（RAG）；大语言模型；可行性研究；事实核查；风险评估")
    set_run_font(r2, size=11.5)


def build_toc(doc: Document) -> None:
    page_break(doc)
    add_center_title(doc, "目录", 20)
    toc = doc.add_paragraph()
    toc.paragraph_format.first_line_indent = Cm(0)
    add_field(toc, 'TOC \\o "1-3" \\h \\z \\u', "目录将在Word中自动更新")
    add_note(doc, "目录域", "文档已设置为打开时更新域；若页码未刷新，请在Word中选中目录并按F9。", kind="info")


def build_chapter_1(doc: Document) -> None:
    doc.add_heading("1 引言", level=1)
    doc.add_heading("1.1 编写目的", level=2)
    add_body(
        doc,
        "本报告用于回答本系统是否值得继续投入、能否在现有条件下完成验收并形成可受控部署的软件产品。报告通过分析业务问题、现有作业方式、建议方案、备选方案、投资收益、风险和法律社会因素，为项目负责人、开发人员、指导教师和验收人员提供可追溯的决策依据。",
    )
    add_body(
        doc,
        "由于项目已形成可运行原型，本报告不是脱离实现的前置设想，而是一次滚动可行性复核：以实际源码、数据库模型、接口、测试和构建结果降低估算不确定性，同时明确从课程/演示原型进入验收或公开部署前仍需完成的条件。",
    )

    doc.add_heading("1.2 背景", level=2)
    add_table(
        doc,
        ["项目属性", "说明"],
        [
            ["项目名称", f"{PROJECT_TITLE}"],
            ["系统简称", "网络新闻真伪鉴别系统（界面名称：智闻辨真）"],
            ["任务提出", "面向课程设计、毕业设计/答辩展示及小规模新闻核验辅助场景"],
            ["建设动因", "网络信息传播速度快、人工核验耗时、证据分散、结论难追溯；需要可解释的机器辅助核验闭环"],
            ["项目现状", "已具备前后端、数据库、RAG、LLM、联网证据、评分、审核、统计、日志与报告原型"],
            ["与其他系统关系", "依赖MySQL、Chroma、DeepSeek、DashScope及可选搜索服务；可独立部署，不替代权威辟谣平台"],
        ],
        widths=[3.5, 13.0],
    )

    doc.add_heading("1.3 定义", level=2)
    add_table(
        doc,
        ["术语/缩略语", "定义"],
        [
            ["RAG", "Retrieval-Augmented Generation，检索增强生成；先检索相关证据，再让模型基于证据分析。"],
            ["LLM", "Large Language Model，大语言模型；本系统主要使用DeepSeek对新闻和候选证据进行结构化分析。"],
            ["Embedding", "将文本映射为向量的过程，用于语义相似度检索；正式方案采用语义向量模型。"],
            ["Chroma", "本地持久化向量数据库，保存知识项向量和检索元数据。"],
            ["可信度评分", "系统在当前证据和规则下形成的0～100分辅助指标；不是行政、司法或媒体权威认定。"],
            ["高风险记录", "满足系统高风险规则的检测记录；公开前必须经过管理员审核。"],
            ["降级处理", "外部搜索或LLM不可用时，保留可用证据和规则结果，并显式标注能力受限。"],
            ["RPO/RTO", "恢复点目标/恢复时间目标，用于描述可接受的数据丢失窗口和服务恢复时长。"],
        ],
        widths=[3.7, 12.8],
    )

    doc.add_heading("1.4 参考资料", level=2)
    references = [
        ["[1]", "GB/T 8567—2006《计算机软件文档编制规范》", "现行；本报告章节结构的直接依据", "https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=84C42B6277D2714B7176B10C6E6B1A44"],
        ["[2]", "GB/T 8566—2022《系统与软件工程 软件生存周期过程》", "现行；用于过程与阶段控制", "https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=1196DB510493E4E57EC6796598E75CDA"],
        ["[3]", "GB/T 11457—2006《信息技术 软件工程术语》", "现行；用于术语统一", "https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=07E3E9867D23EA5A74EB525A44622E86"],
        ["[4]", "GB/T 25000.10—2016《系统与软件质量模型》", "现行；用于质量评价维度", "https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=DB14B9415F3D51A9EF321EA62EDDE9A6"],
        ["[5]", "GB/T 25000.51—2016《就绪可用软件产品的质量要求和测试细则》", "现行；用于验收与测试参考", "https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=4D62FDB5C72083A33B532CFBB08BB197"],
        ["[6]", "GB/T 35273—2020《信息安全技术 个人信息安全规范》", "现行；用于个人信息处理参考", "https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=4568F276E0F8346EB0FBA097AA0CE05E"],
        ["[7]", "GB/T 22239—2019《信息安全技术 网络安全等级保护基本要求》", "现行；用于公开部署安全参考", "https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=BAFB47E8874764186BDB7865E8344DAF"],
        ["[8]", "项目源码、Alembic迁移、项目设计文档及代码知识图谱", "评估基线：2026-06-20", "E:/nan/NewsCredibilityEvaluator"],
        ["[9]", "《生成式人工智能服务管理暂行办法》", "公开提供生成式AI服务时的条件性合规参考", "https://www.gov.cn/zhengce/zhengceku/202307/content_6891752.htm"],
        ["[10]", "《人工智能生成合成内容标识办法》", "现行；对外提供生成合成内容时的标识参考", "https://www.cac.gov.cn/2025-03/14/c_1743654684782215.htm"],
    ]
    add_table(doc, ["序号", "资料", "用途/状态", "来源"], references, widths=[1.2, 5.4, 4.0, 5.9], font_size=8.1)
    add_note(doc, "标准核验", "上述国家标准状态于2026年6月20日通过国家标准全文公开系统核实。法规适用性应在实际部署主体、服务对象和数据范围确定后由合规人员复核。", kind="warning")


def build_chapter_2(doc: Document) -> None:
    doc.add_heading("2 可行性研究的前提", level=1)
    doc.add_heading("2.1 要求", level=2)
    doc.add_heading("2.1.1 功能要求", level=3)
    add_table(
        doc,
        ["编号", "功能域", "核心要求", "优先级"],
        [
            ["F-01", "用户与权限", "支持游客、注册用户、管理员；注册登录、JWT鉴权、账号状态和角色权限控制", "高"],
            ["F-02", "新闻输入", "支持标题、正文、类别、来源和发布时间输入；可选URL安全提取", "高"],
            ["F-03", "证据检索", "从Chroma召回本地证据；本地证据不足时可触发联网补充并去重", "高"],
            ["F-04", "智能分析", "对新闻与证据执行结构化LLM分析、证据质量评价和证据仲裁", "高"],
            ["F-05", "规则与评分", "形成证据分、LLM分、规则分、综合分、风险等级、理由、风险点和建议", "高"],
            ["F-06", "记录与报告", "保存检测及有效证据；支持历史查询、详情、HTML/PDF报告生成下载", "高"],
            ["F-07", "高风险复核", "高风险记录默认不公开；管理员审核后才能决定是否公开", "高"],
            ["F-08", "知识与Prompt", "管理员维护知识库、向量状态和Prompt模板；支持单条向量化和全量重建", "中"],
            ["F-09", "统计与审计", "提供趋势、分布、关键词、用户活动统计和关键操作日志", "中"],
            ["F-10", "采集调度", "可按配置定时采集新闻并记录任务结果，不影响核心检测服务", "低"],
        ],
        widths=[1.4, 2.7, 10.8, 1.6],
        font_size=8.8,
    )

    doc.add_heading("2.1.2 性能、质量与安全要求", level=3)
    add_table(
        doc,
        ["类别", "建议验收指标", "说明"],
        [
            ["正确性", "关键业务验收用例通过率100%；严重/阻断缺陷为0", "以接口、服务、权限和降级场景为重点"],
            ["响应时间", "普通查询P95≤2 s；不含外部服务的本地检索P95≤3 s", "需在目标服务器与代表性数据量上复测"],
            ["智能检测", "外部服务正常时P95≤120 s；超时必须给出可理解错误或降级结果", "受LLM、Embedding和搜索服务影响"],
            ["并发能力", "课程/小规模场景支持20个并发用户，无数据串扰和明显错误率上升", "不是当前已验证结论，是验收目标"],
            ["安全性", "密码哈希、JWT、RBAC、输入校验、访问限流、SSRF防护、密钥外置、审计日志", "生产环境禁止通配CORS和弱密钥"],
            ["可靠性", "数据库操作失败可回滚；外部服务失败可重试/降级；报告与索引失败可追踪", "跨MySQL/Chroma一致性采用应用层补偿"],
            ["可维护性", "分层明确、迁移可追踪、配置外置、关键链路有测试和文档", "避免在API层堆叠业务逻辑"],
            ["备份恢复", "建议RPO≤24 h、RTO≤4 h；至少每季度演练一次恢复", "MySQL、Chroma、报告文件需作为同一恢复集"],
        ],
        widths=[2.5, 6.2, 7.8],
        font_size=8.8,
    )

    doc.add_heading("2.1.3 输入、输出与数据流程", level=3)
    add_bullets(
        doc,
        [
            "主要输入：新闻标题、正文、类别、来源、发布时间、可选URL；知识库新闻/辟谣/事实核查材料；Prompt模板；管理员审核意见。",
            "主要输出：综合可信度分、分项评分、风险等级、判断结论、理由、风险点、关键词、建议、有效证据、检测历史、统计图表、系统日志和PDF报告。",
            "外部接口：DeepSeek对话分析接口、DashScope语义向量接口、可选搜索接口和公开网页内容提取。",
            "内部存储：MySQL保存结构化业务数据；Chroma保存知识项向量；文件系统保存HTML/PDF报告。",
        ],
    )

    doc.add_heading("2.2 目标", level=2)
    add_numbered(
        doc,
        [
            "把分散的新闻检索、来源判断、文本风险检查和报告整理整合为一条可重复、可追踪的辅助核验流程。",
            "以RAG约束模型分析，使结论能够回溯到具体证据，并在本地证据不足时进行受控联网补充。",
            "通过规则评分和人工复核降低单一模型判断的不可解释性与误判风险。",
            "为普通用户提供清晰的结果、历史和报告，为管理员提供知识、Prompt、审核、统计与审计能力。",
            "形成符合软件工程过程的需求、设计、测试、验收和运维文档，为后续扩展或答辩提供证据。",
        ],
    )

    doc.add_heading("2.3 条件、假定和限制", level=2)
    add_table(
        doc,
        ["类别", "内容", "影响"],
        [
            ["组织条件", "按小型项目配置1名负责人/后端、1名前端/测试，可由同一成员兼任文档与部署", "适合课程或小规模试点，不代表企业级轮班运维"],
            ["技术条件", "具备Python、Node.js、MySQL和网络访问；可获得LLM、Embedding与搜索服务凭据", "外部凭据不可用时智能能力下降"],
            ["数据条件", "知识库包含可合法使用、来源明确、标签可解释的新闻与核查材料", "知识覆盖和标签质量直接影响结果"],
            ["部署范围", "优先本地/内网或小规模受控部署；公开互联网部署需增加网关、HTTPS、备份、监控和合规措施", "限制当前结论的适用规模"],
            ["时间假定", "现有原型基础上，4周完成加固、验证、文档和验收准备", "新增大规模爬虫、移动端或多租户将突破范围"],
            ["算法限制", "系统提供辅助判断，不承诺自动确定新闻的客观真伪", "必须展示依据、置信边界和人工复核入口"],
            ["法律限制", "不得未经授权采集、存储或公开个人信息、受版权保护全文和敏感数据", "需最小化采集并建立删除/更正机制"],
        ],
        widths=[2.4, 8.2, 5.9],
        font_size=8.8,
    )

    doc.add_heading("2.4 进行可行性研究的方法", level=2)
    add_body(doc, "本研究采用“标准对照—源码证据—运行验证—方案比较—成本模型—风险复核”的方法。")
    add_numbered(
        doc,
        [
            "按GB/T 8567—2006确定报告提纲，并用GB/T 25000.10—2016的质量特性补充评价维度。",
            "优先使用codebase-memory知识图谱进行架构、实体、路由和调用链发现；对变更影响和非代码配置再进行定向核查。",
            "检查依赖清单、ORM模型、Alembic迁移、API、服务、前端路由和项目设计资料，验证实现与目标的一致性。",
            "执行后端单元/接口测试、前端测试和生产构建，取得可重复的工程证据。",
            "比较RAG＋LLM＋规则、规则系统、LLM直判和第三方SaaS四类方案，并进行加权评价。",
            "采用明确假设的三年成本收益模型和敏感性分析，避免将估算值表述为已发生财务数据。",
            "识别技术、数据、法律、运行和项目管理风险，给出责任、触发条件和缓解措施。",
        ],
    )

    doc.add_heading("2.5 评价尺度", level=2)
    add_table(
        doc,
        ["维度", "权重", "主要判据", "通过条件"],
        [
            ["技术可行性", "25%", "技术成熟度、架构完整性、外部依赖、测试证据、可扩展性", "无不可消除的技术阻断"],
            ["运行可行性", "15%", "角色流程、可用性、培训、运维、异常处理", "目标用户可在合理培训后使用"],
            ["经济可行性", "15%", "一次性投入、经常性支出、可量化与不可量化收益", "基准或三年情景收益/成本>1"],
            ["进度可行性", "10%", "剩余范围、资源、里程碑和关键路径", "可在计划窗口内验收"],
            ["法律与社会可行性", "15%", "隐私、数据、版权、内容治理、使用边界", "不存在原则性禁止，合规条件可落实"],
            ["安全与可靠性", "10%", "鉴权、最小权限、审计、备份、降级和恢复", "重大风险有控制与验收项"],
            ["维护可行性", "10%", "分层、配置、迁移、文档、测试和供应商替换", "维护工作量与团队能力匹配"],
        ],
        widths=[3.0, 1.5, 8.1, 3.9],
        font_size=8.7,
    )


def build_chapter_3(doc: Document) -> None:
    doc.add_heading("3 对现有系统的分析", level=1)
    add_body(
        doc,
        "本章所称“现有系统”包括两部分：一是项目建设前以人工搜索、人工判断和手工整理报告为主的业务方式；二是当前已形成但尚需加固的原型基线。二者并列分析，可以避免把原型现状误写为已完成生产验收。",
    )

    doc.add_heading("3.1 处理流程和数据流程", level=2)
    doc.add_heading("3.1.1 原有人工处理流程", level=3)
    add_numbered(
        doc,
        [
            "接收待核验新闻标题、正文或链接。",
            "在搜索引擎、媒体网站和辟谣平台分别检索相似信息。",
            "人工阅读来源、时间、正文和评论，判断证据是否可信。",
            "按个人经验给出“可信/存疑/谣言”结论。",
            "用文档或表格手工记录理由、链接和结论，需要时再制作报告。",
        ],
    )
    add_note(doc, "主要问题", "证据来源分散、核验标准不统一、重复检索耗时、结论难复现、历史记录难统计，且容易因时间压力遗漏反证。", kind="warning")

    doc.add_heading("3.1.2 当前原型处理流程", level=3)
    add_body(
        doc,
        "知识图谱对检测主函数进行双向调用追踪后确认，现有原型已实现文本清洗、关键词提取、本地知识检索、证据不足判定、联网证据补充、证据合并、规则评分、LLM分析、风险分级、记录保存和结果展示等环节，并提供外部服务失败时的重试或降级路径。",
    )
    add_figure(doc, FLOW_IMAGE, "图3-1 当前原型的新闻可信度评估主流程", width_inches=4.8)

    doc.add_heading("3.2 工作负荷", level=2)
    add_table(
        doc,
        ["工作项", "人工方式", "当前原型", "预期变化"],
        [
            ["单条新闻初筛", "约15～30分钟，取决于搜索和阅读量", "自动组织证据与分项结果，人工复核约5～10分钟", "减少重复搜索和整理时间"],
            ["历史追踪", "依赖个人表格或文档", "统一保存检测记录、证据、评分和审核状态", "可按用户、时间和风险筛选"],
            ["报告制作", "手工复制证据和结论", "模板化生成HTML/PDF", "显著减少排版时间"],
            ["高风险发布", "可能缺少一致审批流程", "待审→通过/驳回→公开/取消公开", "降低未经复核直接发布风险"],
            ["统计汇总", "人工统计，时效性差", "按趋势、风险、类别、关键词和用户活动聚合", "支持管理和答辩展示"],
        ],
        widths=[3.0, 4.3, 5.2, 4.0],
        font_size=8.8,
    )
    add_body(doc, "基准经济情景假定每月处理300条新闻，人工方式平均15分钟/条，系统辅助后平均5分钟/条，每月可节省约50工时。该数值仅用于可行性估算，实际应通过试运行计时修正。")

    doc.add_heading("3.3 费用开支", level=2)
    add_body(doc, "人工方式的主要成本是持续的人力搜索、阅读、记录和报告制作；当前原型的主要成本转化为一次性开发与文档投入，以及服务器、数据库备份、外部模型/向量/搜索API和维护支出。若只用于本地课程演示，可利用既有设备并使用小额API配额，现金支出较低；若公开部署，安全、监控和合规成本显著增加。")

    doc.add_heading("3.4 人员", level=2)
    add_table(
        doc,
        ["角色", "现状/需求", "主要职责"],
        [
            ["项目负责人/需求", "1人，可兼任后端", "范围控制、业务口径、计划、验收和风险决策"],
            ["后端与AI", "1人", "FastAPI、MySQL、Chroma、RAG、外部API、评分与报告"],
            ["前端与交互", "1人，可兼任测试", "Vue页面、权限导航、数据展示、错误提示和可访问性"],
            ["测试与文档", "0.5～1人，可由成员兼任", "测试、构建、缺陷记录、用户文档和验收材料"],
            ["领域复核", "按需邀请", "审核样例、事实核查口径、法律与内容发布边界"],
        ],
        widths=[3.2, 3.3, 10.0],
    )

    doc.add_heading("3.5 设备", level=2)
    add_table(
        doc,
        ["设备/资源", "最低建议", "现有可用性"],
        [
            ["开发终端", "4核CPU、16 GB内存、20 GB可用空间", "普通开发电脑可满足"],
            ["试运行服务器", "2～4 vCPU、4～8 GB内存、50 GB SSD", "可使用本地服务器或云主机"],
            ["数据库", "MySQL 8.x，独立账号和定期备份", "开源软件，部署成熟"],
            ["向量存储", "Chroma本地持久化目录，容量随知识库增长", "无需独立集群即可运行"],
            ["网络", "可访问LLM、Embedding和搜索服务；生产环境使用HTTPS", "受运营商和第三方服务可用性影响"],
        ],
        widths=[3.3, 6.0, 7.2],
    )

    doc.add_heading("3.6 局限性", level=2)
    add_bullets(
        doc,
        [
            "人工方式依赖个人经验，标准、证据和结论难统一，无法稳定复现。",
            "当前原型的准确性受知识库覆盖、向量质量、外部搜索质量和模型输出稳定性共同影响。",
            "模型可能产生幻觉或过度概括；自动评分不能代替权威核查，尤其不能用于医疗、法律、金融等高风险决策。",
            "MySQL与Chroma之间不存在分布式事务，当前通过状态字段、重试和补偿降低不一致风险。",
            "报告文件使用本地文件系统，当前没有对象存储、跨机容灾和自动生命周期管理。",
            "限流主要基于进程内存；多实例部署时需替换为共享限流或网关策略。",
            "项目没有完整CI/CD和容器化基线；生产环境还需自动化质量门禁、监控和发布回滚。",
            "现有测试能够证明功能基线，但尚未形成代表性大数据量、长时间和高并发性能报告。",
        ],
    )


def build_chapter_4(doc: Document) -> None:
    doc.add_heading("4 所建议的系统", level=1)
    doc.add_heading("4.1 对所建议系统的说明", level=2)
    add_body(
        doc,
        "建议继续采用前后端分离、后端分层的单体架构：Vue 3负责用户与管理员界面；FastAPI提供REST接口、鉴权和业务编排；SQLAlchemy/Alembic管理MySQL结构化数据；Chroma负责向量检索；DeepSeek、DashScope和可选搜索服务作为受控外部能力；本地目录生成HTML/PDF报告。对课程/小规模试点而言，该方案复杂度适中，能够覆盖完整业务闭环。",
    )
    add_figure(doc, ARCH_IMAGE, "图4-1 所建议系统总体架构", width_inches=6.25)
    add_table(
        doc,
        ["层次", "技术/组件", "职责"],
        [
            ["表现与交互", "Vue 3、Vue Router、Pinia、Axios、Element Plus、ECharts", "页面、状态、权限导航、图表和结果解释"],
            ["接口与业务", "FastAPI、Pydantic、Service、CRUD", "输入校验、鉴权、检测编排、知识管理、审核、统计和报告"],
            ["结构化数据", "MySQL、SQLAlchemy、Alembic", "用户、知识、检测、证据、Prompt、报告、日志和采集任务"],
            ["向量数据", "Chroma、Embedding", "知识项向量、元数据和语义相似检索"],
            ["智能与外部证据", "DeepSeek、DashScope、搜索服务、网页提取", "证据分析、向量化、联网补充和内容提取"],
            ["文档与审计", "Jinja2、xhtml2pdf、系统日志", "可下载报告与关键操作追踪"],
        ],
        widths=[3.0, 6.4, 7.1],
        font_size=8.7,
    )

    doc.add_heading("4.2 处理流程和数据流程", level=2)
    add_numbered(
        doc,
        [
            "接收文本或安全提取URL内容，执行长度、格式、空值和危险地址检查。",
            "清洗标题与正文，提取关键词，组合RAG查询文本。",
            "调用Embedding生成查询向量，在Chroma中召回Top-K本地知识证据。",
            "根据最高相似度、有效证据数量和配置阈值判断是否触发联网补充。",
            "合并、去重并规范化本地证据和网络证据，生成来源中立的候选池。",
            "调用LLM执行证据相关性、质量、立场和拒绝原因分析；契约失败时进行一次聚焦重试。",
            "计算证据分、LLM分和规则分，形成综合可信度分和风险等级；LLM不可用时显式降级。",
            "在MySQL事务中保存检测记录和最终有效证据；登录用户可在历史中追踪。",
            "高风险记录进入管理员审核队列；只有审核通过并明确公开的记录才面向用户展示。",
            "按需生成报告，统计和日志模块提供运营视图与审计轨迹。",
        ],
    )
    add_figure(doc, STORE_IMAGE, "图4-2 MySQL与Chroma协同及一致性边界", width_inches=4.75)

    doc.add_heading("4.3 改进之处", level=2)
    add_table(
        doc,
        ["对比维度", "原有方式", "建议系统改进"],
        [
            ["证据获取", "人工多站点检索", "本地RAG优先，证据不足时自动联网补充"],
            ["判断依据", "依赖个人经验", "证据质量＋LLM分析＋可解释规则的组合判断"],
            ["可追溯性", "链接和理由分散", "记录输入、分项评分、有效证据、审核和报告"],
            ["风险控制", "可能直接发布结论", "高风险记录默认不公开，管理员审核后再决定"],
            ["异常处理", "失败后从头重做", "搜索失败保留本地证据；LLM失败显式降级；数据库失败回滚"],
            ["知识复用", "每次从零搜索", "知识项结构化管理和向量化复用"],
            ["统计审计", "手工汇总", "自动趋势、分布、关键词、用户活动和系统日志"],
        ],
        widths=[3.0, 5.1, 8.4],
        font_size=8.8,
    )

    doc.add_heading("4.4 影响", level=2)
    doc.add_heading("4.4.1 对设备的影响", level=3)
    add_body(doc, "开发阶段可复用现有电脑。试运行需为MySQL、Chroma和报告目录预留稳定磁盘，启用自动备份；知识库、日志和报告增长时应监控容量。若并发或数据量明显上升，可将数据库、向量库和文件存储拆分。")

    doc.add_heading("4.4.2 对软件的影响", level=3)
    add_body(doc, "需维护Python和Node依赖、MySQL版本、Alembic迁移、环境变量和外部API契约。正式发布前应固定依赖版本、建立漏洞与许可证检查、配置测试/生产环境隔离，并对模型或Embedding切换执行回归测试和向量索引重建。")

    doc.add_heading("4.4.3 对用户单位机构的影响", level=3)
    add_body(doc, "需要明确系统负责人、管理员和内容复核责任人；制定账号权限、知识入库、Prompt变更、高风险公开、数据删除和异常处置流程。自动评分不得直接作为对个人、机构或媒体作出不利决定的唯一依据。")

    doc.add_heading("4.4.4 对系统运行过程的影响", level=3)
    add_body(doc, "运行过程从“人工自由检索”转为“系统自动初筛＋人工复核”。需要日常检查外部API、失败任务、向量同步状态、数据库备份、磁盘容量和审计日志；重大模型、Prompt或评分规则变更必须留痕并经过样例回归。")

    doc.add_heading("4.4.5 对开发的影响", level=3)
    add_body(doc, "开发需遵守API—Service—CRUD—Model分层，数据库结构通过Alembic变更，敏感配置只进入环境变量。新增检测行为应同时更新测试、接口说明、风险说明和验收用例，避免文档与实现分离。")

    doc.add_heading("4.4.6 对地点和设施的影响", level=3)
    add_body(doc, "本地/内网部署无需专用机房，但需稳定网络、电源和受控访问。公开部署建议采用云主机或受管环境，配置HTTPS、反向代理/网关、防火墙、安全组、日志保留和异地备份。")

    doc.add_heading("4.4.7 对经费开支的影响", level=3)
    add_body(doc, "主要新增支出为工程加固工时、云资源、备份、模型/向量/搜索API及持续维护。系统本身采用开源框架，不产生核心软件许可费；外部API用量是最显著的可变成本，应配置预算、限额、缓存和降级策略。")

    doc.add_heading("4.5 局限性", level=2)
    add_bullets(
        doc,
        [
            "系统评估的是‘在当前证据下的可信度’，不能证明新闻在客观世界中绝对真或假。",
            "对新发生、地方性、专业性或证据稀缺事件，知识库和搜索可能无法提供足够依据。",
            "相似度高不等于事实一致；因此候选证据必须经过质量与立场仲裁。",
            "第三方模型、向量和搜索服务的价格、限额、内容策略与可用性可能变化。",
            "公开网络内容可能包含版权、个人信息、错误或恶意页面，必须限制采集和展示范围。",
            "当前方案定位于课程与小规模辅助核验，不直接满足大规模舆情监测或关键基础设施要求。",
        ],
    )

    doc.add_heading("4.6 技术条件方面的可行性", level=2)
    doc.add_heading("4.6.1 技术成熟度", level=3)
    add_body(doc, "Vue、FastAPI、SQLAlchemy、MySQL和JWT均为成熟技术；Chroma适合本地向量检索；DeepSeek、DashScope和搜索API通过标准HTTP调用，可被替换或降级。建议方案不存在必须自研底层模型或数据库的技术障碍。")

    doc.add_heading("4.6.2 代码知识图谱证据", level=3)
    add_table(
        doc,
        ["指标", "结果", "说明"],
        [
            ["图节点/关系", "3,073 / 8,131", "覆盖函数、方法、类、模块、路由、变量、环境变量等"],
            ["文件节点", "250", "Python、Vue、JavaScript、HTML、CSS、SQL"],
            ["函数/方法", "603 / 390", "核心检测函数已完成双向调用追踪"],
            ["类", "218", "含ORM、Schema、服务异常和测试类"],
            ["路由节点", "134", "包含后端路由、前端调用路径和测试请求路径"],
            ["核心数据实体", "8", "User、KnowledgeItem、DetectionRecord、EvidenceMatch、PromptTemplate、Report、SystemLog、CrawlTask"],
            ["测试映射关系", "110", "知识图谱识别到的TESTS关系，不等同于测试用例总数"],
        ],
        widths=[3.6, 3.0, 9.9],
    )

    doc.add_heading("4.6.3 实际验证结果", level=3)
    add_table(
        doc,
        ["验证项", "命令/方式", "结果", "判定"],
        [
            ["后端测试", "python -m unittest discover -s tests -p test_*.py", "392项，全部通过；37.947 s", "通过"],
            ["前端测试", "npm test", "14项，全部通过", "通过"],
            ["生产构建", "npm run build", "1,650个模块转换，构建成功", "通过（有非阻断告警）"],
            ["构建告警", "Vite/Rollup输出", "ECharts块约519 kB；部分第三方PURE注释被移除", "验收前可接受，生产优化项"],
            ["图谱状态", "codebase-memory index_status", "ready；能够执行架构、调用链和变更影响查询", "通过"],
        ],
        widths=[2.8, 5.2, 5.6, 2.9],
        font_size=8.6,
    )
    add_note(doc, "技术结论", "原型、测试和构建结果证明核心技术路线可实现。技术可行性不等于生产就绪；容量、备份恢复、安全配置和外部服务SLA仍须在目标环境验收。", kind="success")


def build_chapter_5(doc: Document) -> None:
    doc.add_heading("5 可选择的其他系统方案", level=1)
    doc.add_heading("5.1 方案A：纯规则与关键词系统", level=2)
    add_body(doc, "仅使用来源白名单、关键词、情绪词、绝对化表述和固定阈值评分，不使用向量检索与大语言模型。")
    add_table(
        doc,
        ["优点", "缺点", "适用场景", "结论"],
        [["成本低、速度快、结果稳定、易解释", "难理解语义、对改写和新型谣言适应差、证据利用弱", "低成本预筛、外部API中断时降级", "保留为组成部分，不作为主方案"]],
        widths=[4.2, 5.3, 4.1, 2.9],
        font_size=8.7,
    )

    doc.add_heading("5.2 方案B：大语言模型直接判断", level=2)
    add_body(doc, "将新闻标题和正文直接提交给大语言模型，由模型输出分数与结论，不建设本地知识库，也不执行证据检索。")
    add_table(
        doc,
        ["优点", "缺点", "适用场景", "结论"],
        [["开发快、语义理解强、交互灵活", "证据不可追溯、幻觉风险高、成本和供应商依赖大、重复结果可能不稳定", "原型演示或无知识库的临时分析", "不满足可解释和可追溯目标，拒绝"]],
        widths=[4.2, 5.3, 4.1, 2.9],
        font_size=8.7,
    )

    doc.add_heading("5.3 方案C：采购第三方事实核查SaaS", level=2)
    add_body(doc, "采购现成新闻识别或舆情服务，通过第三方界面或API获得标签和报告。")
    add_table(
        doc,
        ["优点", "缺点", "适用场景", "结论"],
        [["上线快、可能已有数据与运营团队", "成本与合同受制于供应商、数据出境/隐私与接口锁定风险、难展示自研过程", "预算充足且有合规采购能力的机构", "可作为外部证据源，不适合作为本项目主体"]],
        widths=[4.2, 5.3, 4.1, 2.9],
        font_size=8.7,
    )

    doc.add_heading("5.4 方案比较与推荐", level=2)
    add_table(
        doc,
        ["评价项（权重）", "推荐：RAG＋LLM＋规则", "A 纯规则", "B LLM直判", "C 第三方SaaS"],
        [
            ["功能覆盖（25%）", "5.0", "3.0", "3.5", "4.0"],
            ["准确性/可解释性（25%）", "4.5", "2.5", "3.0", "3.5"],
            ["工程风险（15%）", "4.0", "4.5", "3.0", "4.0"],
            ["数据自主（15%）", "4.5", "5.0", "2.5", "2.0"],
            ["成本（10%）", "3.5", "5.0", "3.0", "2.5"],
            ["扩展性（10%）", "4.5", "3.0", "4.0", "2.5"],
            ["加权总分（5分制）", "4.43", "3.60", "3.18", "3.30"],
        ],
        widths=[4.6, 3.4, 2.7, 2.7, 3.1],
        font_size=8.6,
    )
    add_note(doc, "推荐方案", "采用RAG＋LLM＋规则评分＋人工复核的混合方案；纯规则作为降级通道，第三方服务只作为可替换能力，不形成单点锁定。", kind="success")


def build_chapter_6(doc: Document) -> None:
    doc.add_heading("6 投资及效益分析", level=1)
    add_note(doc, "估算口径", "以下金额为人民币、含税的教学/小规模试点估算，不是采购报价或已发生财务数据。人工按等价成本800元/人日计算；实际项目应以部署规模、供应商价格和组织薪酬重新测算。", kind="info")

    doc.add_heading("6.1 支出", level=2)
    doc.add_heading("6.1.1 基本建设投资", level=3)
    add_table(
        doc,
        ["项目", "数量/工时", "单价", "金额（元）", "说明"],
        [
            ["需求与架构复核", "5人日", "800", "4,000", "范围、数据、接口、风险与验收口径"],
            ["后端/AI加固", "12人日", "800", "9,600", "外部服务、降级、数据一致性、安全与日志"],
            ["前端与交互完善", "8人日", "800", "6,400", "结果解释、异常状态、后台操作与可用性"],
            ["测试、文档与验收", "8人日", "800", "6,400", "回归、性能、安全、文档和验收材料"],
            ["部署与培训", "3人日", "800", "2,400", "环境、备份、恢复演练与用户培训"],
            ["硬件购置", "0", "—", "0", "复用现有开发设备；云资源计入经常性支出"],
            ["合计", "36人日", "—", "28,800", "一次性等价投入"],
        ],
        widths=[3.7, 2.2, 1.8, 2.5, 6.3],
        font_size=8.6,
    )

    doc.add_heading("6.1.2 其他一次性支出", level=3)
    add_body(doc, "若用于课程/校内验收，域名、测评和采购手续可不发生；若公开部署，应另行预算域名备案、渗透测试、合规咨询、数据授权和安全整改。由于主体与范围未确定，本报告不将其计入基准金额，而作为部署前专项预算。")

    doc.add_heading("6.1.3 非一次性支出", level=3)
    add_table(
        doc,
        ["项目", "年费用（元）", "估算说明"],
        [
            ["云主机/网络", "2,400", "小规模2～4 vCPU实例或等价资源"],
            ["数据库、备份与存储", "1,200", "备份空间、磁盘扩容和恢复保留"],
            ["LLM/Embedding/搜索API", "3,600", "按低至中等调用量并设置预算上限"],
            ["域名、证书与基础监控", "400", "证书可用免费方案，费用主要为域名/监控"],
            ["维护与小版本升级", "4,000", "约5人日/年"],
            ["合计", "11,600", "基准年度经常性支出"],
        ],
        widths=[5.0, 3.0, 8.5],
    )

    doc.add_heading("6.2 收益", level=2)
    doc.add_heading("6.2.1 一次性收益", level=3)
    add_bullets(
        doc,
        [
            "形成可复用的前后端、数据库、RAG、LLM、审核、统计和报告完整工程资产。",
            "形成国标化文档、测试用例、数据库迁移和知识库管理流程，降低后续同类项目启动成本。",
            "提升课程答辩、作品展示、团队培训和技术验证的完整度。",
        ],
    )

    doc.add_heading("6.2.2 非一次性收益", level=3)
    add_table(
        doc,
        ["收益项", "计算假定", "年收益（元）"],
        [
            ["核验工时节省", "300条/月×节省10分钟×12月×80元/小时", "48,000"],
            ["报告整理与统计复用", "按每年节省60小时×80元/小时", "4,800"],
            ["合计", "基准情景", "52,800"],
        ],
        widths=[5.1, 7.8, 3.6],
    )

    doc.add_heading("6.2.3 不可定量收益", level=3)
    add_bullets(
        doc,
        [
            "核验流程和证据口径更加一致，降低个人经验差异。",
            "保留证据、评分、审核和日志，提高可追溯性与复盘能力。",
            "高风险公开经过人工审核，降低未经核实信息二次扩散的管理风险。",
            "积累高质量知识库和测试样例，为后续算法评估与模型替换提供基础。",
            "培养团队在RAG、LLM治理、前后端工程、测试和软件文档方面的综合能力。",
        ],
    )

    doc.add_heading("6.3 收益/投资比", level=2)
    add_table(
        doc,
        ["指标", "计算", "结果"],
        [
            ["首年总成本", "一次性28,800＋年度11,600", "40,400元"],
            ["首年收益/成本", "52,800÷40,400", "1.31"],
            ["三年总成本", "28,800＋11,600×3", "63,600元"],
            ["三年总收益", "52,800×3", "158,400元"],
            ["三年收益/成本", "158,400÷63,600", "2.49"],
            ["三年净收益", "158,400－63,600", "94,800元"],
        ],
        widths=[4.0, 7.5, 5.0],
    )

    doc.add_heading("6.4 投资回收周期", level=2)
    add_body(doc, "基准年度净收益为52,800－11,600＝41,200元。按一次性投入28,800元计算，静态投资回收期约为28,800÷41,200＝0.70年，即约8.4个月。该结果对每月处理量和单位人工成本较敏感。")

    doc.add_heading("6.5 敏感性分析", level=2)
    add_table(
        doc,
        ["情景", "年收益", "年经常性支出", "年净收益", "静态回收期", "判断"],
        [
            ["低使用量：150条/月", "26,400", "11,600", "14,800", "1.95年", "三年仍可回收，经济性偏弱"],
            ["基准：300条/月", "52,800", "11,600", "41,200", "0.70年", "经济可行"],
            ["API费用上升50%", "52,800", "13,400", "39,400", "0.73年", "影响有限，但需预算控制"],
            ["高使用量：600条/月", "105,600", "13,400", "92,200", "0.31年", "经济性明显，但需扩容验证"],
        ],
        widths=[3.8, 2.4, 2.7, 2.4, 2.3, 2.9],
        font_size=8.3,
    )
    add_note(doc, "经济结论", "在每月约300条的基准使用量下，三年收益/成本为2.49，经济上可行；即使使用量减半，三年仍有回收可能。若仅用于教学展示，应将主要收益理解为工程资产、学习与答辩价值。", kind="success")


def build_chapter_7(doc: Document) -> None:
    doc.add_heading("7 社会因素方面的可行性", level=1)
    doc.add_heading("7.1 法律方面的可行性", level=2)
    add_body(
        doc,
        "本系统的技术路线本身不存在原则性禁止，但新闻、网页、用户信息和模型输出均可能触及网络安全、数据安全、个人信息保护、著作权和生成式人工智能治理要求。法律可行性的前提是明确处理目的和部署主体，并将下列控制落实到产品、流程和合同。",
    )
    add_table(
        doc,
        ["领域", "主要风险", "必要控制"],
        [
            ["个人信息", "新闻正文、URL内容、账号、日志或报告可能包含个人信息", "目的明确、最小必要、告知同意/合法基础、访问控制、保留期限、查询更正删除渠道"],
            ["数据安全", "数据库、向量库、报告和日志泄漏、篡改或丢失", "分类分级、最小权限、加密传输、备份恢复、审计、事件处置和供应商管理"],
            ["网络安全", "弱密钥、通配CORS、接口滥用、SSRF、恶意文件或越权", "HTTPS、强密钥、白名单、输入校验、限流、SSRF防护、依赖更新和安全测试"],
            ["版权与网页采集", "抓取或长期存储受保护全文、违反网站条款、报告二次传播", "优先保存必要摘要与来源链接，限制批量抓取，尊重robots/条款，取得授权或采用法定许可范围"],
            ["内容治理", "自动把未经证实内容标注为谣言，损害个人或机构权益", "使用‘辅助评估’措辞、展示证据与不确定性、高风险公开前人工审核、提供申诉与更正机制"],
            ["生成式AI", "公开提供生成式服务时可能适用暂行办法与标识要求", "确认服务属性；落实安全、透明、投诉处置和必要标识，不隐瞒AI参与"],
            ["第三方服务", "新闻文本或个人信息传给模型/搜索供应商", "审查隐私政策和数据处理条款，控制传输字段，禁止发送敏感信息，保留可替换方案"],
        ],
        widths=[2.6, 6.2, 7.7],
        font_size=8.3,
    )
    add_note(doc, "法律边界", "本报告不是法律意见。公开上线、面向未成年人、处理敏感个人信息、形成规模化舆情分析或跨境传输数据时，应进行专项法律与安全评估。", kind="danger")

    doc.add_heading("7.2 使用方面的可行性", level=2)
    doc.add_heading("7.2.1 用户接受度", level=3)
    add_body(doc, "系统采用浏览器访问，不要求用户安装专用客户端；检测页、结果页、历史页和管理员后台均采用常见Web交互。评分拆分、证据列表、风险点和建议能够帮助用户理解结论，使用门槛较低。")

    doc.add_heading("7.2.2 培训与运行制度", level=3)
    add_table(
        doc,
        ["对象", "培训内容", "建议时长"],
        [
            ["普通用户", "新闻输入、结果理解、证据核验、报告下载、隐私注意事项", "30～45分钟"],
            ["管理员", "知识入库、向量重建、Prompt变更、高风险审核、报告和日志", "2小时＋实操"],
            ["维护人员", "部署配置、迁移、备份恢复、外部API、日志排障和安全更新", "0.5～1天"],
        ],
        widths=[3.2, 9.8, 3.5],
    )

    doc.add_heading("7.2.3 伦理与社会影响", level=3)
    add_bullets(
        doc,
        [
            "积极影响：降低初筛成本、促进证据意识、提升信息素养、为事实核查提供可追溯工具。",
            "潜在负面影响：误判造成名誉损害，用户对分数产生自动化依赖，高风险样例公开造成二次传播。",
            "控制原则：以人为中心、可解释、可申诉、可更正、必要人工复核，不以模型结论取代专业责任。",
            "公平性要求：建立多类别、多来源、多时间段测试集，监控模型和知识库对特定来源或群体的系统性偏差。",
        ],
    )


def build_chapter_8(doc: Document) -> None:
    doc.add_heading("8 结论", level=1)
    add_table(
        doc,
        ["评价维度", "权重", "评分（5分）", "折算分", "结论"],
        [
            ["技术可行性", "25%", "4.6", "23.0", "原型完整，测试与构建通过"],
            ["运行可行性", "15%", "4.3", "12.9", "流程清晰，培训成本低"],
            ["经济可行性", "15%", "4.0", "12.0", "基准三年收益/成本2.49"],
            ["进度可行性", "10%", "4.5", "9.0", "基于原型，4周可完成验收加固"],
            ["法律与社会", "15%", "3.6", "10.8", "可行但需落实隐私、版权和内容治理"],
            ["安全与可靠性", "10%", "3.8", "7.6", "已有基础控制，生产加固与恢复验证待完成"],
            ["维护可行性", "10%", "4.0", "8.0", "分层、迁移、配置和测试基础良好"],
            ["综合", "100%", "—", "83.3", "有条件可行"],
        ],
        widths=[3.1, 1.7, 2.4, 2.0, 7.3],
        font_size=8.6,
    )
    add_note(
        doc,
        "最终结论",
        "建议批准项目继续进入‘工程加固—验收测试—受控部署’阶段。推荐采用RAG＋LLM＋规则评分＋人工复核方案，不建议采用LLM无证据直判。",
        kind="success",
    )
    add_body(doc, "批准继续实施应同时满足以下前置条件：")
    add_numbered(
        doc,
        [
            "冻结验收范围和评分/风险口径，建立代表性真值测试集，并记录人工标注依据。",
            "在目标环境完成性能、并发、长稳、安全和备份恢复测试，普通查询与智能检测达到约定指标。",
            "生产环境启用HTTPS、强随机密钥、明确CORS白名单、最小权限数据库账号、集中限流和审计。",
            "完善MySQL、Chroma和报告文件的一致备份、恢复和定期演练；对向量同步失败建立可视化告警。",
            "对知识材料、联网采集、个人信息和第三方API完成来源、授权、最小化与保留期限审查。",
            "所有自动结论均标注辅助性质；高风险内容公开前必须人工审核，并提供更正/撤回流程。",
            "为外部模型、Embedding和搜索服务配置超时、重试、预算上限、降级和替换预案。",
            "将392项后端测试、14项前端测试和生产构建纳入自动化质量门禁，修复或登记构建体积告警。",
        ],
    )

    doc.add_heading("8.1 建议实施计划", level=2)
    add_table(
        doc,
        ["阶段", "周期", "主要工作", "退出准则"],
        [
            ["基线冻结", "第1周", "确认需求、数据口径、验收用例、法律边界和风险责任人", "范围、指标和测试集批准"],
            ["工程加固", "第2周", "安全配置、外部API韧性、备份、监控、跨存储补偿和前端异常状态", "重大风险均有实现与测试"],
            ["专项验证", "第3周", "回归、性能、并发、安全、恢复、兼容性和模型样例评估", "阻断/严重缺陷为0"],
            ["文档与验收", "第4周", "完成五类软件文档、培训、演示脚本、缺陷闭环和验收会议", "验收材料签署、版本受控"],
        ],
        widths=[2.7, 2.0, 7.8, 4.0],
        font_size=8.7,
    )


def build_appendices(doc: Document) -> None:
    page_break(doc)
    doc.add_heading("附录A 可行性风险登记表", level=1)
    add_table(
        doc,
        ["风险", "概率", "影响", "等级", "主要缓解措施", "责任角色"],
        [
            ["知识库覆盖不足或标签错误", "4", "5", "20 高", "来源分级、双人抽检、真值集、定期更新、保留反证", "领域复核/管理员"],
            ["LLM幻觉或证据仲裁错误", "4", "5", "20 高", "结构化契约、一次聚焦重试、规则交叉验证、人工复核、明确免责声明", "AI/后端"],
            ["外部API不可用或限额", "4", "4", "16 高", "超时、重试、熔断、预算限额、降级和供应商替换", "后端/运维"],
            ["个人信息或敏感内容泄漏", "3", "5", "15 高", "最小化采集、脱敏、权限、加密、保留期限、删除与事件响应", "负责人/安全"],
            ["版权或网页采集合规问题", "3", "4", "12 中高", "保存必要摘要和链接、限制抓取、授权审查、删除通道", "负责人/管理员"],
            ["MySQL与Chroma不一致", "3", "4", "12 中高", "同步状态、重试补偿、全量重建、对账与告警", "后端/运维"],
            ["报告/日志/向量数据丢失", "3", "4", "12 中高", "统一备份集、异地副本、恢复演练、容量监控", "运维"],
            ["调用成本超预算", "3", "3", "9 中", "配额、缓存、短文本、分层模型、低价值请求限流", "负责人/后端"],
            ["前端大分块影响加载", "2", "3", "6 中", "ECharts按需加载、动态拆分、压缩与缓存", "前端"],
            ["成员变动或知识集中", "2", "4", "8 中", "文档、代码评审、运行手册、交叉培训和受控版本", "项目负责人"],
        ],
        widths=[3.4, 1.1, 1.1, 1.5, 7.2, 2.2],
        font_size=7.7,
    )
    add_body(doc, "注：概率和影响采用1～5级；风险等级＝概率×影响。15～25为高，10～14为中高，5～9为中，1～4为低。")

    doc.add_heading("附录B 软件与数据资源清单", level=1)
    add_table(
        doc,
        ["类别", "资源", "版本/现状", "用途"],
        [
            ["后端", "FastAPI / Uvicorn", "0.111.0 / 0.30.1", "REST接口与ASGI运行"],
            ["数据", "SQLAlchemy / Alembic / PyMySQL", "2.0.31 / 1.13.2 / 1.1.1", "ORM、迁移和MySQL连接"],
            ["安全", "python-jose / passlib / bcrypt", "3.3.0 / 1.7.4 / 4.0.1", "JWT与密码哈希"],
            ["向量", "Chroma", ">=1.0,<2.0", "本地向量库"],
            ["报告", "Jinja2 / xhtml2pdf", "3.1.6 / 0.2.17", "HTML与PDF报告"],
            ["前端", "Vue / Vite / Vue Router / Pinia", "3.5.13 / 6.x / 4.5.0 / 2.3.0", "界面、构建、路由和状态"],
            ["可视化", "Element Plus / ECharts", "2.9.1 / 5.6.0", "组件与统计图表"],
            ["外部服务", "DeepSeek / DashScope / 搜索服务", "环境变量配置", "分析、Embedding和联网证据"],
            ["结构化库", "MySQL", "建议8.x、utf8mb4", "业务主数据"],
            ["文件", "报告目录", "本地持久化", "HTML/PDF文件"],
        ],
        widths=[2.5, 5.2, 4.0, 4.8],
        font_size=8.4,
    )

    doc.add_heading("附录C 国标提纲符合性对照", level=1)
    add_table(
        doc,
        ["GB/T 8567—2006要求", "本报告位置", "符合性说明"],
        [
            ["1 引言", "第1章", "含目的、背景、定义和参考资料"],
            ["2 可行性研究前提", "第2章", "含要求、目标、限制、方法和评价尺度"],
            ["3 对现有系统的分析", "第3章", "含流程、负荷、费用、人员、设备和局限"],
            ["4 所建议的系统", "第4章", "含系统说明、流程、改进、影响、局限和技术可行性"],
            ["5 可选择的其他方案", "第5章", "比较三类备选方案并给出加权结论"],
            ["6 投资及效益分析", "第6章", "含支出、收益、收益/投资、回收期和敏感性"],
            ["7 社会因素可行性", "第7章", "含法律与使用可行性"],
            ["8 结论", "第8章", "给出有条件可行结论、条件与实施计划"],
        ],
        widths=[5.0, 3.1, 8.4],
        font_size=8.7,
    )

    doc.add_heading("附录D 证据与估算声明", level=1)
    add_bullets(
        doc,
        [
            "源码事实来自2026年6月20日项目工作区；知识图谱用于代码结构发现，变更影响和非代码资料另行核对。",
            "测试数字来自本次实际命令输出：后端392项通过，前端14项通过，前端生产构建成功。",
            "性能、并发、RPO/RTO等为建议验收目标，不是尚未执行的测试结论。",
            "成本、收益、处理量和人工单价均为显式假设，仅用于方案比较；实际立项前应由项目负责人和财务复核。",
            "法律合规内容为工程风险识别，不构成法律意见。",
        ],
    )


def enable_update_fields(doc: Document) -> None:
    settings = doc.settings.element
    update_fields = settings.find(qn("w:updateFields"))
    if update_fields is None:
        update_fields = OxmlElement("w:updateFields")
        settings.append(update_fields)
    update_fields.set(qn("w:val"), "true")


def build_document() -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    doc = Document()
    configure_styles(doc)
    configure_section(doc.sections[0], header_footer=False)
    build_cover(doc)

    front_section = doc.add_section(WD_SECTION.NEW_PAGE)
    configure_section(front_section, header_footer=True, page_format="lowerRoman")
    build_document_control(doc)
    build_abstract(doc)
    build_toc(doc)

    body_section = doc.add_section(WD_SECTION.NEW_PAGE)
    configure_section(body_section, header_footer=True, page_format="decimal")
    build_chapter_1(doc)
    build_chapter_2(doc)
    build_chapter_3(doc)
    build_chapter_4(doc)
    build_chapter_5(doc)
    build_chapter_6(doc)
    build_chapter_7(doc)
    build_chapter_8(doc)
    build_appendices(doc)
    enable_update_fields(doc)

    doc.core_properties.title = f"《{PROJECT_TITLE}》{DOC_TITLE}"
    doc.core_properties.subject = "软件工程可行性研究报告"
    doc.core_properties.author = f"《{PROJECT_TITLE}》项目组"
    doc.core_properties.keywords = "GB/T 8567-2006, 可行性研究, RAG, 大语言模型, 新闻真伪鉴别"
    doc.core_properties.comments = "基于源码、知识图谱和实际测试结果编制"
    doc.save(OUTPUT_PATH)
    return OUTPUT_PATH


if __name__ == "__main__":
    print(build_document())
