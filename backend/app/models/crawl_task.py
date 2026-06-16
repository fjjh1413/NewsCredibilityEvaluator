from sqlalchemy import BigInteger, Column, DateTime, Index, Integer, String, Text, func

from app.db.base_class import Base


class CrawlTask(Base):
    """Execution log for scheduled news crawl jobs.

    One row per crawl job execution, recording how many results were found,
    how many were newly added to the knowledge base, and any errors encountered.
    """

    __tablename__ = "crawl_tasks"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    job_name = Column(String(100), nullable=False, comment="抓取任务名称")
    search_query = Column(String(500), nullable=False, comment="实际搜索 query")
    freshness = Column(String(50), nullable=False, comment="搜索时间范围")
    total_found = Column(Integer, nullable=False, default=0, comment="Bocha 返回条目数")
    new_added = Column(Integer, nullable=False, default=0, comment="新增入库数")
    duplicates = Column(Integer, nullable=False, default=0, comment="去重跳过数")
    fetch_failed = Column(Integer, nullable=False, default=0, comment="全文抓取失败数")
    errors = Column(Text, nullable=True, comment="错误摘要")
    started_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        comment="开始时间",
    )
    finished_at = Column(DateTime, nullable=True, comment="完成时间")
    status = Column(
        String(20),
        nullable=False,
        default="running",
        server_default="running",
        comment="running / success / partial / failed",
    )

    __table_args__ = (
        Index("idx_crawl_tasks_job", "job_name"),
        Index("idx_crawl_tasks_time", "started_at"),
    )
