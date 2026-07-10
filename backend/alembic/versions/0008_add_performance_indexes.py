"""Add composite indexes for performance-critical list and statistics queries."""

from __future__ import annotations

from alembic import op


revision = "0008_performance_indexes"
down_revision = "0007_analysis_payload"
branch_labels = None
depends_on = None


DETECTION_INDEXES = (
    ("idx_detection_user_created", ["user_id", "created_at", "id"]),
    ("idx_detection_created_risk", ["created_at", "risk_level"]),
    ("idx_detection_created_category", ["created_at", "category"]),
    ("idx_detection_created_user", ["created_at", "user_id"]),
    ("idx_detection_high_created", ["is_high_risk", "created_at", "id"]),
    (
        "idx_detection_public_high_reviewed",
        [
            "is_public",
            "is_high_risk",
            "review_status",
            "reviewed_at",
            "created_at",
            "id",
        ],
    ),
    (
        "idx_detection_public_high_score",
        [
            "is_public",
            "is_high_risk",
            "review_status",
            "final_score",
            "reviewed_at",
            "created_at",
            "id",
        ],
    ),
)

REPORT_INDEXES = (
    ("idx_report_created", ["created_at", "id"]),
    ("idx_report_user_created", ["user_id", "created_at", "id"]),
)


def upgrade() -> None:
    for name, columns in DETECTION_INDEXES:
        op.create_index(name, "detection_records", columns)

    for name, columns in REPORT_INDEXES:
        op.create_index(name, "reports", columns)


def downgrade() -> None:
    for name, _columns in reversed(REPORT_INDEXES):
        op.drop_index(name, table_name="reports")

    for name, _columns in reversed(DETECTION_INDEXES):
        op.drop_index(name, table_name="detection_records")
