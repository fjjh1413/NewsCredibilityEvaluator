from sqlalchemy import (
    BigInteger,
    Boolean,
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


class DetectionRecord(Base):
    __tablename__ = "detection_records"

    id = Column(BigIntId, primary_key=True, autoincrement=True)
    user_id = Column(
        BigIntId,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    input_title = Column(String(255), nullable=False)
    input_content = Column(Text, nullable=False)
    category = Column(String(50), nullable=True)
    keywords = Column(String(500), nullable=True)
    final_score = Column(Numeric(5, 2), nullable=False)
    evidence_score = Column(Numeric(5, 2), nullable=False)
    llm_score = Column(Numeric(5, 2), nullable=False)
    rule_score = Column(Numeric(5, 2), nullable=False)
    risk_level = Column(String(30), nullable=False)
    judgement_result = Column(String(100), nullable=False)
    reason = Column(Text, nullable=True)
    risk_points = Column(Text, nullable=True)
    suggestion = Column(Text, nullable=True)
    is_high_risk = Column(Boolean, nullable=False, default=False, server_default="0")
    review_status = Column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
    )
    is_public = Column(Boolean, nullable=False, default=False, server_default="0")
    admin_remark = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(
        BigIntId,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    report_url = Column(String(500), nullable=True)
    created_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    evidence_matches = relationship(
        "EvidenceMatch",
        back_populates="detection",
        cascade="all, delete-orphan",
        order_by="EvidenceMatch.rank_order",
    )
    report = relationship(
        "Report",
        back_populates="detection",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )

    __table_args__ = (
        Index("idx_detection_user_id", "user_id"),
        Index("idx_detection_risk_level", "risk_level"),
        Index("idx_detection_is_high_risk", "is_high_risk"),
        Index("idx_detection_review_status", "review_status"),
        Index("idx_detection_is_public", "is_public"),
        Index("idx_detection_reviewed_by", "reviewed_by"),
        Index("idx_detection_created_at", "created_at"),
    )
