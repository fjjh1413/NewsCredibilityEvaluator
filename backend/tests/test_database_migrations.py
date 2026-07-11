import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.schemas.user import UserAdminCreate


class MigrationGuardTestCase(unittest.TestCase):
    def test_guard_raises_when_database_has_no_alembic_revision(self) -> None:
        from app.db import migration_guard

        with (
            patch(
                "app.db.migration_guard.get_head_revisions",
                return_value={"0006_create_crawl_tasks"},
            ),
            patch("app.db.migration_guard.get_current_revisions", return_value=set()),
        ):
            with self.assertRaisesRegex(RuntimeError, "alembic upgrade head"):
                migration_guard.assert_database_at_head()

    def test_guard_raises_when_database_is_behind_head(self) -> None:
        from app.db import migration_guard

        with (
            patch(
                "app.db.migration_guard.get_head_revisions",
                return_value={"0006_create_crawl_tasks"},
            ),
            patch(
                "app.db.migration_guard.get_current_revisions",
                return_value={"0002_add_high_risk_review_fields"},
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "alembic upgrade head"):
                migration_guard.assert_database_at_head()

    def test_guard_allows_database_at_head(self) -> None:
        from app.db import migration_guard

        with (
            patch(
                "app.db.migration_guard.get_head_revisions",
                return_value={"0006_create_crawl_tasks"},
            ),
            patch(
                "app.db.migration_guard.get_current_revisions",
                return_value={"0006_create_crawl_tasks"},
            ),
        ):
            migration_guard.assert_database_at_head()


class InitDbMigrationTestCase(unittest.TestCase):
    def test_init_db_requires_alembic_head_and_does_not_create_tables(self) -> None:
        from app.db import init_db

        superuser = UserAdminCreate(
            username="admin",
            password="strong-password",
            email="admin@example.com",
            role="admin",
            status="active",
        )
        existing_user = SimpleNamespace(username="admin")

        with (
            patch("app.db.init_db.assert_database_at_head") as assert_at_head,
            patch("sqlalchemy.schema.MetaData.create_all") as create_all,
            patch("app.db.init_db._build_superuser_payload", return_value=superuser),
            patch("app.db.init_db.get_user_by_username", return_value=existing_user),
        ):
            created, message = init_db.init_db(Mock())

        self.assertFalse(created)
        self.assertIn("Admin user already exists", message)
        assert_at_head.assert_called_once_with()
        create_all.assert_not_called()


class SeedDemoDataMigrationTestCase(unittest.TestCase):
    def test_seed_schema_check_requires_alembic_head_and_does_not_create_tables(
        self,
    ) -> None:
        from app.db import seed_demo_data

        columns_by_table = {
            "users": {"username", "password_hash", "role", "status"},
            "knowledge_items": {
                "title",
                "content",
                "category",
                "truth_label",
                "source_name",
                "summary",
                "keywords",
                "risk_level",
                "vector_sync_status",
            },
            "detection_records": {
                "user_id",
                "input_title",
                "input_content",
                "category",
                "keywords",
                "final_score",
                "evidence_score",
                "llm_score",
                "rule_score",
                "risk_level",
                "judgement_result",
                "reason",
                "risk_points",
                "suggestion",
                "is_high_risk",
                "review_status",
                "is_public",
                "admin_remark",
                "reviewed_at",
                "reviewed_by",
                "report_url",
                "updated_at",
            },
            "evidence_matches": {
                "detection_id",
                "knowledge_id",
                "title",
                "summary",
                "source_name",
                "similarity_score",
                "rank_order",
                "updated_at",
            },
            "reports": {"detection_id", "pdf_path", "updated_at"},
            "prompt_templates": {"name", "type", "content", "is_default", "status"},
            "system_logs": {"user_id", "action", "module", "created_at"},
        }

        inspector = Mock()
        inspector.get_table_names.return_value = list(columns_by_table)
        inspector.get_columns.side_effect = lambda table_name: [
            {"name": column_name} for column_name in columns_by_table[table_name]
        ]

        with (
            patch("app.db.seed_demo_data.assert_database_at_head") as assert_at_head,
            patch("sqlalchemy.schema.MetaData.create_all") as create_all,
            patch("app.db.seed_demo_data.inspect", return_value=inspector),
        ):
            seed_demo_data.ensure_schema_ready()

        assert_at_head.assert_called_once_with()
        create_all.assert_not_called()


class AlembicSchemaCoverageTestCase(unittest.TestCase):
    def test_crawl_tasks_table_is_managed_by_alembic(self) -> None:
        versions_dir = (
            Path(__file__).resolve().parents[1] / "alembic" / "versions"
        )
        migration_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in versions_dir.glob("*.py")
        )

        self.assertIn('"crawl_tasks"', migration_text)
        self.assertIn('revision = "0005_add_evidence_web_source"', migration_text)
        self.assertIn('down_revision = "0005_add_evidence_web_source"', migration_text)

    def test_knowledge_index_jobs_table_is_managed_by_alembic(self) -> None:
        versions_dir = (
            Path(__file__).resolve().parents[1] / "alembic" / "versions"
        )
        migration_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in versions_dir.glob("*.py")
        )

        self.assertIn('"knowledge_index_jobs"', migration_text)
        self.assertIn('revision = "0010_knowledge_index_jobs"', migration_text)
        self.assertIn('down_revision = "0009_detection_tasks"', migration_text)


if __name__ == "__main__":
    unittest.main()
