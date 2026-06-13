"""Add updated_at to core business tables."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0004_add_business_updated_at"
down_revision = "0003_add_system_logs"
branch_labels = None
depends_on = None


BUSINESS_TABLES = ("detection_records", "evidence_matches", "reports")


def upgrade() -> None:
    for table_name in BUSINESS_TABLES:
        _add_updated_at(table_name)


def downgrade() -> None:
    for table_name in reversed(BUSINESS_TABLES):
        op.drop_column(table_name, "updated_at")


def _add_updated_at(table_name: str) -> None:
    op.add_column(table_name, sa.Column("updated_at", sa.DateTime(), nullable=True))
    op.execute(
        sa.text(
            f"UPDATE {table_name} "
            "SET updated_at = created_at "
            "WHERE updated_at IS NULL"
        )
    )
    _alter_updated_at_not_null(table_name)


def _alter_updated_at_not_null(table_name: str) -> None:
    server_default = sa.text("CURRENT_TIMESTAMP")
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table(table_name, recreate="always") as batch_op:
            batch_op.alter_column(
                "updated_at",
                existing_type=sa.DateTime(),
                nullable=False,
                server_default=server_default,
            )
        return

    op.alter_column(
        table_name,
        "updated_at",
        existing_type=sa.DateTime(),
        nullable=False,
        server_default=server_default,
    )
