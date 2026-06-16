"""Add web source fields to evidence matches."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0005_add_evidence_web_source"
down_revision = "0004_add_business_updated_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "evidence_matches",
        sa.Column("url", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "evidence_matches",
        sa.Column(
            "origin",
            sa.String(length=20),
            nullable=False,
            server_default="knowledge",
        ),
    )
    op.create_index("idx_evidence_origin", "evidence_matches", ["origin"])


def downgrade() -> None:
    op.drop_index("idx_evidence_origin", table_name="evidence_matches")
    op.drop_column("evidence_matches", "origin")
    op.drop_column("evidence_matches", "url")
