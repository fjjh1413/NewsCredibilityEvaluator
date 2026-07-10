import unittest
from pathlib import Path

from app.models.detection_record import DetectionRecord
from app.models.report import Report


EXPECTED_DETECTION_INDEXES = {
    "idx_detection_user_created": ("user_id", "created_at", "id"),
    "idx_detection_created_risk": ("created_at", "risk_level"),
    "idx_detection_created_category": ("created_at", "category"),
    "idx_detection_created_user": ("created_at", "user_id"),
    "idx_detection_high_created": ("is_high_risk", "created_at", "id"),
    "idx_detection_public_high_reviewed": (
        "is_public",
        "is_high_risk",
        "review_status",
        "reviewed_at",
        "created_at",
        "id",
    ),
    "idx_detection_public_high_score": (
        "is_public",
        "is_high_risk",
        "review_status",
        "final_score",
        "reviewed_at",
        "created_at",
        "id",
    ),
}

EXPECTED_REPORT_INDEXES = {
    "idx_report_created": ("created_at", "id"),
    "idx_report_user_created": ("user_id", "created_at", "id"),
}


class PerformanceIndexTestCase(unittest.TestCase):
    def test_detection_record_model_declares_hot_path_indexes(self) -> None:
        indexes = _index_columns(DetectionRecord)

        for name, columns in EXPECTED_DETECTION_INDEXES.items():
            with self.subTest(index=name):
                self.assertEqual(indexes.get(name), columns)

    def test_report_model_declares_hot_path_indexes(self) -> None:
        indexes = _index_columns(Report)

        for name, columns in EXPECTED_REPORT_INDEXES.items():
            with self.subTest(index=name):
                self.assertEqual(indexes.get(name), columns)

    def test_performance_index_migration_creates_and_drops_indexes(self) -> None:
        migration = (
            Path(__file__).resolve().parents[1]
            / "alembic"
            / "versions"
            / "0008_add_performance_indexes.py"
        )
        text = migration.read_text(encoding="utf-8")

        for name in (*EXPECTED_DETECTION_INDEXES, *EXPECTED_REPORT_INDEXES):
            with self.subTest(index=name):
                self.assertIn(f'"{name}"', text)
                self.assertIn(f"op.drop_index(name", text)


def _index_columns(model) -> dict[str, tuple[str, ...]]:
    return {
        index.name: tuple(column.name for column in index.columns)
        for index in model.__table__.indexes
    }


if __name__ == "__main__":
    unittest.main()
