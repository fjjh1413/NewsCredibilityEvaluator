"""Add system logs table."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_add_system_logs"
down_revision = "0002_add_high_risk_review_fields"
branch_labels = None
depends_on = None


def bigint_id() -> sa.BigInteger:
    return sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "system_logs",
        sa.Column("id", bigint_id(), primary_key=True, autoincrement=True),
        sa.Column("user_id", bigint_id(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("module", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(length=50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("idx_system_log_user_id", "system_logs", ["user_id"])
    op.create_index("idx_system_log_module", "system_logs", ["module"])
    op.create_index("idx_system_log_action", "system_logs", ["action"])
    op.create_index("idx_system_log_created_at", "system_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("system_logs")
