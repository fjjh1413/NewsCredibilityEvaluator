"""Create knowledge index job table for async vector indexing."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0010_knowledge_index_jobs"
down_revision = "0009_detection_tasks"
branch_labels = None
depends_on = None


def _bigint_type() -> sa.BigInteger:
    return sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "knowledge_index_jobs",
        sa.Column("id", _bigint_type(), autoincrement=True, nullable=False),
        sa.Column("knowledge_id", _bigint_type(), nullable=False),
        sa.Column(
            "operation",
            sa.String(length=20),
            server_default="upsert",
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="queued",
            nullable=False,
        ),
        sa.Column("source", sa.String(length=100), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column("locked_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["knowledge_id"], ["knowledge_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_knowledge_index_jobs_status_next",
        "knowledge_index_jobs",
        ["status", "next_attempt_at", "id"],
    )
    op.create_index(
        "idx_knowledge_index_jobs_knowledge_status",
        "knowledge_index_jobs",
        ["knowledge_id", "status"],
    )
    op.create_index(
        "idx_knowledge_index_jobs_created",
        "knowledge_index_jobs",
        ["created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("idx_knowledge_index_jobs_created", table_name="knowledge_index_jobs")
    op.drop_index(
        "idx_knowledge_index_jobs_knowledge_status",
        table_name="knowledge_index_jobs",
    )
    op.drop_index(
        "idx_knowledge_index_jobs_status_next",
        table_name="knowledge_index_jobs",
    )
    op.drop_table("knowledge_index_jobs")
