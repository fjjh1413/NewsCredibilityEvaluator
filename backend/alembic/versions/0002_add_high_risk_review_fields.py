"""Add high-risk review fields."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_add_high_risk_review_fields"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def bigint_id() -> sa.BigInteger:
    return sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.add_column(
        "detection_records",
        sa.Column(
            "review_status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "detection_records",
        sa.Column(
            "is_public",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "detection_records",
        sa.Column("admin_remark", sa.Text(), nullable=True),
    )
    op.add_column(
        "detection_records",
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "detection_records",
        sa.Column("reviewed_by", bigint_id(), nullable=True),
    )

    op.execute(
        "UPDATE detection_records "
        "SET is_high_risk = 1 "
        "WHERE final_score < 40 OR risk_level = '高风险谣言'"
    )
    op.execute(
        "UPDATE detection_records "
        "SET review_status = 'pending', is_public = 0 "
        "WHERE is_high_risk = 1"
    )

    op.create_index(
        "idx_detection_review_status",
        "detection_records",
        ["review_status"],
    )
    op.create_index(
        "idx_detection_is_public",
        "detection_records",
        ["is_public"],
    )
    op.create_index(
        "idx_detection_reviewed_by",
        "detection_records",
        ["reviewed_by"],
    )
    op.create_foreign_key(
        "fk_detection_reviewed_by",
        "detection_records",
        "users",
        ["reviewed_by"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_detection_reviewed_by",
        "detection_records",
        type_="foreignkey",
    )
    op.drop_index("idx_detection_reviewed_by", table_name="detection_records")
    op.drop_index("idx_detection_is_public", table_name="detection_records")
    op.drop_index("idx_detection_review_status", table_name="detection_records")
    op.drop_column("detection_records", "reviewed_by")
    op.drop_column("detection_records", "reviewed_at")
    op.drop_column("detection_records", "admin_remark")
    op.drop_column("detection_records", "is_public")
    op.drop_column("detection_records", "review_status")
