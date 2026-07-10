from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Index, Integer, String, Text, func

from app.db.base_class import Base


BigIntId = BigInteger().with_variant(Integer, "sqlite")


class DetectionTask(Base):
    __tablename__ = "detection_tasks"

    id = Column(String(36), primary_key=True)
    celery_task_id = Column(String(100), nullable=True)
    user_id = Column(
        BigIntId,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    detection_id = Column(
        BigIntId,
        ForeignKey("detection_records.id", ondelete="SET NULL"),
        nullable=True,
    )
    status = Column(
        String(20),
        nullable=False,
        default="queued",
        server_default="queued",
    )
    request_payload = Column(Text, nullable=False)
    result_payload = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
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
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_detection_task_user_created", "user_id", "created_at", "id"),
        Index("idx_detection_task_status_created", "status", "created_at", "id"),
        Index("idx_detection_task_detection_id", "detection_id"),
        Index("idx_detection_task_celery_task_id", "celery_task_id"),
    )

