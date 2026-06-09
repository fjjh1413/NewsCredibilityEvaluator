import unittest
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.crud.detection_crud import save_detection_record
from app.db.base import Base
from app.models.detection_record import DetectionRecord
from app.models.user import User
from app.schemas.detection import DetectionCreate
from app.services.high_risk_service import (
    HighRiskConflictError,
    get_public_high_risk_categories,
    get_public_high_risk_keywords,
    list_admin_high_risk,
    list_public_high_risk,
    list_public_high_risk_ranking,
    update_high_risk_public_status,
    update_high_risk_review,
)


class HighRiskServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        TestingSessionLocal = sessionmaker(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.db = TestingSessionLocal()
        self.db.add(
            User(
                id=1,
                username="admin",
                email="admin@example.com",
                password_hash="hash",
                role="admin",
                status="active",
            )
        )
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def test_save_detection_auto_marks_score_below_40_and_defaults_private(self) -> None:
        record = save_detection_record(
            self.db,
            self._payload(final_score=39.9, risk_level="疑似谣言"),
        )

        self.assertTrue(record.is_high_risk)
        self.assertEqual(record.review_status, "pending")
        self.assertFalse(record.is_public)

    def test_save_detection_auto_marks_high_risk_level(self) -> None:
        record = save_detection_record(
            self.db,
            self._payload(final_score=75, risk_level="高风险谣言"),
        )

        self.assertTrue(record.is_high_risk)

    def test_public_list_strictly_filters_and_does_not_leak_sensitive_fields(self) -> None:
        visible = self._record(
            1,
            score=20,
            review_status="approved",
            is_public=True,
            title="公开记录",
            keywords="网传,官方",
            category="社会",
        )
        self.db.add_all(
            [
                visible,
                self._record(2, review_status="pending", is_public=True),
                self._record(3, review_status="rejected", is_public=True),
                self._record(4, review_status="approved", is_public=False),
                self._record(
                    5,
                    review_status="approved",
                    is_public=True,
                    is_high_risk=False,
                ),
            ]
        )
        self.db.commit()

        items, total = list_public_high_risk(self.db)

        self.assertEqual(total, 1)
        self.assertEqual(items[0]["title"], "公开记录")
        self.assertNotIn("input_content", items[0])
        self.assertNotIn("admin_remark", items[0])
        self.assertNotIn("review_status", items[0])
        self.assertNotIn("is_public", items[0])
        self.assertLessEqual(len(items[0]["summary"]), 153)
        self.assertEqual(
            get_public_high_risk_keywords(self.db),
            [{"keyword": "网传", "count": 1}, {"keyword": "官方", "count": 1}],
        )
        self.assertEqual(
            get_public_high_risk_categories(self.db),
            [{"category": "社会", "count": 1}],
        )

    def test_public_ranking_uses_lowest_score_then_latest_time(self) -> None:
        now = datetime(2026, 6, 4, 12, 0, 0)
        first = self._record(1, score=20, title="较早低分")
        second = self._record(2, score=20, title="较新低分")
        third = self._record(3, score=30, title="较高分")
        first.reviewed_at = now - timedelta(days=1)
        second.reviewed_at = now
        third.reviewed_at = now
        self.db.add_all([first, second, third])
        self.db.commit()

        ranking = list_public_high_risk_ranking(self.db)

        self.assertEqual(
            [item["title"] for item in ranking],
            ["较新低分", "较早低分", "较高分"],
        )

    def test_review_and_public_rules_force_non_approved_records_private(self) -> None:
        record = self._record(1, review_status="pending", is_public=False)
        self.db.add(record)
        self.db.commit()

        with self.assertRaises(HighRiskConflictError):
            update_high_risk_public_status(self.db, record.id, True)

        approved = update_high_risk_review(
            self.db,
            record.id,
            "approved",
            admin_id=1,
            admin_remark="审核通过",
        )
        self.assertEqual(approved["review_status"], "approved")
        self.assertFalse(approved["is_public"])

        published = update_high_risk_public_status(self.db, record.id, True)
        self.assertTrue(published["is_public"])

        rejected = update_high_risk_review(
            self.db,
            record.id,
            "rejected",
            admin_id=1,
        )
        self.assertFalse(rejected["is_public"])

    def test_admin_list_contains_all_high_risk_review_states(self) -> None:
        self.db.add_all(
            [
                self._record(1, review_status="pending", is_public=False),
                self._record(2, review_status="approved", is_public=True),
                self._record(3, review_status="rejected", is_public=False),
                self._record(4, is_high_risk=False),
            ]
        )
        self.db.commit()

        items, total = list_admin_high_risk(self.db)

        self.assertEqual(total, 3)
        self.assertEqual({item["review_status"] for item in items}, {"pending", "approved", "rejected"})

    def _payload(self, final_score: float, risk_level: str) -> DetectionCreate:
        return DetectionCreate(
            user_id=1,
            input_title="测试新闻",
            input_content="用于验证高风险自动标记的新闻正文。",
            category="社会",
            keywords="测试",
            final_score=final_score,
            evidence_score=50,
            llm_score=50,
            rule_score=50,
            risk_level=risk_level,
            judgement_result="需要核查",
            is_high_risk=False,
        )

    def _record(
        self,
        record_id: int,
        score: float = 25,
        review_status: str = "approved",
        is_public: bool = True,
        is_high_risk: bool = True,
        title: str | None = None,
        keywords: str = "网传",
        category: str = "社会",
    ) -> DetectionRecord:
        return DetectionRecord(
            id=record_id,
            user_id=1,
            input_title=title or f"新闻 {record_id}",
            input_content=("这是仅允许在服务端生成摘要的完整新闻正文。" * 20),
            category=category,
            keywords=keywords,
            final_score=score,
            evidence_score=50,
            llm_score=50,
            rule_score=50,
            risk_level="高风险谣言",
            judgement_result="存在较高风险",
            reason="需要管理员复核",
            risk_points='["来源不明"]',
            suggestion="查阅权威来源",
            is_high_risk=is_high_risk,
            review_status=review_status,
            is_public=is_public,
            admin_remark="内部审核备注",
            reviewed_at=datetime(2026, 6, 4, 10, 0, 0),
            reviewed_by=1,
            created_at=datetime(2026, 6, 3, 10, 0, 0),
        )


if __name__ == "__main__":
    unittest.main()
