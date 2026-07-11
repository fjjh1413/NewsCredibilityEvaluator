from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Index, Integer, String, Text, func

from app.db.base_class import Base


BigIntId = BigInteger().with_variant(Integer, "sqlite")


class KnowledgeIndexJob(Base):
    __tablename__ = "knowledge_index_jobs"

    id = Column(BigIntId, primary_key=True, autoincrement=True)
    knowledge_id = Column(
        BigIntId,
        ForeignKey("knowledge_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    operation = Column(
        String(20),
        nullable=False,
        default="upsert",
        server_default="upsert",
    )
    status = Column(
        String(20),
        nullable=False,
        default="queued",
        server_default="queued",
    )
    source = Column(String(100), nullable=True)
    attempts = Column(Integer, nullable=False, default=0, server_default="0")
    max_attempts = Column(Integer, nullable=False, default=3, server_default="3")
    error_message = Column(Text, nullable=True)
    next_attempt_at = Column(DateTime, nullable=True, server_default=func.now())
    locked_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("idx_knowledge_index_jobs_status_next", "status", "next_attempt_at", "id"),
        Index("idx_knowledge_index_jobs_knowledge_status", "knowledge_id", "status"),
        Index("idx_knowledge_index_jobs_created", "created_at", "id"),
    )
