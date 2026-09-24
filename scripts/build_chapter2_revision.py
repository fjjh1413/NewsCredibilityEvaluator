from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Iterable

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get("CHAPTER2_SOURCE_DOCX", ROOT / ".artifacts" / "docs" / "input" / "chapter4.docx"))
OUTPUT_DIR = ROOT / ".artifacts" / "docs"
OUTPUT_DOCX = OUTPUT_DIR / "智闻辨真_第二章需求分析优化版.docx"
OUTPUT_MD = OUTPUT_DIR / "第二章修改说明.md"
WORK_DIR = OUTPUT_DIR / "chapter2_revision"
FIGURE_DIR = WORK_DIR / "figures"
BUILD_REPORT = WORK_DIR / "build_report.json"
DOT = os.environ.get("GRAPHVIZ_DOT") or shutil.which("dot")


REQUIRED_HEADINGS = [
    (1, "第2章 系统需求分析"),
    (2, "2.1 系统需求概述"),
    (3, "2.1.1 系统定位与业务边界"),
    (3, "2.1.2 系统角色分析"),
    (2, "2.2 系统功能需求分析"),
    (3, "2.2.1 新闻输入与内容预览需求"),
    (3, "2.2.2 新闻可信度评估与结果查看需求"),
    (3, "2.2.3 个人记录与报告需求"),
    (3, "2.2.4 管理员业务管理需求"),
    (3, "2.2.5 智能评估支撑需求"),
    (2, "2.3 系统业务流程分析"),
    (3, "2.3.1 新闻输入与URL预览流程"),
    (3, "2.3.2 新闻可信度评估主流程"),
    (3, "2.3.3 异常处理与降级流程"),
    (3, "2.3.4 知识库维护与向量同步流程"),
    (3, "2.3.5 高风险复核与报告管理流程"),
    (2, "2.4 系统非功能需求分析"),
    (2, "2.5 本章小结"),
]


USER_REQUIREMENTS = [
    ["FR-U01", "游客/注册用户", "新闻文本输入", "标题、正文、来源、发布时间", "规范化待评估内容", "标题或正文为空时拒绝提交"],
    ["FR-U02", "游客/注册用户", "URL内容预览", "HTTP/HTTPS新闻URL", "可确认、可修订的内容预览", "提取失败保留原链接并允许重试或改为手工输入"],
    ["FR-U03", "游客/注册用户", "新闻可信度评估", "经确认的新闻内容、联网选项", "评分、风险等级、理由和状态", "证据不足或模型降级时明确标记能力边界"],
    ["FR-U04", "游客/注册用户", "结果与证据查看", "当次检测结果", "风险点、关键词、建议、有效证据和排除证据", "相似度仅用于召回、补充判断和展示"],
    ["FR-U05", "注册用户", "历史与重新评估", "本人记录、重评请求", "分页历史、详情和新评估记录", "仅本人访问；重评不得覆盖旧记录"],
    ["FR-U06", "注册用户", "检测报告生成", "已保存的本人检测记录", "PDF报告或失败提示", "生成失败不改变原检测记录"],
]


ADMIN_REQUIREMENTS = [
    ["FR-A01", "管理员", "知识库管理", "知识条目及同步操作", "业务记录、同步状态和恢复结果", "失败原因可查；支持单条重试和全量重建"],
    ["FR-A02", "管理员", "Prompt模板管理", "模板内容、状态和默认设置", "可用模板及变更结果", "无效或停用模板不得设为默认模板"],
    ["FR-A03", "管理员", "高风险复核", "高风险记录、状态、备注和公开设置", "复核状态与公开状态", "风险等级仅作为复核线索，不等同人工结论"],
    ["FR-A04", "管理员", "用户、检测和报告管理", "查询条件与授权管理操作", "列表、详情和操作结果", "管理接口仅管理员访问并保留必要审计记录"],
    ["FR-A05", "管理员", "统计与日志", "时间范围、统计维度和日志条件", "聚合统计和分页日志", "统计口径来自业务数据；日志不得记录密钥"],
]


SUPPORT_REQUIREMENTS = [
    ["FR-S01", "智能评估支撑", "多源候选获取", "新闻文本、本地索引、联网选项", "本地及按需补充的网络候选", "联网失败保留本地路径，不据此判定新闻不可信"],
    ["FR-S02", "智能评估支撑", "候选标准化与去重", "多源候选证据", "统一格式、规范化URL、唯一候选标识和稳定顺序", "重复候选合并；来源顺序不得影响处理规则"],
    ["FR-S03", "智能评估支撑", "证据仲裁", "全部候选及新闻内容", "有效证据、排除证据和逐条仲裁理由", "两类集合应完整且不重复覆盖候选"],
    ["FR-S04", "智能评估支撑", "契约校验与重试", "结构化仲裁结果", "校验结果、一次聚焦重试和异常摘要", "重试后仍不合格的候选不得参与证据评分"],
    ["FR-S05", "智能评估支撑", "分支式评分与降级", "模型状态、有效证据状态和规则分", "对应评分分支、风险等级和降级状态", "模型不可用时仅采用确定性规则，不虚构证据质量"],
    ["FR-S06", "智能评估支撑", "评估过程持久化", "候选、仲裁、评分和异常信息", "可追溯检测记录及契约版本", "持久化失败回滚并返回明确错误，不报告伪成功"],
]


NFR_ROWS = [
    ["NFR-S01", "权限安全", "管理接口仅管理员访问；个人历史、详情和报告仅记录所有者或授权管理员访问。", "以游客、普通用户和管理员执行越权接口测试。"],
    ["NFR-S02", "输入安全", "账号、分页、枚举和检测文本在接口边界校验；正文和候选数量设置合理上限。", "执行空值、超长文本、非法枚举和边界值测试。"],
    ["NFR-S03", "URL访问安全", "仅允许HTTP/HTTPS；拒绝本机、私有、链路本地和保留地址；每次重定向后重新校验。", "使用受限地址、协议和重定向链模拟测试。"],
    ["NFR-S04", "敏感信息安全", "数据库、令牌、模型和搜索服务密钥不得写入代码、论文或普通日志。", "检查源码、配置样例、论文和日志输出。"],
    ["NFR-R01", "外部服务可靠性", "网页抓取、联网搜索和模型调用设置超时；单项失败不得被解释为新闻风险升高。", "模拟超时、无结果、网络错误并检查降级状态。"],
    ["NFR-R02", "模型输出可靠性", "模型输出须经字段、类型、范围、枚举和候选完整性校验，必要时仅聚焦重试一次。", "注入缺字段、越界分值、未知标识和重复划分结果。"],
    ["NFR-D01", "数据一致性", "业务数据库作为事实源，向量索引作为派生数据；记录同步状态并提供补偿、重试和重建路径。", "模拟向量写入、删除及数据库提交失败并检查恢复状态。"],
    ["NFR-E01", "可解释性", "结果同时给出评分、等级、理由、风险点、建议、证据取舍和降级说明。", "检查正常、证据不足和模型失败三类结果。"],
    ["NFR-M01", "可维护性", "评估、知识、Prompt、报告、统计和审计职责边界清晰；外部配置集中管理。", "审查模块边界、配置来源和异常日志。"],
    ["NFR-X01", "可扩展性", "新增知识来源、新闻类别或外部服务适配时，尽量保持稳定业务入口和需求编号。", "通过设计审查和替换适配配置验证影响范围。"],
    ["NFR-P01", "数据查询性能", "列表接口使用分页，统计尽量在数据库层聚合，避免一次返回无界数据。", "检查接口分页参数、返回规模和统计查询实现。"],
    ["NFR-P02", "外部调用控制", "网页响应体、新闻正文和候选数量设置上限；抓取、搜索和模型调用具有超时与失败退出。", "执行超大响应、超量候选和超时模拟测试。"],
    ["NFR-A01", "审计性", "知识、Prompt、用户、高风险、检测和报告等关键管理操作形成可查询审计记录。", "执行关键管理操作并核对操作者、动作、模块和时间。"],
]


FIGURE_DOTS = {
    "fig2-1-use-case": r'''digraph G {
  graph [bgcolor="white", pad="0.12", margin="0", nodesep="0.30", ranksep="0.40",
         fontname="SimSun", fontsize=11, color="#222222", penwidth=1.0];
  node [fontname="SimSun", fontsize=10, color="#222222", fontcolor="#111111", penwidth=1.0];
  edge [fontname="SimSun", fontsize=9, color="#222222", fontcolor="#111111", arrowsize=0.65, penwidth=0.9];
  rankdir=LR; splines=polyline;
  guest [label="游客\n（角色）", shape=box, style="rounded"];
  user [label="注册用户\n（角色）", shape=box, style="rounded"];
  admin [label="管理员\n（角色）", shape=box, style="rounded"];
  subgraph cluster_system {
    label="智闻辨真系统边界"; labelloc="t"; style="rounded"; color="#333333";
    browse [label="浏览公开信息", shape=ellipse];
    preview [label="URL内容预览", shape=ellipse];
    detect [label="提交一次性检测", shape=ellipse];
    history [label="查看本人历史与详情", shape=ellipse];
    reevaluate [label="重新评估", shape=ellipse];
    report [label="生成本人检测报告", shape=ellipse];
    knowledge [label="知识库与向量同步管理", shape=ellipse];
    prompt [label="Prompt模板管理", shape=ellipse];
    review [label="高风险复核与公开管理", shape=ellipse];
    governance [label="用户、检测、报告、统计与日志管理", shape=ellipse];
  }
  guest -> browse [dir=none]; guest -> preview [dir=none]; guest -> detect [dir=none];
  user -> history [dir=none]; user -> reevaluate [dir=none]; user -> report [dir=none];
  admin -> knowledge [dir=none]; admin -> prompt [dir=none]; admin -> review [dir=none]; admin -> governance [dir=none];
  user -> guest [label="继承基础功能", arrowhead=empty];
  admin -> user [label="继承用户功能", arrowhead=empty];
}''',
    "fig2-2-evaluation-flow": r'''digraph G {
  graph [bgcolor="white", pad="0.10", margin="0", nodesep="0.26", ranksep="0.62",
         fontname="SimSun", fontsize=10, color="#222222", penwidth=1.0];
  node [shape=box, style="rounded", fontname="SimSun", fontsize=9.5, color="#222222",
        fontcolor="#111111", penwidth=1.0, margin="0.10,0.06"];
  edge [fontname="SimSun", fontsize=8, color="#222222", fontcolor="#111111", arrowsize=0.58, penwidth=0.85];
  rankdir=TB; splines=polyline;
  start [label="经用户确认的新闻内容", shape=oval];
  validate [label="内容校验"];
  local [label="本地候选召回"];
  enough [label="本地证据是否充足？", shape=diamond, style="solid", margin="0.04"];
  allow [label="是否允许联网？", shape=diamond, style="solid", margin="0.04"];
  web [label="联网补充候选"];
  webfail [label="联网失败：保留本地候选", style="rounded,dashed"];
  normalize [label="候选标准化与去重\n生成稳定候选标识并来源中立排序"];
  analyze [label="模型分析与逐条证据仲裁"];
  available [label="模型是否可用？", shape=diamond, style="solid", margin="0.04"];
  contract [label="契约校验是否通过？", shape=diamond, style="solid", margin="0.04"];
  retried [label="是否已聚焦重试？", shape=diamond, style="solid", margin="0.04"];
  retry [label="聚焦重试一次"];
  exclude [label="排除未通过仲裁的候选"];
  effective [label="是否存在有效证据？", shape=diamond, style="solid", margin="0.04"];
  score3 [label="模型、证据与规则分支"];
  score2 [label="模型与规则分支"];
  fallback [label="确定性规则评分降级\n不使用未仲裁候选，不生成证据质量分"];
  output [label="生成评分、风险等级与解释\n标记证据不足或降级状态"];
  save [label="保存候选、仲裁、评分和异常信息", shape=oval];
  invalid [label="不合法：返回原因", style="rounded,dashed"];

  {rank=same; start; validate; local;}
  {rank=same; enough; allow; web; webfail;}
  {rank=same; normalize; analyze; available;}
  {rank=same; contract; retried; retry;}
  {rank=same; exclude; effective; fallback;}
  {rank=same; score3; score2;}
  {rank=same; output; save;}

  start -> validate;
  validate -> invalid [label="不通过", constraint=false];
  validate -> local [label="通过"];
  local -> enough;
  enough -> normalize [label="是"];
  enough -> allow [label="否"];
  allow -> web [label="是"];
  allow -> normalize [label="否"];
  web -> normalize [label="成功"];
  web -> webfail [label="失败"];
  webfail -> normalize;
  normalize -> analyze -> available;
  available -> fallback [label="否"];
  available -> contract [label="是"];
  contract -> effective [label="是"];
  contract -> retried [label="否"];
  retried -> retry [label="否"];
  retry -> analyze [constraint=false];
  retried -> exclude [label="是"];
  exclude -> effective;
  effective -> score3 [label="是"];
  effective -> score2 [label="否"];
  score3 -> output; score2 -> output; fallback -> output;
  output -> save;
}''',
    "fig2-3-knowledge-sync": r'''digraph G {
  graph [bgcolor="white", pad="0.12", margin="0", nodesep="0.28", ranksep="0.50",
         fontname="SimSun", fontsize=10, color="#222222", penwidth=1.0];
  node [shape=box, style="rounded", fontname="SimSun", fontsize=9.5, color="#222222",
        fontcolor="#111111", penwidth=1.0, margin="0.11,0.07"];
  edge [fontname="SimSun", fontsize=8, color="#222222", fontcolor="#111111", arrowsize=0.62, penwidth=0.9];
  rankdir=TB; splines=polyline;
  admin [label="管理员维护知识条目", shape=oval];
  validate [label="数据校验"];
  valid [label="校验是否通过？", shape=diamond, style="solid", margin="0.04"];
  reject [label="拒绝操作并返回原因", style="rounded,dashed"];
  business [label="维护业务数据库记录\n事实源"];
  vector [label="维护向量索引\n由知识数据派生"];
  synced [label="同步是否成功？", shape=diamond, style="solid", margin="0.04"];
  success [label="记录同步成功状态", shape=oval];
  failure [label="记录失败原因与同步状态"];
  recover [label="按操作执行回滚或补偿"];
  choice [label="选择恢复方式", shape=diamond, style="solid", margin="0.04"];
  retry [label="单条重试"];
  rebuild [label="全量索引重建"];
  boundary [label="边界：业务数据库是事实源，向量索引是派生数据；\n两者不构成跨存储强事务。", shape=note, style="solid"];
  {rank=same; admin; validate; valid; reject;}
  {rank=same; business; vector; synced; success;}
  {rank=same; failure; recover; choice;}
  {rank=same; retry; rebuild;}
  admin -> validate -> valid;
  valid -> reject [label="否"];
  valid -> business [label="是"];
  business -> vector -> synced;
  synced -> success [label="是"];
  synced -> failure [label="否"];
  failure -> recover -> choice;
  choice -> retry [label="单条恢复"];
  choice -> rebuild [label="批量恢复"];
  retry -> vector [constraint=false]; rebuild -> vector [constraint=false];
  boundary -> business [style=dashed, arrowhead=none, constraint=false];
  boundary -> vector [style=dashed, arrowhead=none, constraint=false];
}''',
}


BODY_CONTENT = [
    ("h1", "第2章 系统需求分析"),
    ("h2", "2.1 系统需求概述"),
    ("p", "本系统面向网络新闻阅读与管理场景，提供基于检索证据和大语言模型分析的新闻可信度辅助评估能力。需求分析关注系统应向不同角色提供何种服务、输入与输出需要满足哪些约束，以及外部服务或数据同步异常时系统应如何表现，不在本章展开具体框架、接口路径、算法公式和数据库字段设计。"),
    ("p", "系统核心业务由新闻输入、候选证据获取、证据仲裁、分支式评分、结果解释、记录与报告管理以及管理员复核构成。各项需求使用FR-U、FR-A、FR-S和NFR编号，作为第4章总体设计、第5章系统实现和第6章测试验收的追踪依据。"),
    ("h3", "2.1.1 系统定位与业务边界"),
    ("p", "“智闻辨真”定位为新闻可信度辅助评估与风险提示工具。系统根据用户提交的新闻内容检索相关材料，对候选证据进行取舍并形成评分、风险等级和解释信息，帮助用户识别需要进一步核验的内容。系统输出不构成具有法律效力的真假认定，也不替代专业事实核查、权威机构结论或人工审核。"),
    ("p", "系统业务范围包括手工输入与URL内容预览、本地知识检索与按需联网补充、候选证据标准化、模型证据仲裁、服务端契约校验、分支式评分、结果持久化、个人历史与报告，以及知识、Prompt、高风险记录、用户、检测、报告、统计和日志管理。网页内容须经用户确认或修订后才能进入正式评估，自动提取结果不直接作为检测事实。"),
    ("p", "证据不足、证据冲突或外部能力不可用时，系统不得输出超出当前依据的确定性结论。检索相似度仅用于候选召回、判断是否需要联网补充和结果展示，不直接等同于证据质量或新闻可信度。系统应公开证据不足、仲裁失败和降级状态，使用户能够理解结果的能力边界。"),
    ("h3", "2.1.2 系统角色分析"),
    ("p", "系统角色分为游客、注册用户和管理员。三类角色共享新闻可信度辅助评估这一业务目标，但在记录归属、个人数据访问和管理权限方面具有不同边界；角色与主要功能需求在表2-1中统一列示。"),
    ("p", "游客可以浏览公开信息、使用URL预览并提交一次性检测。游客检测记录不绑定用户账号，结果仅用于承接当次检测，不开放个人历史、持久化详情和报告能力。"),
    ("p", "注册用户继承游客的基础功能，并可查看本人历史与检测详情、基于旧记录重新发起评估，以及根据本人已保存的检测结果生成和下载报告。个人数据访问必须校验记录归属，重新评估应生成新记录而不是覆盖原记录。"),
    ("p", "管理员在注册用户能力基础上承担系统治理职责，可以维护知识库和Prompt模板，查看向量同步状态并执行恢复操作，复核高风险新闻及其公开状态，管理用户、检测记录和报告，并查看统计与系统日志。系统自动生成的风险等级仅作为管理员复核线索，不能自动等同于人工复核结论。"),
    ("p", "系统总体用例关系如图2-1所示。注册用户继承游客的基础业务能力，管理员进一步取得治理与审计能力。"),
    ("fig", "fig2-1-use-case", "图2-1 系统总体用例图", 15.0),
    ("h2", "2.2 系统功能需求分析"),
    ("p", "系统功能需求分为用户功能需求、管理员功能需求和智能评估支撑需求。表2-1以稳定编号给出角色或支撑主体、主要输入、主要输出以及异常或边界要求；同一编号在后续设计、实现和测试中应保持语义一致。"),
    ("table-fr",),
    ("h3", "2.2.1 新闻输入与内容预览需求"),
    ("p", "系统应支持手工输入和URL提取预览两条路径。手工输入至少包括新闻标题与正文，并允许补充来源和发布时间；URL路径先提取标题、正文、来源与发布时间形成预览，不直接触发检测。用户确认或修订预览内容后，系统才接收最终文本进入评估流程。"),
    ("p", "系统应在提交前检查标题和正文的必要性、文本长度和基本格式，不允许空白正文进入检测。URL提取失败时应返回可理解的原因，保留用户输入的原链接，并允许重新尝试或切换为手工输入。上述需求由FR-U01和FR-U02追踪。"),
    ("h3", "2.2.2 新闻可信度评估与结果查看需求"),
    ("p", "用户提交经确认的新闻内容后，系统应完成候选证据获取、证据仲裁和评分分支选择，输出可信度评分、风险等级、判断理由、风险点、关键词和建议。结果页面还应区分有效证据与排除证据，给出证据取舍理由，并显示证据不足、联网失败、仲裁失败或模型降级等状态。"),
    ("p", "相似度可以随候选证据展示，也可以参与本地证据是否充足的判断，但不得直接表述为新闻可信度分数或证据质量分。联网搜索失败不等于新闻不可信，模型服务失败也不等于新闻风险升高；系统应根据可用信息进入相应分支，而不是把技术异常转化为事实结论。上述需求由FR-U03和FR-U04追踪。"),
    ("h3", "2.2.3 个人记录与报告需求"),
    ("p", "注册用户应能够分页查看本人历史记录和检测详情。重新评估使用原记录中的新闻输入重新执行当前评估流程，并保存为新的检测记录，以保留知识、模板或模型状态变化前后的结果，不得覆盖旧记录。"),
    ("p", "报告只能根据已经保存且用户有权访问的检测结果生成，内容应与该次检测的评分、风险等级、解释和证据一致。PDF生成失败时应返回明确提示并清理无效派生文件，不得修改原检测记录或影响页面结果查看。上述需求由FR-U05和FR-U06追踪。"),
    ("h3", "2.2.4 管理员业务管理需求"),
    ("p", "管理员应能够对知识条目执行新增、查询、修改和删除，查看派生向量的同步状态与失败原因，并对失败记录执行单条重试或全量索引重建。Prompt模板管理应支持新增、修改、启用、停用和默认模板设置；内容无效或处于停用状态的模板不得设置为默认模板。"),
    ("p", "管理员还应能够查询和管理用户、检测记录与报告，维护高风险记录的复核状态、备注和公开状态，并查看统计分析与系统日志。知识、Prompt、用户状态、高风险复核、检测和报告等关键管理操作应保留必要审计信息。上述需求由FR-A01至FR-A05追踪。"),
    ("h3", "2.2.5 智能评估支撑需求"),
    ("p", "系统应优先从本地知识库召回候选证据，并依据本地候选数量与相似度判断证据是否充足；仅在用户选择和系统配置允许时按需联网补充。联网失败时保留本地分析路径。本地与网络候选应转换为统一结构，完成URL规范化和重复候选处理，并为每条候选生成稳定且唯一的candidate_id。候选送入分析前应采用来源中立且可复现的顺序，减少来源位置对结果的影响。"),
    ("p", "模型应对全部候选逐条给出相关性、质量、立场和取舍理由，并将候选完整且不重复地划分为有效证据和排除证据。服务端应校验candidate_id、字段类型、分数范围、立场枚举以及两类集合对候选的完整覆盖，防止未知、重复、缺失或越界结果进入评分。"),
    ("p", "首次仲裁不符合契约时，系统仅针对证据仲裁执行一次聚焦重试。重试后仍不符合要求的候选不得参与证据评分，并应保存仲裁失败状态与异常摘要。系统不以模型返回的自由文本替代服务端校验，也不因候选相似度较高而跳过仲裁。"),
    ("p", "系统应根据模型服务状态和有效证据状态选择评分策略。模型可用且存在有效证据时使用包含证据质量的评分分支；模型可用但无有效证据时使用不含证据质量的分支；模型不可用时进入确定性规则评分降级路径，不使用未经仲裁的候选证据，不虚构证据质量分，并在结果中标记降级状态和能力边界。"),
    ("p", "评估完成后，系统应保存原始候选证据、有效证据、排除证据、评分分量、仲裁状态、异常摘要和分析契约版本，使结果能够追溯到当次输入、证据取舍和评分条件。上述能力由FR-S01至FR-S06追踪。"),
    ("h2", "2.3 系统业务流程分析"),
    ("h3", "2.3.1 新闻输入与URL预览流程"),
    ("p", "手工输入路径由用户填写标题、正文、来源和发布时间，系统校验后形成待评估内容。URL路径由用户提交公开网页地址，系统在通过协议、地址和响应限制检查后提取内容，并将标题、正文、来源和发布时间返回为预览。两条路径最终都以用户确认的文本作为正式检测输入。"),
    ("p", "链接提取失败时，交互界面应保留原链接并展示失败原因，用户可以再次尝试或改用手工输入；提取结果正文为空或经用户删除为空时，不得进入检测流程。URL预览与正式检测应分为两个阶段，以避免网页解析误差直接形成检测记录。"),
    ("h3", "2.3.2 新闻可信度评估主流程"),
    ("p", "新闻可信度评估从内容校验开始。系统先执行本地候选召回并判断本地证据是否充足，在允许且需要时联网补充；随后统一候选格式、规范化URL、处理重复项、生成稳定候选标识并形成来源中立顺序。模型对候选执行分析和证据仲裁，服务端完成契约校验，必要时聚焦重试一次。"),
    ("p", "系统根据模型是否可用以及是否存在有效证据选择对应评分分支，再生成风险等级、理由、风险点、建议和状态说明，最后保存候选、仲裁、评分和异常信息。该流程强调先仲裁、后评分，检索命中本身不构成可信度判断。主流程及其判断分支如图2-2所示。"),
    ("fig", "fig2-2-evaluation-flow", "图2-2 新闻可信度评估业务流程图", 14.6),
    ("h3", "2.3.3 异常处理与降级流程"),
    ("p", "本地证据不足时，系统在满足授权和配置条件后尝试联网补充；未获授权、联网失败或搜索无结果时，继续使用现有本地候选并标记证据状态。联网失败仅表示补充能力不可用，不能据此判定新闻不可信。"),
    ("p", "模型输出结构不合格、候选划分不完整或字段越界时，服务端拒绝该次仲裁并聚焦重试一次；重试仍失败时，相关候选不参与证据评分。模型服务整体不可用时，系统进入确定性规则评分降级路径，结果必须标记模型降级和证据能力边界。模型失败不应自动提高新闻风险等级。"),
    ("p", "检测数据持久化失败时，系统应回滚当前写入并返回明确错误，不得向用户报告检测已成功保存。报告生成失败发生在已保存结果之后，只影响报告派生文件与报告状态，不得改变原检测记录。异常分支应保存必要的错误摘要，以支持问题定位和后续测试。"),
    ("h3", "2.3.4 知识库维护与向量同步流程"),
    ("p", "知识维护以业务数据库中的知识记录为事实源，向量索引由知识数据派生并用于语义召回。管理员新增、修改或删除知识条目时，系统应校验业务数据、执行相应业务记录与向量索引维护，并记录同步状态；两类存储之间不宣称跨存储强事务或始终一致。"),
    ("p", "同步失败时，系统应记录失败原因并根据操作阶段执行回滚或补偿，支持对单条记录重试以及在需要时全量重建索引。检索命中向量后仍应以业务事实源确认条目有效性，从而降低孤立或过期索引进入候选池的风险。维护与恢复流程如图2-3所示。"),
    ("fig", "fig2-3-knowledge-sync", "图2-3 知识库维护与向量同步流程图", 14.6),
    ("h3", "2.3.5 高风险复核与报告管理流程"),
    ("p", "系统将达到高风险条件的检测记录提供给管理员作为复核线索。管理员可以查看新闻内容、评估解释和证据，维护复核状态、备注及公开状态。自动风险等级不能直接替代人工复核结论，未满足公开条件的记录不得通过公开页面展示。"),
    ("p", "报告管理以已保存检测记录为依据。注册用户只能为本人记录生成和下载报告，管理员可在授权范围内查看全局报告信息。报告生成失败时保留原检测记录和页面结果，不以空文件或伪成功状态代替真实失败。"),
    ("h2", "2.4 系统非功能需求分析"),
    ("p", "非功能需求用于约束系统在安全、可靠、数据一致、可解释、可维护、可扩展、性能控制和审计方面的质量属性。表2-2给出可追踪要求及验收方式，不预设尚未在目标环境验证的并发量、毫秒级响应时间、系统可用率或高可用指标。"),
    ("table-nfr",),
    ("p", "验收时应重点覆盖权限越权、恶意或异常URL、超长输入、外部服务超时、模型契约错误、向量同步失败、报告失败和数据库写入失败等场景。列表查询应采用分页，统计尽量在数据库层聚合；网页响应体、新闻正文和候选证据数量应设置上限，避免无界输入和外部调用长期占用资源。"),
    ("p", "安全要求还包括每次URL重定向后重新进行地址检查，密钥不得进入代码、论文和普通日志。上述异常分支可通过模拟失败和边界输入进行验证，验收结论应以实际测试记录为准。"),
    ("h2", "2.5 本章小结"),
    ("p", "本章明确了系统作为新闻可信度辅助评估与风险提示工具的业务边界，区分游客、注册用户和管理员三类角色，并从用户功能、管理员治理和智能评估支撑三个方面定义了可追踪功能需求。系统输出不替代专业事实核查，证据不足或外部能力不可用时需暴露不确定性和降级状态。"),
    ("p", "本章还规定了URL预览、证据仲裁、异常重试、规则降级、知识向量恢复、高风险复核和报告管理流程，并以NFR编号约束安全、可靠、解释、维护、性能控制和审计要求。这些编号为后续总体设计、系统实现和测试验收建立统一依据。"),
]


def set_run_font(run, size: float = 10.5, bold: bool | None = None) -> None:
    run.font.name = "Times New Roman"
    run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.rFonts
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    rfonts.set(qn("w:ascii"), "Times New Roman")
    rfonts.set(qn("w:hAnsi"), "Times New Roman")
    rfonts.set(qn("w:eastAsia"), "宋体")


def set_border(container, edge: str, val: str, size: str = "8") -> None:
    tag = "w:tcBorders" if container.tag.endswith("}tcPr") else "w:tblBorders"
    borders = container.find(qn(tag))
    if borders is None:
        borders = OxmlElement(tag)
        container.append(borders)
    element = borders.find(qn(f"w:{edge}"))
    if element is None:
        element = OxmlElement(f"w:{edge}")
        borders.append(element)
    element.set(qn("w:val"), val)
    if val != "nil":
        element.set(qn("w:sz"), size)
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), "000000")


def set_cell_margins(cell, top=70, start=85, bottom=70, end=85) -> None:
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


def prevent_row_split(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    cant_split = tr_pr.find(qn("w:cantSplit"))
    if cant_split is None:
        cant_split = OxmlElement("w:cantSplit")
        tr_pr.append(cant_split)


def repeat_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    header = tr_pr.find(qn("w:tblHeader"))
    if header is None:
        header = OxmlElement("w:tblHeader")
        header.set(qn("w:val"), "true")
        tr_pr.append(header)


def format_three_line_table(table, widths: list[float], font_size: float) -> None:
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    tbl_pr = table._tbl.tblPr
    layout = tbl_pr.find(qn("w:tblLayout"))
    if layout is None:
        layout = OxmlElement("w:tblLayout")
        tbl_pr.append(layout)
    layout.set(qn("w:type"), "fixed")
    set_border(tbl_pr, "top", "single", "12")
    set_border(tbl_pr, "bottom", "single", "12")
    for edge in ("left", "right", "insideH", "insideV"):
        set_border(tbl_pr, edge, "nil")
    repeat_header(table.rows[0])
    for row_index, row in enumerate(table.rows):
        prevent_row_split(row)
        for column_index, cell in enumerate(row.cells):
            cell.width = Cm(widths[column_index])
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_cell_margins(cell)
            tc_pr = cell._tc.get_or_add_tcPr()
            shading = tc_pr.find(qn("w:shd"))
            if shading is not None:
                tc_pr.remove(shading)
            if row_index == 0:
                set_border(tc_pr, "bottom", "single", "8")
            for paragraph in cell.paragraphs:
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                paragraph.paragraph_format.first_line_indent = Pt(0)
                paragraph.paragraph_format.space_before = Pt(0)
                paragraph.paragraph_format.space_after = Pt(0)
                paragraph.paragraph_format.line_spacing = 1.0
                paragraph.paragraph_format.keep_with_next = row_index < len(table.rows) - 1
                for run in paragraph.runs:
                    set_run_font(run, font_size, bold=(row_index == 0))


def generate_figures() -> dict[str, Path]:
    if not DOT or not Path(DOT).is_file():
        raise FileNotFoundError("Graphviz dot not found; add it to PATH or set GRAPHVIZ_DOT")
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    result: dict[str, Path] = {}
    for name, dot_text in FIGURE_DOTS.items():
        dot_path = FIGURE_DIR / f"{name}.dot"
        png_path = FIGURE_DIR / f"{name}.png"
        if name == "fig2-2-evaluation-flow":
            draw_evaluation_flow(png_path)
            result[name] = png_path
            continue
        if name == "fig2-3-knowledge-sync":
            draw_knowledge_sync_flow(png_path)
            result[name] = png_path
            continue
        dot_path.write_text(dot_text, encoding="utf-8")
        subprocess.run(
            [str(DOT), "-Tpng", "-Gdpi=300", str(dot_path), "-o", str(png_path)],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        with Image.open(png_path) as image:
            converted = image.convert("RGB")
            converted.save(png_path, dpi=(300, 300), optimize=True)
        result[name] = png_path
    return result


def _fonts() -> tuple[ImageFont.FreeTypeFont, ImageFont.FreeTypeFont, ImageFont.FreeTypeFont]:
    regular_path = Path(r"C:\Windows\Fonts\simsun.ttc")
    bold_path = Path(r"C:\Windows\Fonts\simhei.ttf")
    if not regular_path.exists() or not bold_path.exists():
        raise FileNotFoundError("Required Chinese fonts are unavailable")
    return (
        ImageFont.truetype(str(regular_path), 44),
        ImageFont.truetype(str(regular_path), 34),
        ImageFont.truetype(str(bold_path), 40),
    )


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> str:
    lines: list[str] = []
    for source_line in text.split("\n"):
        current = ""
        for char in source_line:
            trial = current + char
            if current and draw.textbbox((0, 0), trial, font=font)[2] > max_width:
                lines.append(current)
                current = char
            else:
                current = trial
        lines.append(current)
    return "\n".join(lines)


def _center_text(draw: ImageDraw.ImageDraw, box, text: str, font, max_width=None) -> None:
    x1, y1, x2, y2 = box
    available = max_width or int(x2 - x1 - 22)
    wrapped = _wrap_text(draw, text, font, available)
    bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=6, align="center")
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    draw.multiline_text(
        ((x1 + x2 - width) / 2, (y1 + y2 - height) / 2 - bbox[1]),
        wrapped,
        font=font,
        fill="black",
        spacing=6,
        align="center",
    )


def _box(draw: ImageDraw.ImageDraw, box, text: str, font, dashed=False, radius=20) -> None:
    if dashed:
        _dashed_rectangle(draw, box, width=4, dash=16)
    else:
        draw.rounded_rectangle(box, radius=radius, outline="black", width=4, fill="white")
    _center_text(draw, box, text, font)


def _ellipse(draw: ImageDraw.ImageDraw, box, text: str, font) -> None:
    draw.ellipse(box, outline="black", width=4, fill="white")
    _center_text(draw, box, text, font)


def _diamond(draw: ImageDraw.ImageDraw, box, text: str, font) -> None:
    x1, y1, x2, y2 = box
    points = [((x1 + x2) / 2, y1), (x2, (y1 + y2) / 2), ((x1 + x2) / 2, y2), (x1, (y1 + y2) / 2)]
    draw.polygon(points, outline="black", fill="white")
    draw.line(points + [points[0]], fill="black", width=4, joint="curve")
    _center_text(draw, box, text, font, int((x2 - x1) * 0.70))


def _note(draw: ImageDraw.ImageDraw, box, text: str, font) -> None:
    x1, y1, x2, y2 = box
    fold = 38
    points = [(x1, y1), (x2 - fold, y1), (x2, y1 + fold), (x2, y2), (x1, y2)]
    draw.polygon(points, outline="black", fill="white")
    draw.line([(x2 - fold, y1), (x2 - fold, y1 + fold), (x2, y1 + fold)], fill="black", width=3)
    _center_text(draw, box, text, font)


def _dashed_rectangle(draw: ImageDraw.ImageDraw, box, width=4, dash=14) -> None:
    x1, y1, x2, y2 = [int(v) for v in box]
    for x in range(x1, x2, dash * 2):
        draw.line((x, y1, min(x + dash, x2), y1), fill="black", width=width)
        draw.line((x, y2, min(x + dash, x2), y2), fill="black", width=width)
    for y in range(y1, y2, dash * 2):
        draw.line((x1, y, x1, min(y + dash, y2)), fill="black", width=width)
        draw.line((x2, y, x2, min(y + dash, y2)), fill="black", width=width)


def _arrow(draw: ImageDraw.ImageDraw, points, label=None, label_pos=None, label_font=None, dashed=False) -> None:
    pts = [(int(x), int(y)) for x, y in points]
    if dashed:
        for start, end in zip(pts, pts[1:]):
            x1, y1 = start
            x2, y2 = end
            steps = max(abs(x2 - x1), abs(y2 - y1))
            if steps == 0:
                continue
            for offset in range(0, steps, 24):
                ratio1 = offset / steps
                ratio2 = min(offset + 13, steps) / steps
                draw.line(
                    (
                        x1 + (x2 - x1) * ratio1,
                        y1 + (y2 - y1) * ratio1,
                        x1 + (x2 - x1) * ratio2,
                        y1 + (y2 - y1) * ratio2,
                    ),
                    fill="black",
                    width=4,
                )
    else:
        draw.line(pts, fill="black", width=4, joint="curve")
    if len(pts) >= 2:
        import math

        x1, y1 = pts[-2]
        x2, y2 = pts[-1]
        angle = math.atan2(y2 - y1, x2 - x1)
        length = 18
        left = (x2 - length * math.cos(angle - 0.55), y2 - length * math.sin(angle - 0.55))
        right = (x2 - length * math.cos(angle + 0.55), y2 - length * math.sin(angle + 0.55))
        draw.polygon([(x2, y2), left, right], fill="black")
    if label and label_pos and label_font:
        draw.text(label_pos, label, font=label_font, fill="black", anchor="mm")


def draw_evaluation_flow(path: Path) -> None:
    image = Image.new("RGB", (2300, 1760), "white")
    draw = ImageDraw.Draw(image)
    font, small, bold = _fonts()

    start = (60, 65, 380, 165)
    validate = (440, 65, 700, 165)
    local = (760, 65, 1040, 165)
    enough = (1110, 45, 1450, 185)
    allow = (1510, 45, 1830, 185)
    web = (1900, 65, 2240, 165)
    webfail = (1900, 245, 2240, 345)
    normalize = (1110, 260, 1760, 380)
    analyze = (690, 470, 1130, 585)
    available = (1240, 450, 1580, 605)
    fallback = (1750, 465, 2240, 590)
    contract = (1230, 675, 1590, 830)
    retried = (1230, 885, 1590, 1040)
    retry = (1760, 895, 2240, 1015)
    exclude = (680, 900, 1130, 1020)
    effective = (1230, 1100, 1590, 1255)
    score3 = (670, 1300, 1130, 1420)
    score2 = (1240, 1300, 1660, 1420)
    output = (830, 1510, 1500, 1635)
    save = (1660, 1520, 2240, 1625)
    invalid = (440, 245, 760, 345)

    _ellipse(draw, start, "经用户确认的新闻内容", font)
    _box(draw, validate, "内容校验", font)
    _box(draw, local, "本地候选召回", font)
    _diamond(draw, enough, "本地证据是否充足？", font)
    _diamond(draw, allow, "是否允许联网？", font)
    _box(draw, web, "联网补充候选", font)
    _box(draw, webfail, "联网失败：保留本地候选", small, dashed=True)
    _box(draw, normalize, "候选标准化与去重\n生成稳定候选标识并来源中立排序", font)
    _box(draw, analyze, "模型分析与逐条证据仲裁", font)
    _diamond(draw, available, "模型是否可用？", font)
    _box(draw, fallback, "确定性规则评分降级\n不使用未仲裁候选，不生成证据质量分", small)
    _diamond(draw, contract, "契约校验是否通过？", font)
    _diamond(draw, retried, "是否已聚焦重试？", font)
    _box(draw, retry, "聚焦重试一次", font)
    _box(draw, exclude, "排除未通过仲裁的候选", font)
    _diamond(draw, effective, "是否存在有效证据？", font)
    _box(draw, score3, "模型、证据与规则评分分支", font)
    _box(draw, score2, "模型与规则评分分支", font)
    _box(draw, output, "生成评分、风险等级与解释\n标记证据不足或降级状态", font)
    _ellipse(draw, save, "保存候选、仲裁、评分和异常信息", small)
    _box(draw, invalid, "输入不合法：返回原因，不进入检测", small, dashed=True)

    _arrow(draw, [(380, 115), (440, 115)])
    _arrow(draw, [(700, 115), (760, 115)])
    _arrow(draw, [(1040, 115), (1110, 115)])
    _arrow(draw, [(700, 165), (700, 245)], "不通过", (750, 205), small)
    _arrow(draw, [(1450, 115), (1510, 115)], "否", (1480, 85), small)
    _arrow(draw, [(1280, 185), (1280, 260)], "是", (1315, 220), small)
    _arrow(draw, [(1830, 115), (1900, 115)], "是", (1865, 85), small)
    _arrow(draw, [(1670, 185), (1670, 260)], "否", (1705, 220), small)
    _arrow(draw, [(2070, 165), (2070, 245)], "失败", (2125, 205), small)
    _arrow(draw, [(1900, 115), (1850, 115), (1850, 320), (1760, 320)], "成功", (1820, 285), small)
    _arrow(draw, [(1900, 295), (1810, 295), (1810, 340), (1760, 340)])
    _arrow(draw, [(1320, 380), (1050, 470)])
    _arrow(draw, [(1130, 527), (1240, 527)])
    _arrow(draw, [(1580, 527), (1750, 527)], "否", (1660, 495), small)
    _arrow(draw, [(1410, 605), (1410, 675)], "是", (1450, 640), small)
    _arrow(draw, [(1410, 830), (1410, 885)], "否", (1450, 858), small)
    _arrow(draw, [(1320, 830), (1320, 1100)], "是", (1280, 965), small)
    _arrow(draw, [(1590, 962), (1760, 955)], "否", (1680, 925), small)
    _arrow(draw, [(1230, 962), (1130, 962)], "是", (1180, 930), small)
    _arrow(draw, [(1760, 955), (1680, 955), (1680, 420), (920, 420), (920, 470)])
    _arrow(draw, [(1130, 960), (1180, 960), (1180, 1175), (1230, 1175)])
    _arrow(draw, [(1410, 1255), (900, 1300)], "是", (1110, 1260), small)
    _arrow(draw, [(1500, 1255), (1450, 1300)], "否", (1510, 1270), small)
    _arrow(draw, [(900, 1420), (1050, 1510)])
    _arrow(draw, [(1450, 1420), (1320, 1510)])
    _arrow(draw, [(2240, 527), (2280, 527), (2280, 1465), (1500, 1565)])
    _arrow(draw, [(1500, 1572), (1660, 1572)])

    image.save(path, dpi=(300, 300), optimize=True)


def draw_knowledge_sync_flow(path: Path) -> None:
    image = Image.new("RGB", (2350, 1180), "white")
    draw = ImageDraw.Draw(image)
    font, small, bold = _fonts()

    admin = (45, 70, 335, 170)
    validate = (390, 70, 630, 170)
    valid = (690, 45, 1010, 195)
    business = (1080, 60, 1410, 180)
    vector = (1490, 60, 1820, 180)
    synced = (1890, 45, 2210, 195)
    success = (1920, 290, 2280, 390)
    reject = (690, 290, 1010, 390)
    failure = (1490, 290, 1820, 400)
    recover = (1490, 500, 1820, 610)
    choice = (1890, 470, 2210, 630)
    retry = (1540, 735, 1830, 835)
    rebuild = (1950, 735, 2280, 835)
    boundary = (420, 870, 1840, 1080)

    _ellipse(draw, admin, "管理员维护知识条目", font)
    _box(draw, validate, "数据校验", font)
    _diamond(draw, valid, "校验是否通过？", font)
    _box(draw, business, "维护业务数据库记录\n事实源", font)
    _box(draw, vector, "维护向量索引\n由知识数据派生", font)
    _diamond(draw, synced, "同步是否成功？", font)
    _ellipse(draw, success, "记录同步成功状态", font)
    _box(draw, reject, "拒绝操作并返回原因", font, dashed=True)
    _box(draw, failure, "记录失败原因与同步状态", font)
    _box(draw, recover, "按操作执行回滚或补偿", font)
    _diamond(draw, choice, "选择恢复方式", font)
    _box(draw, retry, "单条重试", font)
    _box(draw, rebuild, "全量索引重建", font)
    _note(draw, boundary, "边界：业务数据库是事实源，向量索引是派生数据；\n两者不构成跨存储强事务。", bold)

    _arrow(draw, [(335, 120), (390, 120)])
    _arrow(draw, [(630, 120), (690, 120)])
    _arrow(draw, [(1010, 120), (1080, 120)], "是", (1045, 88), small)
    _arrow(draw, [(850, 195), (850, 290)], "否", (895, 240), small)
    _arrow(draw, [(1410, 120), (1490, 120)])
    _arrow(draw, [(1820, 120), (1890, 120)])
    _arrow(draw, [(2050, 195), (2100, 290)], "是", (2110, 235), small)
    _arrow(draw, [(1950, 195), (1655, 290)], "否", (1780, 230), small)
    _arrow(draw, [(1655, 400), (1655, 500)])
    _arrow(draw, [(1820, 555), (1890, 555)])
    _arrow(draw, [(2010, 630), (1685, 735)], "单条恢复", (1800, 665), small)
    _arrow(draw, [(2140, 630), (2115, 735)], "批量恢复", (2185, 680), small)
    _arrow(draw, [(1685, 735), (1685, 680), (1450, 680), (1450, 120), (1490, 120)])
    _arrow(draw, [(2115, 735), (2320, 735), (2320, 25), (1655, 25), (1655, 60)])
    image.save(path, dpi=(300, 300), optimize=True)


def find_body_element(doc: Document, exact_text: str):
    for paragraph in doc.paragraphs:
        if paragraph.text.strip() == exact_text:
            return paragraph._p
    raise RuntimeError(f"Cannot find paragraph: {exact_text}")


def body_range(doc: Document, start_text: str, end_text: str) -> list:
    body = doc._element.body
    children = list(body.iterchildren())
    start = find_body_element(doc, start_text)
    end = find_body_element(doc, end_text)
    start_index = children.index(start)
    end_index = children.index(end)
    if start_index >= end_index:
        raise RuntimeError("Invalid chapter boundaries")
    return children[start_index:end_index]


def count_range(elements: Iterable) -> dict[str, int]:
    paragraphs = tables = drawings = nonempty_paragraphs = 0
    for element in elements:
        if element.tag == qn("w:p"):
            paragraphs += 1
            text = "".join(element.itertext()).strip()
            nonempty_paragraphs += int(bool(text))
            drawings += len(element.xpath(".//w:drawing")) + len(element.xpath(".//w:pict"))
        elif element.tag == qn("w:tbl"):
            tables += 1
            drawings += len(element.xpath(".//w:drawing")) + len(element.xpath(".//w:pict"))
    return {
        "paragraphs": paragraphs,
        "nonempty_paragraphs": nonempty_paragraphs,
        "tables": tables,
        "drawings": drawings,
    }


def move_before(element, reference) -> None:
    reference.addprevious(element)


def add_paragraph_before(doc: Document, reference, text: str = "", style: str | None = None):
    paragraph = doc.add_paragraph(style=style)
    if text:
        run = paragraph.add_run(text)
        set_run_font(run)
    move_before(paragraph._p, reference)
    return paragraph


def add_heading_before(doc: Document, reference, text: str, level: int):
    paragraph = doc.add_paragraph(style=f"Heading {level}")
    run = paragraph.add_run(text)
    paragraph.paragraph_format.keep_with_next = True
    move_before(paragraph._p, reference)
    return paragraph


def add_body_before(doc: Document, reference, text: str, body_style: str):
    paragraph = add_paragraph_before(doc, reference, style=body_style)
    run = paragraph.add_run(text)
    set_run_font(run, 10.5)
    paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    paragraph.paragraph_format.first_line_indent = Pt(21)
    paragraph.paragraph_format.line_spacing = 1.5
    paragraph.paragraph_format.space_before = Pt(0)
    paragraph.paragraph_format.space_after = Pt(0)
    paragraph.paragraph_format.widow_control = True
    return paragraph


def add_caption_before(doc: Document, reference, text: str, body_style: str, continued=False):
    paragraph = add_paragraph_before(doc, reference, style=body_style)
    run = paragraph.add_run(text)
    set_run_font(run, 10.5)
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.first_line_indent = Pt(0)
    paragraph.paragraph_format.space_before = Pt(3 if continued else 6)
    paragraph.paragraph_format.space_after = Pt(3)
    paragraph.paragraph_format.keep_with_next = True
    return paragraph


def add_table_segment(
    doc: Document,
    reference,
    headers: list[str],
    rows: list[list[str]],
    widths: list[float],
    font_size: float,
):
    table = doc.add_table(rows=1, cols=len(headers))
    for index, value in enumerate(headers):
        table.cell(0, index).text = value
    for row_data in rows:
        row = table.add_row()
        for index, value in enumerate(row_data):
            row.cells[index].text = value
    format_three_line_table(table, widths, font_size)
    move_before(table._tbl, reference)
    return table


def add_function_requirements_table(doc: Document, reference, body_style: str) -> int:
    headers = ["编号", "角色/主体", "功能需求", "主要输入", "主要输出", "异常或边界要求"]
    widths = [1.45, 1.55, 2.25, 2.85, 3.05, 4.35]
    segments = [USER_REQUIREMENTS, ADMIN_REQUIREMENTS, SUPPORT_REQUIREMENTS]
    add_caption_before(doc, reference, "表2-1 系统角色与主要功能需求表", body_style)
    for index, rows in enumerate(segments):
        if index:
            add_caption_before(doc, reference, "续表2-1", body_style, continued=True)
        add_table_segment(doc, reference, headers, rows, widths, 8.0)
    return 1


def add_nfr_table(doc: Document, reference, body_style: str) -> int:
    headers = ["编号", "需求类别", "具体要求", "验收方式"]
    widths = [1.75, 2.35, 6.65, 4.75]
    segments = [NFR_ROWS[:3], NFR_ROWS[3:6], NFR_ROWS[6:9], NFR_ROWS[9:]]
    add_caption_before(doc, reference, "表2-2 系统非功能需求表", body_style)
    for index, rows in enumerate(segments):
        if index:
            add_caption_before(doc, reference, "续表2-2", body_style, continued=True)
        add_table_segment(doc, reference, headers, rows, widths, 8.8)
    return 1


def add_figure_before(
    doc: Document,
    reference,
    image_path: Path,
    caption: str,
    width_cm: float,
    body_style: str,
):
    paragraph = doc.add_paragraph(style=body_style)
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.first_line_indent = Pt(0)
    paragraph.paragraph_format.space_before = Pt(3)
    paragraph.paragraph_format.space_after = Pt(0)
    paragraph.paragraph_format.keep_with_next = True
    run = paragraph.add_run()
    run.add_picture(str(image_path), width=Cm(width_cm))
    move_before(paragraph._p, reference)

    caption_p = doc.add_paragraph(style=body_style)
    caption_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    caption_p.paragraph_format.first_line_indent = Pt(0)
    caption_p.paragraph_format.space_before = Pt(0)
    caption_p.paragraph_format.space_after = Pt(6)
    caption_run = caption_p.add_run(caption)
    set_run_font(caption_run, 10.5)
    move_before(caption_p._p, reference)


def enable_update_fields(doc: Document) -> None:
    settings = doc.settings._element
    update = settings.find(qn("w:updateFields"))
    if update is None:
        update = OxmlElement("w:updateFields")
        settings.append(update)
    update.set(qn("w:val"), "true")


def count_breaks(doc: Document) -> dict[str, int]:
    root = doc._element
    return {
        "page_breaks": len(root.xpath(".//w:br[@w:type='page']")),
        "column_breaks": len(root.xpath(".//w:br[@w:type='column']")),
        "section_properties": len(root.xpath(".//w:sectPr")),
        "sections": len(doc.sections),
    }


def extract_chapter_signature(doc: Document, start_text: str, end_text: str) -> list:
    signature = []
    for element in body_range(doc, start_text, end_text):
        if element.tag == qn("w:p"):
            text = "".join(element.itertext()).strip()
            style_nodes = element.xpath("./w:pPr/w:pStyle/@w:val")
            signature.append(["p", style_nodes[0] if style_nodes else "", text])
        elif element.tag == qn("w:tbl"):
            rows = []
            for tr in element.xpath("./w:tr"):
                row = []
                for tc in tr.xpath("./w:tc"):
                    row.append("".join(tc.itertext()).strip())
                rows.append(row)
            signature.append(["tbl", rows])
    return signature


def update_toc_with_word(path: Path) -> tuple[bool, str]:
    try:
        import win32com.client

        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0
        document = None
        try:
            document = word.Documents.Open(
                str(path),
                ConfirmConversions=False,
                ReadOnly=False,
                AddToRecentFiles=False,
            )
            count = int(document.TablesOfContents.Count)
            for index in range(1, count + 1):
                document.TablesOfContents(index).Update()
            document.Repaginate()
            document.Save()
            return True, f"Microsoft Word已刷新{count}个目录域"
        finally:
            if document is not None:
                document.Close(SaveChanges=False)
            word.Quit(SaveChanges=False)
    except Exception as exc:
        return False, f"未自动刷新目录域：{type(exc).__name__}: {exc}"


def validate_output(source_doc: Document, output_doc: Document, figure_paths: dict[str, Path]) -> dict:
    output_range = body_range(output_doc, "第2章 系统需求分析", "第3章 系统开发环境与关键技术")
    output_stats = count_range(output_range)
    chapter_text = "\n".join(
        "".join(element.itertext()).strip()
        for element in output_range
        if element.tag == qn("w:p")
    )
    headings = [
        paragraph.text.strip()
        for paragraph in output_doc.paragraphs
        if paragraph.text.strip().startswith(("第2章", "2."))
        and paragraph._p in output_range
    ]
    expected = [text for _, text in REQUIRED_HEADINGS]
    forbidden = [
        "DeepSeek API调用异常，系统应返回检测失败",
        "保证业务数据与检索数据一致",
        "确保MySQL中的结构化数据与Chroma中的向量数据保持一致",
        "相似度越高新闻越真实",
        "保证结果绝对准确",
        "彻底消除模型幻觉",
    ]
    image_info = {}
    for name, path in figure_paths.items():
        with Image.open(path) as image:
            image_info[name] = {
                "width_px": image.width,
                "height_px": image.height,
                "dpi": tuple(round(float(x)) for x in image.info.get("dpi", (0, 0))),
            }
    validations = {
        "zip_valid": zipfile.is_zipfile(OUTPUT_DOCX),
        "chapter_headings_match": headings == expected,
        "forbidden_phrases_absent": not any(phrase in chapter_text for phrase in forbidden),
        "required_terms_present": all(
            term in chapter_text
            for term in (
                "candidate_id",
                "有效证据",
                "排除证据",
                "降级状态",
                "业务数据库中的知识记录为事实源",
                "向量索引由知识数据派生",
                "联网失败仅表示补充能力不可用",
            )
        ),
        "chapter1_unchanged": extract_chapter_signature(
            source_doc, "第1章 绪论", "第2章 系统需求分析"
        )
        == extract_chapter_signature(output_doc, "第1章 绪论", "第2章 系统需求分析"),
        "chapter3_unchanged": extract_chapter_signature(
            source_doc, "第3章 系统开发环境与关键技术", "第4章 系统总体设计"
        )
        == extract_chapter_signature(
            output_doc, "第3章 系统开发环境与关键技术", "第4章 系统总体设计"
        ),
        "chapter4_unchanged": extract_chapter_signature(
            source_doc, "第4章 系统总体设计", "参考文献"
        )
        == extract_chapter_signature(output_doc, "第4章 系统总体设计", "参考文献"),
        "breaks_unchanged": count_breaks(source_doc) == count_breaks(output_doc),
        "source_breaks": count_breaks(source_doc),
        "output_breaks": count_breaks(output_doc),
        "output_chapter_stats": output_stats,
        "image_info": image_info,
    }
    validations["all_pass"] = all(
        validations[key]
        for key in (
            "zip_valid",
            "chapter_headings_match",
            "forbidden_phrases_absent",
            "required_terms_present",
            "chapter1_unchanged",
            "chapter3_unchanged",
            "chapter4_unchanged",
            "breaks_unchanged",
        )
    )
    return validations


def build_markdown(report: dict) -> str:
    validation = report["validation"]
    toc_status = report["toc_status"]
    source_stats = report["source_chapter_stats"]
    output_stats = validation["output_chapter_stats"]
    image_lines = "\n".join(
        f"- {name}：{info['width_px']}×{info['height_px']}像素，PNG元数据{info['dpi'][0]}dpi。"
        for name, info in validation["image_info"].items()
    )
    return f"""# 第二章修改说明

## 1. 文件与修改范围

- 原文件：`{SOURCE}`
- 输出文件：`{OUTPUT_DOCX}`
- 处理方式：先复制原文件为新文件，再仅替换“第2章系统需求分析”至“第3章系统开发环境与关键技术”之前的内容，原文件未覆盖。
- 原第二章包含{source_stats['paragraphs']}个段落块、{source_stats['tables']}张表和{source_stats['drawings']}幅图；优化版第二章包含{output_stats['paragraphs']}个段落块、2张逻辑表（分段续表排版）和3幅图。

## 2. 原第二章主要问题

1. 角色仅笼统写为普通用户和管理员，没有明确区分游客、注册用户与管理员的记录归属和访问边界。
2. 章节偏重Vue3、FastAPI、MySQL、Chroma和DeepSeek等技术栈说明，与第3章技术选型内容重复，不符合需求分析侧重“系统应实现什么”的写作目的。
3. 原文写明DeepSeek API异常时返回检测失败，与第4章“模型不可用时进入确定性规则评分降级路径”的实际方法冲突。
4. 原文使用“保证MySQL与Chroma一致”“确保两类数据保持一致”等绝对化表述，未体现业务事实源、派生向量索引及跨存储补偿边界。
5. 原流程将检索相关度与综合评分并列描述，容易把语义相似度误解为证据质量或新闻可信度。
6. 原第二章缺少URL预览确认、候选标准化、稳定候选标识、来源中立排序、证据契约校验、聚焦重试、分支式评分和评估过程持久化等关键需求。
7. 原流程图缺少联网、契约校验、模型可用性、有效证据和降级评分等判断分支；非功能需求也缺少可验收编号。
8. 原第二章没有2.5本章小结，需求与后续设计、实现和测试之间缺少稳定追踪编号。

## 3. 修改后的目录结构

```text
第2章 系统需求分析
2.1 系统需求概述
  2.1.1 系统定位与业务边界
  2.1.2 系统角色分析
2.2 系统功能需求分析
  2.2.1 新闻输入与内容预览需求
  2.2.2 新闻可信度评估与结果查看需求
  2.2.3 个人记录与报告需求
  2.2.4 管理员业务管理需求
  2.2.5 智能评估支撑需求
2.3 系统业务流程分析
  2.3.1 新闻输入与URL预览流程
  2.3.2 新闻可信度评估主流程
  2.3.3 异常处理与降级流程
  2.3.4 知识库维护与向量同步流程
  2.3.5 高风险复核与报告管理流程
2.4 系统非功能需求分析
2.5 本章小结
```

## 4. 删除或纠正的冲突表述

- 将“模型异常时检测失败”改为：模型服务不可用时仅采用确定性规则评分，不使用未经仲裁的候选证据，不虚构证据质量分，并标记降级状态和能力边界。
- 将“确保MySQL与Chroma始终一致”改为：业务数据库中的知识记录是事实源，向量索引是派生数据；通过同步状态、失败原因、回滚、补偿、单条重试和全量重建降低不一致风险，不宣称跨存储强事务。
- 将“检索相关度参与综合可信度计算”的模糊表述改为：相似度用于候选召回、联网补充判断和结果展示，不直接等同于证据质量或新闻可信度。
- 将“自动风险等级等同审核结论”的潜在歧义改为：高风险等级仅作为管理员复核线索，复核状态、备注和公开状态由管理员维护。
- 将“URL直接进入检测”改为两阶段流程：先提取预览，再由用户确认或修订后提交正式检测。

## 5. 新增需求编号

- 用户功能：FR-U01～FR-U06。
- 管理员功能：FR-A01～FR-A05。
- 智能评估支撑：FR-S01～FR-S06。
- 非功能需求：NFR-S01～NFR-S04、NFR-R01～NFR-R02、NFR-D01、NFR-E01、NFR-M01、NFR-X01、NFR-P01～NFR-P02、NFR-A01。

## 6. 新增或替换的图表

- 表2-1“系统角色与主要功能需求表”：将角色边界、用户需求、管理员需求和智能评估支撑需求合并到统一编号表中；为避免单元格过窄，按FR-U、FR-A、FR-S分段排版并标注“续表2-1”。
- 表2-2“系统非功能需求表”：给出质量属性、具体要求和验收方式；采用短表分段并标注“续表2-2”，减少跨页拆分。
- 图2-1“系统总体用例图”：新增游客、注册用户、管理员及角色继承关系。
- 图2-2“新闻可信度评估业务流程图”：替换原检测流程图，补充本地证据充足性、联网许可、契约校验、聚焦重试、模型可用性、有效证据和评分分支。
- 图2-3“知识库维护与向量同步流程图”：替换原知识库流程图，明确事实源、派生索引、同步状态和补偿恢复边界。

图件检查：

{image_lines}

## 7. 未修改内容说明

- 未修改封面、第1章、第3章、第4章、参考文献及其他章节正文。
- 未修改全文页边距、已有分节、全局标题样式及其他章节图表编号。
- 未新增分页符或分节符；源文档与输出文档的分页符、分节属性和节数量核对一致。
- 原文件保持不变，所有输出均位于指定“润色”目录。

## 8. 与第4章及项目实际功能的一致性检查

- 第4章4.1～4.7与项目路由、服务、数据模型和测试代码已交叉核对。
- 游客匿名检测与URL预览、注册用户本人历史/重评/报告、管理员知识/Prompt/高风险/用户/检测/报告/统计/日志能力与当前实现一致。
- 候选证据标准化、candidate_id、来源中立排序、逐条仲裁、完整划分、契约校验、一次聚焦重试、分支式评分和降级状态与第4章及检测服务一致。
- 知识业务记录作为事实源、向量索引作为派生数据、同步状态、单条重试和全量重建与第4章及知识管理服务一致。
- 报告基于已保存结果生成且生成失败不改变原检测记录，与第4章及报告服务一致。

## 9. Word格式检查结果

- 文档可由python-docx正常打开，DOCX压缩包结构有效：{validation['zip_valid']}。
- 第二章标题层级及顺序检查：{validation['chapter_headings_match']}。
- 第1章正文未变：{validation['chapter1_unchanged']}；第3章正文未变：{validation['chapter3_unchanged']}；第4章正文未变：{validation['chapter4_unchanged']}。
- 新增正文统一为五号字；中文字体为宋体，英文、数字和变量为Times New Roman。
- 表格无填充色，采用三线表，设置固定列宽、禁止行内跨页拆分，并对分段续表重复表头。
- 图片按原比例插入，图题位于图片下方；图件采用黑白线条和300dpi PNG，不使用渐变或阴影。
- 分页符与分节符数量未增加：{validation['breaks_unchanged']}。
- 目录处理：{toc_status}。文档设置为打开时更新域。

## 10. 仍需作者人工确认的内容

1. 请在Microsoft Word中右键目录，选择“更新域—更新整个目录”，并复核第二章及后续章节页码；不同Word版本、打印机驱动或字体环境可能造成分页变化。
2. 请以100%缩放检查图2-1至图2-3文字是否符合学校打印要求，并在最终提交前做一次黑白打印预览。
3. 表2-1和表2-2采用分段续表以保证列宽；如学校模板对“续表”题注位置有特殊规定，请按学院样例微调。
4. 当前项目已经实现管理员高风险复核入口，但系统自动风险等级仍只是复核线索；论文答辩时不应表述为具有权威性的人工事实核查结论。
5. 非功能需求采用可验证的定性边界，未虚构并发量、响应时间或可用率；如第6章已有真实测试数据，可在后续测试章节引用相同NFR编号补充证据。
"""


def main() -> None:
    if not SOURCE.exists() or not zipfile.is_zipfile(SOURCE):
        raise FileNotFoundError(f"Invalid source document: {SOURCE}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    figures = generate_figures()

    source_doc = Document(SOURCE)
    source_breaks = count_breaks(source_doc)
    source_range = body_range(source_doc, "第2章 系统需求分析", "第3章 系统开发环境与关键技术")
    source_stats = count_range(source_range)

    shutil.copy2(SOURCE, OUTPUT_DOCX)
    doc = Document(OUTPUT_DOCX)
    chapter3 = find_body_element(doc, "第3章 系统开发环境与关键技术")
    for element in body_range(doc, "第2章 系统需求分析", "第3章 系统开发环境与关键技术"):
        element.getparent().remove(element)

    body_style = "Normal (Web)" if "Normal (Web)" in doc.styles else "Normal"
    logical_tables = 0
    figures_added = 0
    for item in BODY_CONTENT:
        kind = item[0]
        if kind == "h1":
            add_heading_before(doc, chapter3, item[1], 1)
        elif kind == "h2":
            add_heading_before(doc, chapter3, item[1], 2)
        elif kind == "h3":
            add_heading_before(doc, chapter3, item[1], 3)
        elif kind == "p":
            add_body_before(doc, chapter3, item[1], body_style)
        elif kind == "fig":
            add_figure_before(doc, chapter3, figures[item[1]], item[2], item[3], body_style)
            figures_added += 1
        elif kind == "table-fr":
            logical_tables += add_function_requirements_table(doc, chapter3, body_style)
        elif kind == "table-nfr":
            logical_tables += add_nfr_table(doc, chapter3, body_style)
        else:
            raise ValueError(f"Unknown content type: {kind}")

    enable_update_fields(doc)
    if count_breaks(doc) != source_breaks:
        raise RuntimeError(
            f"Break or section count changed before save: source={source_breaks}, output={count_breaks(doc)}"
        )
    doc.save(OUTPUT_DOCX)

    toc_ok, toc_status = update_toc_with_word(OUTPUT_DOCX)
    output_doc = Document(OUTPUT_DOCX)
    validation = validate_output(source_doc, output_doc, figures)
    if not validation["all_pass"]:
        raise RuntimeError(json.dumps(validation, ensure_ascii=False, indent=2))

    report = {
        "source": str(SOURCE),
        "output_docx": str(OUTPUT_DOCX),
        "output_md": str(OUTPUT_MD),
        "source_chapter_stats": source_stats,
        "logical_tables": logical_tables,
        "figures_added": figures_added,
        "toc_updated": toc_ok,
        "toc_status": toc_status,
        "validation": validation,
    }
    BUILD_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    OUTPUT_MD.write_text(build_markdown(report), encoding="utf-8")

    output_stats = validation["output_chapter_stats"]
    print(f"修改段落：原第二章{source_stats['paragraphs']}个段落块已替换，优化版共{output_stats['paragraphs']}个段落块")
    print(f"新增或重做表格：{logical_tables}张逻辑表")
    print(f"新增或重做图件：{figures_added}幅")
    print("修改范围：仅第二章；目录域按允许范围刷新")
    print(f"DOCX：{OUTPUT_DOCX}")
    print(f"说明：{OUTPUT_MD}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
