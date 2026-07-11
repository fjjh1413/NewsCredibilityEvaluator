"""Extend system logs with structured audit context."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0011_system_log_audit_context"
down_revision = "0010_knowledge_index_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("system_logs", sa.Column("request_id", sa.String(length=128), nullable=True))
    op.add_column("system_logs", sa.Column("target_type", sa.String(length=100), nullable=True))
    op.add_column("system_logs", sa.Column("target_id", sa.String(length=100), nullable=True))
    op.add_column("system_logs", sa.Column("result_status", sa.String(length=20), nullable=True))
    op.add_column("system_logs", sa.Column("metadata_json", sa.JSON(), nullable=True))

    op.create_index("idx_system_log_request_id", "system_logs", ["request_id"])
    op.create_index("idx_system_log_target", "system_logs", ["target_type", "target_id"])
    op.create_index("idx_system_log_result_status", "system_logs", ["result_status"])


def downgrade() -> None:
    op.drop_index("idx_system_log_result_status", table_name="system_logs")
    op.drop_index("idx_system_log_target", table_name="system_logs")
    op.drop_index("idx_system_log_request_id", table_name="system_logs")

    op.drop_column("system_logs", "metadata_json")
    op.drop_column("system_logs", "result_status")
    op.drop_column("system_logs", "target_id")
    op.drop_column("system_logs", "target_type")
    op.drop_column("system_logs", "request_id")
