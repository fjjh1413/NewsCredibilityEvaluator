import unittest
from datetime import datetime
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.crud.detection_crud import (
    delete_detection_record,
    get_detection_detail,
    get_detection_history,
    save_detection_record,
)
from app.db.base import Base
from app.schemas.detection import DetectionCreate, DetectionDetailOut


def _user(user_id: int, role: str = "user") -> SimpleNamespace:
    return SimpleNamespace(id=user_id, role=role)


def _payload(
    user_id: int,
    title: str = "Test news",
    risk_level: str = "存疑信息",
    analysis_payload: dict | None = None,
) -> DetectionCreate:
    return DetectionCreate(
        user_id=user_id,
        input_title=title,
        input_content="Test content",
        category="society",
        keywords="test,news",
        final_score=68.5,
        evidence_score=70,
        llm_score=65,
        rule_score=72,
        risk_level=risk_level,
        judgement_result="需要进一步核查",
        reason="证据不足。",
        risk_points=["来源不明确", "缺少权威证据"],
        suggestion="建议查看官方通报。",
        is_high_risk=False,
        report_url="/api/report/download/1",
        analysis_payload=analysis_payload or {},
        evidence_matches=[
            {
                "knowledge_id": 1,
                "title": "相似证据",
                "summary": "证据摘要",
                "source_name": "官方媒体",
                "similarity_score": 0.8321,
                "rank_order": 1,
            }
        ],
    )


def _set_created_at(db, record, created_at: datetime) -> None:
    record.created_at = created_at
    db.add(record)
    db.commit()
    db.refresh(record)


class DetectionCrudTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        self.addCleanup(self.engine.dispose)
        TestingSessionLocal = sessionmaker(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.db = TestingSessionLocal()
        self.addCleanup(self.db.close)

    def test_save_detection_record_with_evidence_matches(self) -> None:
        record = save_detection_record(self.db, _payload(user_id=1))

        self.assertIsNotNone(record.id)
        self.assertEqual(record.user_id, 1)
        self.assertEqual(len(record.evidence_matches), 1)
        self.assertEqual(record.evidence_matches[0].title, "相似证据")

        output = DetectionDetailOut.model_validate(record)
        self.assertEqual(output.risk_points, ["来源不明确", "缺少权威证据"])
        self.assertEqual(output.evidence_matches[0].rank_order, 1)
        self.assertIsNotNone(output.updated_at)
        self.assertIsNotNone(output.evidence_matches[0].updated_at)

    def test_save_detection_record_persists_analysis_payload(self) -> None:
        payload = {
            "arbitration_status": "ok",
            "knowledge_has_relevant_match": False,
            "web_has_relevant_match": True,
            "excluded_evidence": [{"candidate_id": "kb:5", "title": "Irrelevant"}],
            "similar_news": [
                {
                    "candidate_id": "web:1",
                    "title": "Related",
                    "risk_level": "可信新闻",
                }
            ],
        }

        record = save_detection_record(
            self.db,
            _payload(user_id=1, analysis_payload=payload),
        )

        self.assertIsInstance(record.analysis_payload, str)
        self.assertIn('"arbitration_status": "ok"', record.analysis_payload)

    def test_user_history_only_returns_own_records(self) -> None:
        save_detection_record(self.db, _payload(user_id=1, title="User 1 news"))
        save_detection_record(self.db, _payload(user_id=2, title="User 2 news"))

        items, total = get_detection_history(self.db, current_user=_user(1))

        self.assertEqual(total, 1)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].input_title, "User 1 news")

    def test_admin_history_can_see_all_records(self) -> None:
        save_detection_record(self.db, _payload(user_id=1, title="User 1 news"))
        save_detection_record(self.db, _payload(user_id=2, title="User 2 news"))

        items, total = get_detection_history(self.db, current_user=_user(99, "admin"))

        self.assertEqual(total, 2)
        self.assertEqual(len(items), 2)

    def test_admin_history_supports_filters(self) -> None:
        old_record = save_detection_record(
            self.db,
            _payload(user_id=1, title="Old suspicious news"),
        )
        new_record = save_detection_record(
            self.db,
            _payload(user_id=2, title="Fresh official news"),
        )
        _set_created_at(self.db, old_record, datetime(2026, 1, 1, 8, 0, 0))
        _set_created_at(self.db, new_record, datetime(2026, 1, 2, 8, 0, 0))

        items, total = get_detection_history(
            self.db,
            current_user=_user(99, "admin"),
            keyword="official",
            user_id=2,
            date_from=datetime(2026, 1, 2, 0, 0, 0),
            date_to=datetime(2026, 1, 2, 23, 59, 59),
        )

        self.assertEqual(total, 1)
        self.assertEqual(items[0].id, new_record.id)

    def test_history_keyword_matches_risk_level(self) -> None:
        suspicious_record = save_detection_record(
            self.db,
            _payload(user_id=1, title="Ordinary title"),
        )
        save_detection_record(
            self.db,
            _payload(
                user_id=1,
                title="Trusted official title",
                risk_level="可信新闻",
            ),
        )

        items, total = get_detection_history(
            self.db,
            current_user=_user(1),
            keyword="存疑",
        )

        self.assertEqual(total, 1)
        self.assertEqual(items[0].id, suspicious_record.id)

    def test_detail_respects_user_scope(self) -> None:
        record = save_detection_record(self.db, _payload(user_id=2))

        user_detail = get_detection_detail(
            self.db,
            detection_id=record.id,
            current_user=_user(1),
        )
        admin_detail = get_detection_detail(
            self.db,
            detection_id=record.id,
            current_user=_user(99, "admin"),
        )

        self.assertIsNone(user_detail)
        self.assertIsNotNone(admin_detail)
        self.assertEqual(admin_detail.id, record.id)

    def test_delete_detection_record(self) -> None:
        record = save_detection_record(self.db, _payload(user_id=1))

        self.assertTrue(delete_detection_record(self.db, record.id))
        self.assertFalse(delete_detection_record(self.db, record.id))
        self.assertIsNone(
            get_detection_detail(
                self.db,
                detection_id=record.id,
                current_user=_user(1),
            )
        )


if __name__ == "__main__":
    unittest.main()
