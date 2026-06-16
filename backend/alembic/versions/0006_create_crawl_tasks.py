"""Create crawl task execution log table."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0006_create_crawl_tasks"
down_revision = "0005_add_evidence_web_source"
branch_labels = None
depends_on = None


def bigint_id() -> sa.BigInteger:
    return sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "crawl_tasks",
        sa.Column("id", bigint_id(), primary_key=True, autoincrement=True),
        sa.Column("job_name", sa.String(length=100), nullable=False),
        sa.Column("search_query", sa.String(length=500), nullable=False),
        sa.Column("freshness", sa.String(length=50), nullable=False),
        sa.Column(
            "total_found",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "new_added",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "duplicates",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "fetch_failed",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("errors", sa.Text(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="running",
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("idx_crawl_tasks_job", "crawl_tasks", ["job_name"])
    op.create_index("idx_crawl_tasks_time", "crawl_tasks", ["started_at"])


def downgrade() -> None:
    op.drop_table("crawl_tasks")
