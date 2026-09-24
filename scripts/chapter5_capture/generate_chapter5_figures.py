from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FIGURE_DIR = ROOT / ".artifacts" / "docs" / "chapter5" / "chapter5_figures"

COMMON = """digraph G {
  graph [fontname="SimSun", rankdir=LR, bgcolor="white", pad="0.2", nodesep="0.45", ranksep="0.55"];
  node [shape=box, style="rounded,filled", fillcolor="#F8FBFE", color="#7BA7C7", penwidth=1.2, fontname="SimSun", fontsize=14, margin="0.12,0.08"];
  edge [color="#3B6F92", penwidth=1.3, arrowsize=0.75, fontname="SimSun", fontsize=12];
"""

CHARTS = {
    "fig5-1-call-chain": COMMON
    + """
  a [label="前端提交\\nDetectView"]; b [label="检测接口\\n/api/detect/news"]; c [label="检测业务服务\\ndetect_news_credibility"]; d [label="本地语义检索\\nChroma Top-10"]; e [label="按需联网补充\\nBocha Web Search"]; f [label="候选证据组织\\n去重/ID/稳定排序"]; g [label="模型分析与仲裁\\nDeepSeek JSON"]; h [label="分支式评分\\nS_L/S_E/S_R"]; i [label="MySQL持久化\\nrecord+analysis_payload"]; j [label="前端结果展示\\n证据/报告/降级"];
  a->b->c->d->e->f->g->h->i->j;
}
""",
    "fig5-2-url-ssrf": COMMON
    + """
  graph [rankdir=TB];
  a [label="用户输入URL"]; b [label="Pydantic校验\\nhttp/https"]; c [label="规范化URL\\n去fragment"]; d [label="DNS/地址检查\\n拒绝本机/私有/保留地址"]; e [label="HTTP请求\\n10s超时/2MB读取上限"]; f [label="重定向复检\\n最多3次"]; g [label="HTML解析\\n标题/正文/来源/时间"]; h [label="预览回填\\n用户确认后检测"]; x [label="异常返回422\\n不写入检测记录", fillcolor="#FFF7ED", color="#EA580C"];
  a->b->c->d->e->f->g->h;
  b->x [label="协议非法"]; d->x [label="地址不安全"]; e->x [label="超时/类型错误"]; g->x [label="标题或正文缺失"];
}
""",
    "fig5-3-local-rag": COMMON
    + """
  a [label="知识条目\\ntitle/content/summary/keywords等"]; b [label="DashScope Embedding\\ntext-embedding-v4/1024维"]; c [label="Chroma写入\\ncollection=knowledge_items\\nvector_id=knowledge:<id>"]; d [label="检测查询文本\\ntitle+content"]; e [label="Chroma Top-10\\ncosine距离"]; f [label="相似度换算\\nmax(0,1-distance)"]; g [label="MySQL回查\\nknowledge_id"]; h [label="候选证据\\n带当前业务字段"];
  a->b->c; d->b; b->e->f->g->h; c->e;
}
""",
    "fig5-4-candidates": COMMON
    + """
  a [label="本地RAG结果"]; b [label="触发规则\\n无候选/Top1低/有效数不足"]; c [label="联网搜索结果"]; d [label="标准化字段\\nsource_type/source_url/summary"]; e [label="去重\\nknowledge_id/url/标题+来源+时间"]; f [label="candidate_id\\nkb:<id>/web:<rank>"]; g [label="输入种子SHA排序\\n减少固定位置偏差"]; h [label="Prompt候选\\n最多10条"];
  a->b; b->c [label="需要补充"]; a->d; c->d; d->e->f->g->h;
}
""",
    "fig5-5-llm-contract": COMMON
    + """
  graph [rankdir=TB];
  a [label="构造RAG Prompt\\n任务/新闻/候选/JSON契约"]; b [label="DeepSeek调用\\n结构化JSON输出"]; c [label="JSON提取与字段归一"]; d [label="契约校验\\nID合法/完整覆盖/不重复/分数范围"]; e [label="有效证据\\nranked_evidence"]; f [label="排除证据\\nrejected_evidence"]; r [label="聚焦重试1次\\n只修复证据仲裁", fillcolor="#EFF6FF", color="#2563EB"]; x [label="仍失败\\n仲裁状态retry_exhausted\\n候选不参与证据质量", fillcolor="#FFF7ED", color="#EA580C"];
  a->b->c->d; d->e [label="通过"]; d->f [label="通过"]; d->r [label="失败"]; r->d; r->x [label="失败"];
}
""",
    "fig5-6-cross-store": COMMON
    + """
  graph [rankdir=TB];
  a [label="MySQL业务事实源\\nKnowledgeItem"]; b [label="生成Embedding"]; c [label="Chroma派生索引\\nupsert/delete"]; d [label="vector_sync_status\\nsynced/pending/failed/delete_failed"]; e [label="单条重试\\nvectorize接口"]; f [label="全量重建\\nreset collection+逐条同步"]; g [label="补偿处理\\n删除失败阻止MySQL删除\\nDB失败尝试恢复向量", fillcolor="#F0FDF4", color="#16A34A"]; h [label="崩溃窗口\\n硬终止仍可能留下中间状态", fillcolor="#FEF2F2", color="#DC2626"];
  a->b->c->d; d->e [label="failed"]; e->d; d->f [label="模型/维度变更"]; c->g; a->g; g->d; g->h [style=dashed];
}
""",
}


def main() -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    for name, dot in CHARTS.items():
        dot_path = FIGURE_DIR / f"{name}.dot"
        png_path = FIGURE_DIR / f"{name}.png"
        dot_path.write_text(dot, encoding="utf-8")
        subprocess.run(["dot", "-Tpng", str(dot_path), "-o", str(png_path)], check=True)
        print(png_path)


if __name__ == "__main__":
    main()
