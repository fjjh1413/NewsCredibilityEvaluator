from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from app.db.base_class import Base


BigIntId = BigInteger().with_variant(Integer, "sqlite")


class EvidenceMatch(Base):
    __tablename__ = "evidence_matches"

    id = Column(BigIntId, primary_key=True, autoincrement=True)
    detection_id = Column(
        BigIntId,
        ForeignKey("detection_records.id", ondelete="CASCADE"),
        nullable=False,
    )
    knowledge_id = Column(
        BigIntId,
        ForeignKey("knowledge_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    title = Column(String(255), nullable=False)
    summary = Column(Text, nullable=True)
    source_name = Column(String(100), nullable=True)
    similarity_score = Column(Numeric(6, 4), nullable=False)
    rank_order = Column(Integer, nullable=False)
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

    detection = relationship("DetectionRecord", back_populates="evidence_matches")

    __table_args__ = (
        Index("idx_evidence_detection_id", "detection_id"),
        Index("idx_evidence_knowledge_id", "knowledge_id"),
    )
