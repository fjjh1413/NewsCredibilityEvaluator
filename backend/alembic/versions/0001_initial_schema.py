"""Create initial application schema."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def bigint_id() -> sa.BigInteger:
    return sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def table_options() -> dict[str, str]:
    return {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=100), nullable=True),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("username"),
        **table_options(),
    )

    op.create_table(
        "knowledge_items",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=True),
        sa.Column("truth_label", sa.String(length=30), nullable=False),
        sa.Column("source_name", sa.String(length=100), nullable=True),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("publish_time", sa.DateTime(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("keywords", sa.String(length=500), nullable=True),
        sa.Column("debunking_explanation", sa.Text(), nullable=True),
        sa.Column("risk_level", sa.String(length=30), nullable=True),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("vector_id", sa.String(length=100), nullable=True),
        sa.Column(
            "vector_sync_status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("vector_sync_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        **table_options(),
    )
    op.create_index("idx_category", "knowledge_items", ["category"])
    op.create_index("idx_truth_label", "knowledge_items", ["truth_label"])
    op.create_index("idx_risk_level", "knowledge_items", ["risk_level"])
    op.create_index(
        "idx_vector_sync_status",
        "knowledge_items",
        ["vector_sync_status"],
    )

    op.create_table(
        "detection_records",
        sa.Column("id", bigint_id(), primary_key=True, autoincrement=True),
        sa.Column("user_id", bigint_id(), nullable=True),
        sa.Column("input_title", sa.String(length=255), nullable=False),
        sa.Column("input_content", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=True),
        sa.Column("keywords", sa.String(length=500), nullable=True),
        sa.Column("final_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("evidence_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("llm_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("rule_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("risk_level", sa.String(length=30), nullable=False),
        sa.Column("judgement_result", sa.String(length=100), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("risk_points", sa.Text(), nullable=True),
        sa.Column("suggestion", sa.Text(), nullable=True),
        sa.Column(
            "is_high_risk",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("report_url", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        **table_options(),
    )
    op.create_index("idx_detection_user_id", "detection_records", ["user_id"])
    op.create_index("idx_detection_risk_level", "detection_records", ["risk_level"])
    op.create_index(
        "idx_detection_is_high_risk",
        "detection_records",
        ["is_high_risk"],
    )
    op.create_index("idx_detection_created_at", "detection_records", ["created_at"])

    op.create_table(
        "evidence_matches",
        sa.Column("id", bigint_id(), primary_key=True, autoincrement=True),
        sa.Column("detection_id", bigint_id(), nullable=False),
        sa.Column("knowledge_id", bigint_id(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("source_name", sa.String(length=100), nullable=True),
        sa.Column("similarity_score", sa.Numeric(6, 4), nullable=False),
        sa.Column("rank_order", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["detection_id"],
            ["detection_records.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_id"],
            ["knowledge_items.id"],
            ondelete="SET NULL",
        ),
        **table_options(),
    )
    op.create_index(
        "idx_evidence_detection_id",
        "evidence_matches",
        ["detection_id"],
    )
    op.create_index(
        "idx_evidence_knowledge_id",
        "evidence_matches",
        ["knowledge_id"],
    )

    op.create_table(
        "prompt_templates",
        sa.Column("id", bigint_id(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "is_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="enabled",
        ),
        sa.Column("created_by", bigint_id(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        **table_options(),
    )
    op.create_index("idx_prompt_type", "prompt_templates", ["type"])
    op.create_index("idx_prompt_status", "prompt_templates", ["status"])
    op.create_index(
        "idx_prompt_type_default",
        "prompt_templates",
        ["type", "is_default"],
    )
    op.create_index("idx_prompt_created_by", "prompt_templates", ["created_by"])

    op.create_table(
        "reports",
        sa.Column("id", bigint_id(), primary_key=True, autoincrement=True),
        sa.Column("detection_id", bigint_id(), nullable=False),
        sa.Column("user_id", bigint_id(), nullable=True),
        sa.Column("report_title", sa.String(length=255), nullable=False),
        sa.Column("html_path", sa.String(length=500), nullable=True),
        sa.Column("pdf_path", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["detection_id"],
            ["detection_records.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("detection_id", name="uq_reports_detection_id"),
        **table_options(),
    )
    op.create_index("idx_report_user_id", "reports", ["user_id"])


def downgrade() -> None:
    op.drop_table("reports")
    op.drop_table("prompt_templates")
    op.drop_table("evidence_matches")
    op.drop_table("detection_records")
    op.drop_table("knowledge_items")
    op.drop_table("users")
