from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "thesis" / "figures" / "chapter4"


COMMON = r'''
  graph [bgcolor="white", pad="0.16", margin="0", nodesep="0.34", ranksep="0.46",
         fontname="SimSun", fontsize=10, color="#7B8794", penwidth=1.0];
  node [shape=box, style="rounded,filled", fillcolor="#F7F8FA", color="#465563",
        fontname="SimSun", fontsize=9, fontcolor="#17202A", penwidth=1.0,
        margin="0.14,0.08"];
  edge [color="#53616E", fontname="SimSun", fontsize=8, fontcolor="#37434F",
        arrowsize=0.68, penwidth=0.9];
'''


FIGURES: dict[str, str] = {
    "fig4-1-system-architecture": rf'''digraph G {{
{COMMON}
  rankdir=TB; splines=ortho;
  browser [label="浏览器用户\n游客｜注册用户｜管理员", fillcolor="#EAF2F8", color="#5B7C99"];

  subgraph cluster_system {{
    label="智闻辨真系统边界"; labelloc="t"; color="#8795A1"; style="rounded";
    subgraph cluster_frontend {{
      label="表现与交互层"; color="#C3CBD2"; style="rounded";
      vue [label="Vue 3前端应用\n页面与组件｜Vue Router｜Pinia｜Axios", fillcolor="#F2F5F7"];
    }}
    subgraph cluster_backend {{
      label="接口与业务层"; color="#C3CBD2"; style="rounded";
      fastapi [label="FastAPI REST接口\n认证鉴权｜参数校验｜统一响应", fillcolor="#EAF2F8", color="#5B7C99"];
      services [label="业务服务\n检测编排｜RAG检索｜证据仲裁｜报告生成｜统计与审计"];
      scheduler [label="APScheduler定时调度\n周期性新闻采集", style="rounded,dashed,filled", fillcolor="#FAFAFA"];
    }}
    subgraph cluster_storage {{
      label="数据与文件层"; color="#C3CBD2"; style="rounded";
      mysql [label="MySQL\n结构化业务数据", shape=cylinder, fillcolor="#F7F8FA"];
      chroma [label="Chroma\nknowledge_items语义索引", shape=cylinder, fillcolor="#F7F8FA"];
      reports [label="报告文件目录\nHTML／PDF", shape=folder, fillcolor="#F7F8FA"];
    }}
  }}

  subgraph cluster_external {{
    label="外部智能与内容服务"; color="#9AA7B2"; style="rounded,dashed";
    external [label="DeepSeek：证据约束下的语义分析\nDashScope：text-embedding-v4／1024维向量\n博查搜索：本地证据不足时补充\n新闻网页：标题、正文与发布时间提取"];
  }}

  browser -> vue [label="页面操作"];
  vue -> fastapi [label="HTTP／JSON；JWT Bearer"];
  fastapi -> services [label="调用"];
  scheduler -> services [label="触发采集"];
  services -> mysql [label="事务读写"];
  services -> chroma [label="向量写入／相似检索"];
  services -> reports [label="模板渲染／文件生成"];
  services -> external [label="受控调用；超时与降级"];
}}''',

    "fig4-2-backend-layered-architecture": rf'''digraph G {{
{COMMON}
  rankdir=TB; splines=ortho;
  api [label="API层（app/api）\n路由、依赖注入、状态码与响应封装", fillcolor="#EAF2F8", color="#5B7C99"];
  schema [label="Schema层（app/schemas）\n请求／响应模型、类型与字段约束"];
  service [label="Service层（app/services）\n业务编排、RAG、评分、外部服务与补偿逻辑"];
  crud [label="CRUD层（app/crud）\n查询、分页、持久化与事务边界"];
  model [label="Model层（app/models）\nSQLAlchemy实体、主外键与级联关系"];
  storage [label="数据存储层\nMySQL｜Chroma｜报告文件目录", shape=box3d, fillcolor="#F2F5F7"];
  core [label="Core横向基础设施\n配置｜JWT与角色校验｜数据库会话\n限流｜调度器｜全局异常处理", style="rounded,dashed,filled", fillcolor="#FAFAFA"];

  api -> schema [label="校验输入／声明输出"];
  api -> service [label="调用用例服务"];
  service -> crud [label="组织数据访问"];
  crud -> model [label="操作实体"];
  model -> storage [label="映射／持久化"];
  service -> storage [label="向量与文件服务", style=dashed];
  core -> api [label="依赖与中间件", style=dashed, constraint=false];
  core -> service [label="配置与调度", style=dashed, constraint=false];
  core -> crud [style=dashed, constraint=false];
}}''',

    "fig4-3-functional-modules": rf'''digraph G {{
{COMMON}
  rankdir=TB; splines=ortho;
  system [label="智闻辨真\n新闻可信度评估系统", shape=ellipse, fillcolor="#EAF2F8", color="#5B7C99", penwidth=1.2];
  userdomain [label="用户业务域\n①用户认证与个人中心\n②检测记录与报告"];
  coredomain [label="核心评估域\n③新闻可信度评估\n④知识库与新闻采集", fillcolor="#EAF2F8", color="#5B7C99"];
  admindomain [label="管理治理域\n⑤管理员业务管理\n⑥数据统计与系统日志"];

  {{rank=same; userdomain; coredomain; admindomain;}}
  system -> userdomain;
  system -> coredomain;
  system -> admindomain;
}}''',

    "fig4-4-detection-overall-flow": rf'''digraph G {{
{COMMON}
  rankdir=TB; splines=polyline; nodesep=0.28; ranksep=0.52;
  input [label="新闻输入与预处理\n文本直输；或URL安全提取后由用户确认", fillcolor="#EAF2F8", color="#5B7C99"];
  retrieve [label="本地检索与联网补充\nEmbedding→Chroma Top-10→条件式博查搜索"];
  pool [label="候选证据池\n格式统一、去重、候选ID与来源中立排序"];
  analyze [label="模型分析与证据仲裁\n质量、相关性、立场及拒绝原因"];
  effective [label="有效证据集\n契约失败时聚焦重试1次；无效候选不计分"];
  score [label="规则评分与分支式综合评分\n风险等级、理由、风险点与建议"];
  save [label="结果持久化\n检测记录、有效证据与分析载荷"];
  result [label="结果展示与报告入口", shape=oval, fillcolor="#EAF2F8", color="#5B7C99"];
  webfail [label="搜索失败：保留本地证据", style="rounded,dashed,filled", fillcolor="#FAFAFA"];
  llmfail [label="模型失败：仅采用规则分", style="rounded,dashed,filled", fillcolor="#FAFAFA"];
  dbfail [label="数据库异常：回滚并统一报错", style="rounded,dashed,filled", fillcolor="#FAFAFA"];

  input -> retrieve -> pool;
  pool -> analyze -> effective -> score;
  score -> save -> result;
  retrieve -> webfail [style=dashed]; webfail -> pool [style=dashed];
  analyze -> llmfail [style=dashed]; llmfail -> score [style=dashed];
  save -> dbfail [style=dashed];
}}''',

    "fig4-5-local-retrieval-web-supplement": rf'''digraph G {{
{COMMON}
  rankdir=TB; splines=polyline; nodesep=0.30; ranksep=0.55;
  query [label="规范化新闻标题＋正文\nDashScope生成1024维查询向量", shape=oval, fillcolor="#EAF2F8", color="#5B7C99"];
  chroma [label="Chroma余弦距离检索\n召回Top-10本地候选"];
  sufficient [label="允许并需要联网补充？\n前提：用户启用且系统允许\n条件：无本地证据；或Top-1＜0.45；\n或Top-1＜0.60且有效候选＜3\n（有效候选相似度≥0.30）", shape=diamond, style="filled", margin="0.08"];
  bocha [label="博查搜索\n标题＋关键词；受数量与时效配置约束"];
  merge [label="多源候选整理\n本地最多5条＋网络最多5条\n同源强标识去重；保留来源类型"];
  pool [label="统一候选证据池\n生成kb:<id>／web:<序号>候选ID\nSHA-256种子确定来源中立顺序\n送入模型的候选不超过10条", shape=oval, fillcolor="#EAF2F8", color="#5B7C99"];

  query -> chroma -> sufficient;
  sufficient -> merge [label="否：本地证据足够"];
  sufficient -> bocha [label="是"];
  bocha -> merge [label="成功时合并；失败／无结果时仅保留本地项"];
  merge -> pool;
}}''',

    "fig4-6-scoring-risk-classification": rf'''digraph G {{
{COMMON}
  rankdir=TB; splines=ortho;
  arbitration [label="证据仲裁结果\nranked有效证据｜rejected排除证据", fillcolor="#EAF2F8", color="#5B7C99"];
  components [label="评分分量\nSₗ：LLM可信度分（0～100）\nSᵣ：规则分（0～100）\n覆盖度C、一致性K（0～100）"];
  eq [label="证据质量分Sₑ＝0.6C＋0.4K\n由服务端重算，不直接信任模型给分"];
  llmfail [label="LLM服务失败？", shape=diamond, style="filled", margin="0.06"];
  has [label="存在有效证据？", shape=diamond, style="filled", margin="0.06"];
  f1 [label="降级：S＝Sᵣ"];
  f2 [label="无有效证据：S＝0.6Sₗ＋0.4Sᵣ"];
  f3 [label="有有效证据：S＝0.5Sₗ＋0.3Sₑ＋0.2Sᵣ", fillcolor="#EAF2F8", color="#5B7C99"];
  level [label="风险等级映射\nS≥80：可信新闻\n60≤S＜80：存疑信息\n40≤S＜60：疑似谣言\nS＜40：高风险谣言"];
  output [label="输出与持久化\n最终分、等级、判断理由、风险点、建议\n原始相似度均值仅展示／记录，不进入当前综合公式", shape=oval, fillcolor="#F2F5F7"];

  arbitration -> components;
  components -> eq;
  components -> llmfail;
  eq -> has;
  llmfail -> f1 [label="是"];
  llmfail -> has [label="否"];
  has -> f3 [label="是"];
  has -> f2 [label="否"];
  f1 -> level;
  f2 -> level;
  f3 -> level;
  level -> output;
}}''',

    "fig4-7-database-er": rf'''digraph G {{
{COMMON}
  rankdir=TB; splines=polyline; nodesep=0.42; ranksep=0.70;
  node [shape=record, style="filled", fillcolor="#F7F8FA", margin="0.08,0.05"];
  users [label="{{users|id（PK）|username（UQ）|role／status}}", fillcolor="#EAF2F8", color="#5B7C99"];
  detections [label="{{detection_records|id（PK）|user_id（FK，可空）|reviewed_by（FK，可空）|final_score／risk_level}}"];
  evidence [label="{{evidence_matches|id（PK）|detection_id（FK）|knowledge_id（FK，可空）|similarity_score／rank_order}}"];
  knowledge [label="{{knowledge_items|id（PK）|title／truth_label|vector_id／vector_sync_status}}"];
  prompts [label="{{prompt_templates|id（PK）|created_by（FK，可空）|type／status／is_default}}"];
  reports [label="{{reports|id（PK）|detection_id（FK，UQ）|user_id（FK，可空）|html_path／pdf_path}}"];
  logs [label="{{system_logs|id（PK）|user_id（FK，可空）|action／module／ip_address}}"];
  crawls [label="{{crawl_tasks|id（PK）|job_name／search_query|status／统计字段}}", style="filled,dashed", fillcolor="#FAFAFA"];

  {{rank=same; detections; prompts;}}
  {{rank=same; logs; knowledge;}}
  {{rank=same; evidence; reports;}}

  users -> detections [label="创建 1：0..N", color="#5B7C99"];
  users -> detections [label="复核 1：0..N", style=dashed];
  detections -> evidence [label="1：0..N"];
  knowledge -> evidence [label="1：0..N", style=dashed];
  detections -> reports [label="1：0..1", color="#5B7C99"];
  users -> reports [label="1：0..N", style=dashed];
  users -> prompts [label="1：0..N", style=dashed];
  users -> logs [label="1：0..N", style=dashed];
}}''',

    "fig4-8-mysql-chroma-collaboration": rf'''digraph G {{
{COMMON}
  rankdir=TB; splines=ortho;
  mysql [label="MySQL：knowledge_items\n业务事实源\nid、全文、标签、vector_id\nvector_sync_status／error", shape=cylinder, fillcolor="#EAF2F8", color="#5B7C99"];
  text [label="构造向量化文本\ntitle、content、category、summary、keywords、\ntruth_label、debunking_explanation"];
  embed [label="DashScope Embedding\ntext-embedding-v4／1024维"];
  chroma [label="Chroma：knowledge_items\nID＝knowledge:<id>；cosine\n元数据：knowledge_id、title、category、\ntruth_label、source_name、risk_level", shape=cylinder, fillcolor="#F7F8FA"];
  query [label="检索时以knowledge_id回查MySQL\n过滤失效条目并补充summary、同步状态等字段"];

  strategy [label="应用层一致性与恢复策略\n新增：先写MySQL；同步失败标记failed\n更新：暂不提交MySQL；向量失败则回滚\n删除：先删向量；MySQL失败则恢复并标记delete_failed\n恢复：单条重试／全量重建；Chroma句柄异常重试1次"];
  boundary [label="边界：上述机制是应用层补偿，\n不是MySQL与Chroma的分布式事务", style="rounded,dashed,filled", fillcolor="#FAFAFA"];

  mysql -> text -> embed -> chroma;
  chroma -> query -> mysql [label="一致性校验与字段回填"];
  strategy -> mysql [style=dashed];
  strategy -> chroma [style=dashed];
  boundary -> strategy [style=dashed, arrowhead=none];
}}''',

    "fig4-9-user-page-structure": rf'''digraph G {{
{COMMON}
  rankdir=LR; splines=ortho;
  layout [label="UserLayout用户端框架\n公共导航与内容出口", fillcolor="#EAF2F8", color="#5B7C99"];
  public [label="公开访问", shape=tab, fillcolor="#F2F5F7"];
  guest [label="仅未登录访问", shape=tab, fillcolor="#F2F5F7"];
  auth [label="需登录访问", shape=tab, fillcolor="#F2F5F7"];
  home [label="首页  /"];
  detect [label="新闻检测  /detect\n文本输入｜URL提取预览｜联网开关"];
  result [label="检测结果  /result/:id\n评分｜风险等级｜证据｜报告操作"];
  high [label="高风险新闻  /high-risk\n公开列表、排行、关键词与分类"];
  login [label="登录  /login"];
  register [label="注册  /register"];
  history [label="历史记录  /history\n筛选、分页、详情与重新评估"];
  profile [label="个人中心  /profile"];

  layout -> public; layout -> guest; layout -> auth;
  public -> home; public -> detect; public -> result; public -> high;
  guest -> login; guest -> register;
  auth -> history; auth -> profile;
}}''',

    "fig4-10-admin-page-structure": rf'''digraph G {{
{COMMON}
  rankdir=LR; splines=ortho;
  layout [label="AdminLayout管理员后台\n前端路由守卫＋后端管理员依赖双重校验", fillcolor="#EAF2F8", color="#5B7C99"];
  overview [label="运行概览与分析", shape=tab, fillcolor="#F2F5F7"];
  business [label="核心业务管理", shape=tab, fillcolor="#F2F5F7"];
  governance [label="配置与审计", shape=tab, fillcolor="#F2F5F7"];
  dash [label="后台首页  /admin/dashboard"];
  stats [label="数据统计  /admin/statistics"];
  users [label="用户管理  /admin/users"];
  detections [label="检测记录  /admin/detections"];
  knowledge [label="知识库管理  /admin/knowledge\n条目维护｜单条向量化｜全量重建"];
  high [label="高风险管理  /admin/high-risk\n复核｜公开状态｜备注"];
  reports [label="报告管理  /admin/reports"];
  prompts [label="Prompt模板  /admin/prompts"];
  logs [label="系统日志  /admin/logs"];

  layout -> overview; layout -> business; layout -> governance;
  overview -> dash; overview -> stats;
  business -> users; business -> detections; business -> knowledge; business -> high; business -> reports;
  governance -> prompts; governance -> logs;
}}''',
}


def render(name: str, source: str) -> None:
    dot_path = OUT / f"{name}.dot"
    dot_path.write_text(source.strip() + "\n", encoding="utf-8")
    for fmt in ("svg", "emf", "png"):
        output = OUT / f"{name}.{fmt}"
        subprocess.run(
            ["dot", f"-T{fmt}", "-Gdpi=144", str(dot_path), "-o", str(output)],
            check=True,
        )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, source in FIGURES.items():
        render(name, source)
    print(f"generated {len(FIGURES)} figures in {OUT}")


if __name__ == "__main__":
    main()
