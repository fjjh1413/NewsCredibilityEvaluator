"""Persist LLM evidence arbitration results on detection records."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0007_analysis_payload"
down_revision = "0006_create_crawl_tasks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "detection_records",
        sa.Column("analysis_payload", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("detection_records", "analysis_payload")
