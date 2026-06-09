from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, func

from app.db.base_class import Base


BigIntId = BigInteger().with_variant(Integer, "sqlite")


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"

    id = Column(BigIntId, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    type = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    is_default = Column(Boolean, nullable=False, default=False, server_default="0")
    status = Column(String(20), nullable=False, default="enabled", server_default="enabled")
    created_by = Column(
        BigIntId,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
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
        Index("idx_prompt_type", "type"),
        Index("idx_prompt_status", "status"),
        Index("idx_prompt_type_default", "type", "is_default"),
        Index("idx_prompt_created_by", "created_by"),
    )
