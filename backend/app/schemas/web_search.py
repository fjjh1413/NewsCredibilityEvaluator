from pydantic import BaseModel, Field


class BochaWebPage(BaseModel):
    """A single web page result from Bocha Web Search API."""

    name: str = Field(default="", description="网页标题")
    url: str = Field(default="", description="网页链接")
    snippet: str = Field(default="", description="搜索摘要")
    summary: str = Field(default="", description="文本摘要（summary=True 时返回）")
    site_name: str = Field(default="", description="网站名称")
    site_icon: str = Field(default="", description="网站图标 URL")
    date_published: str = Field(default="", description="发布时间")


class BochaSearchResponse(BaseModel):
    """Parsed response from Bocha Web Search API."""

    webpages: list[BochaWebPage] = Field(default_factory=list)
    total_count: int = Field(default=0)


class WebEvidenceItem(BaseModel):
    """Unified evidence item from web search, ready for LLM consumption."""

    title: str
    url: str = ""
    summary: str = ""
    site_name: str = ""
    date_published: str = ""
    similarity_score: float = 0.0
    source_type: str = "web_search"
    source_label: str = "🌐 网络检索"
    rank_order: int = 0


class WebSearchMeta(BaseModel):
    """Metadata about a web search execution."""

    triggered: bool = False
    sources_count: int = 0
    query: str = ""
    error: str = ""
