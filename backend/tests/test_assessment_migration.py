import importlib.util
import json
from pathlib import Path
import unittest

from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa


class AssessmentMigrationTests(unittest.TestCase):
    def test_upgrade_preserves_completed_scores_and_backfills_known_abstentions(self):
        path = Path(__file__).resolve().parents[1] / "alembic/versions/0012_detection_assessment.py"
        spec = importlib.util.spec_from_file_location("assessment_migration", path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        engine = sa.create_engine("sqlite:///:memory:")
        with engine.begin() as conn:
            conn.execute(sa.text("""CREATE TABLE detection_records (
                id INTEGER PRIMARY KEY, analysis_payload TEXT, final_score NUMERIC(5,2) NOT NULL,
                risk_level VARCHAR(30), judgement_result VARCHAR(100), is_high_risk BOOLEAN,
                is_public BOOLEAN)"""))
            conn.execute(sa.text("CREATE TABLE evidence_matches (id INTEGER PRIMARY KEY, detection_id INTEGER)"))
            snapshots = [
                {"arbitration_status": "provider_error", "quality_status": "unavailable"},
                {"arbitration_status": "no_evidence", "quality_status": "no_evidence"},
                {"arbitration_status": "ok", "quality_status": "ok", "evidence_quality": {"coverage": 80}},
                {},
                {"arbitration_status": "ok", "quality_status": "ok"},
                {"arbitration_status": "ok", "quality_status": "ok", "evidence_quality": {"coverage": 0}},
                {"arbitration_status": "ok", "quality_status": "ok", "evidence_quality": {"coverage": 101}},
            ]
            for record_id, payload in enumerate(snapshots, 1):
                conn.execute(sa.text("INSERT INTO detection_records VALUES (:id, :payload, 99, '可信新闻', '旧判断', 1, 1)"),
                             {"id": record_id, "payload": json.dumps(payload)})
            conn.execute(sa.text("INSERT INTO evidence_matches VALUES (1, 3)"))
            conn.execute(sa.text("INSERT INTO evidence_matches VALUES (2, 6)"))
            conn.execute(sa.text("INSERT INTO evidence_matches VALUES (3, 7)"))
            context = MigrationContext.configure(conn)
            with Operations.context(context):
                migration.upgrade()
            rows = conn.execute(sa.text("SELECT id, assessment_status, final_score, risk_level, is_high_risk, is_public FROM detection_records ORDER BY id")).mappings().all()
            self.assertEqual([r["assessment_status"] for r in rows], ["degraded", "insufficient_evidence", "completed", "legacy", "insufficient_evidence", "insufficient_evidence", "degraded"])
            for index in (0, 1, 4, 5, 6):
                self.assertIsNone(rows[index]["final_score"])
                self.assertEqual(rows[index]["risk_level"], "无法判断")
                self.assertFalse(rows[index]["is_high_risk"])
                self.assertFalse(rows[index]["is_public"])
            self.assertEqual(rows[2]["final_score"], 99)
            self.assertEqual(rows[3]["final_score"], 99)
            with Operations.context(context):
                with self.assertRaisesRegex(RuntimeError, "unscored records"):
                    migration.downgrade()
        engine.dispose()


if __name__ == "__main__":
    unittest.main()
