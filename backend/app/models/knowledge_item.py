from sqlalchemy import BigInteger, Column, DateTime, Index, String, Text, func

from app.db.base_class import Base


class KnowledgeItem(Base):
    __tablename__ = "knowledge_items"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String(50), nullable=True)
    truth_label = Column(String(30), nullable=False)
    source_name = Column(String(100), nullable=True)
    source_url = Column(String(500), nullable=True)
    publish_time = Column(DateTime, nullable=True)
    summary = Column(Text, nullable=True)
    keywords = Column(String(500), nullable=True)
    debunking_explanation = Column(Text, nullable=True)
    risk_level = Column(String(30), nullable=True)
    admin_note = Column(Text, nullable=True)
    vector_id = Column(String(100), nullable=True)
    vector_sync_status = Column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
    )
    vector_sync_error = Column(Text, nullable=True)
    created_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("idx_category", "category"),
        Index("idx_truth_label", "truth_label"),
        Index("idx_risk_level", "risk_level"),
        Index("idx_vector_sync_status", "vector_sync_status"),
    )
