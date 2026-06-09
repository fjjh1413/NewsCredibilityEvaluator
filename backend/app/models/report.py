from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.db.base_class import Base


BigIntId = BigInteger().with_variant(Integer, "sqlite")


class Report(Base):
    __tablename__ = "reports"

    id = Column(BigIntId, primary_key=True, autoincrement=True)
    detection_id = Column(
        BigIntId,
        ForeignKey("detection_records.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        BigIntId,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    report_title = Column(String(255), nullable=False)
    html_path = Column(String(500), nullable=True)
    pdf_path = Column(String(500), nullable=True)
    created_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    detection = relationship("DetectionRecord", back_populates="report")

    __table_args__ = (
        UniqueConstraint("detection_id", name="uq_reports_detection_id"),
        Index("idx_report_user_id", "user_id"),
    )
