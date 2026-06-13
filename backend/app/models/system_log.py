from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.db.base_class import Base


BigIntId = BigInteger().with_variant(Integer, "sqlite")


class SystemLog(Base):
    __tablename__ = "system_logs"

    id = Column(BigIntId, primary_key=True, autoincrement=True)
    user_id = Column(
        BigIntId,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    action = Column(String(100), nullable=False)
    module = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    ip_address = Column(String(50), nullable=True)
    created_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    user = relationship("User")

    __table_args__ = (
        Index("idx_system_log_user_id", "user_id"),
        Index("idx_system_log_module", "module"),
        Index("idx_system_log_action", "action"),
        Index("idx_system_log_created_at", "created_at"),
    )
