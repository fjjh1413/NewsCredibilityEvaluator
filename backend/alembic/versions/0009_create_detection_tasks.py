"""Create detection task table for async detection jobs."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0009_detection_tasks"
down_revision = "0008_performance_indexes"
branch_labels = None
depends_on = None


def _bigint_type() -> sa.BigInteger:
    return sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "detection_tasks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("celery_task_id", sa.String(length=100), nullable=True),
        sa.Column("user_id", _bigint_type(), nullable=True),
        sa.Column("detection_id", _bigint_type(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="queued",
            nullable=False,
        ),
        sa.Column("request_payload", sa.Text(), nullable=False),
        sa.Column("result_payload", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["detection_id"], ["detection_records.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_detection_task_user_created",
        "detection_tasks",
        ["user_id", "created_at", "id"],
    )
    op.create_index(
        "idx_detection_task_status_created",
        "detection_tasks",
        ["status", "created_at", "id"],
    )
    op.create_index(
        "idx_detection_task_detection_id",
        "detection_tasks",
        ["detection_id"],
    )
    op.create_index(
        "idx_detection_task_celery_task_id",
        "detection_tasks",
        ["celery_task_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_detection_task_celery_task_id", table_name="detection_tasks")
    op.drop_index("idx_detection_task_detection_id", table_name="detection_tasks")
    op.drop_index("idx_detection_task_status_created", table_name="detection_tasks")
    op.drop_index("idx_detection_task_user_created", table_name="detection_tasks")
    op.drop_table("detection_tasks")

