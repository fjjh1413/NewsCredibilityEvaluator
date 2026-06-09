import unittest
from datetime import date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.detection_record import DetectionRecord
from app.models.knowledge_item import KnowledgeItem
from app.models.report import Report
from app.models.user import User
from app.services.statistics_service import (
    StatisticsRangeError,
    get_category_distribution,
    get_detection_trend,
    get_keyword_statistics,
    get_knowledge_overview,
    get_risk_distribution,
    get_statistics_overview,
    get_user_activity,
)


class StatisticsServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        TestingSessionLocal = sessionmaker(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.db = TestingSessionLocal()
        self._seed_data()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def test_overview_returns_real_counts(self) -> None:
        result = get_statistics_overview(self.db, today=date(2026, 6, 2))

        self.assertEqual(
            result,
            {
                "total_detections": 4,
                "today_detections": 2,
                "total_users": 3,
                "total_knowledge": 3,
                "total_high_risk": 1,
                "total_reports": 1,
            },
        )

    def test_trend_fills_dates_without_detections(self) -> None:
        result = get_detection_trend(
            self.db,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 4),
        )

        self.assertEqual(
            result["dates"],
            ["2026-06-01", "2026-06-02", "2026-06-03", "2026-06-04"],
        )
        self.assertEqual(result["counts"], [1, 2, 1, 0])

    def test_risk_and_category_distributions_use_real_fields_and_range(self) -> None:
        risk = get_risk_distribution(
            self.db,
            start_date=date(2026, 6, 2),
            end_date=date(2026, 6, 2),
        )
        categories = get_category_distribution(self.db)

        self.assertEqual(
            {item["name"]: item["value"] for item in risk},
            {"高风险谣言": 1, "存疑信息": 1},
        )
        self.assertEqual(
            {item["name"]: item["value"] for item in categories},
            {"社会": 2, "科技": 1, "未分类": 1},
        )

    def test_keywords_are_split_and_counted(self) -> None:
        result = get_keyword_statistics(self.db, limit=10)

        self.assertEqual(
            {item["keyword"]: item["count"] for item in result},
            {"官方": 2, "网传": 2, "通报": 1},
        )

    def test_user_activity_counts_distinct_logged_in_users(self) -> None:
        result = get_user_activity(
            self.db,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 3),
        )

        self.assertEqual(result["dates"], ["2026-06-01", "2026-06-02", "2026-06-03"])
        self.assertEqual(result["active_users"], [1, 2, 0])

    def test_knowledge_overview_returns_category_label_and_vector_statistics(self) -> None:
        result = get_knowledge_overview(self.db)

        self.assertEqual(result["total_knowledge"], 3)
        self.assertEqual(
            {item["name"]: item["value"] for item in result["category_distribution"]},
            {"社会": 2, "科技": 1},
        )
        self.assertEqual(
            {item["name"]: item["value"] for item in result["truth_label_distribution"]},
            {"可信": 2, "虚假": 1},
        )
        self.assertEqual(
            {item["name"]: item["value"] for item in result["vector_status_distribution"]},
            {"synced": 2, "failed": 1},
        )

    def test_invalid_date_range_is_rejected(self) -> None:
        with self.assertRaises(StatisticsRangeError):
            get_detection_trend(
                self.db,
                start_date=date(2026, 6, 2),
                end_date=date(2026, 6, 1),
            )

    def _seed_data(self) -> None:
        self.db.add_all(
            [
                User(
                    id=1,
                    username="admin",
                    email="admin@example.com",
                    password_hash="hash",
                    role="admin",
                    status="active",
                ),
                User(
                    id=2,
                    username="alice",
                    email="alice@example.com",
                    password_hash="hash",
                    role="user",
                    status="active",
                ),
                User(
                    id=3,
                    username="bob",
                    email="bob@example.com",
                    password_hash="hash",
                    role="user",
                    status="active",
                ),
            ]
        )
        self.db.add_all(
            [
                self._knowledge(1, "社会案例一", "社会", "可信", "synced"),
                self._knowledge(2, "社会案例二", "社会", "虚假", "failed"),
                self._knowledge(3, "科技案例", "科技", "可信", "synced"),
            ]
        )
        detections = [
            self._detection(
                1,
                user_id=2,
                created_at=datetime(2026, 6, 1, 9, 0),
                category="社会",
                risk_level="可信新闻",
                keywords="官方,通报",
            ),
            self._detection(
                2,
                user_id=2,
                created_at=datetime(2026, 6, 2, 9, 0),
                category="社会",
                risk_level="高风险谣言",
                keywords="官方，网传",
                is_high_risk=True,
            ),
            self._detection(
                3,
                user_id=3,
                created_at=datetime(2026, 6, 2, 10, 0),
                category="科技",
                risk_level="存疑信息",
                keywords="网传",
            ),
            self._detection(
                4,
                user_id=None,
                created_at=datetime(2026, 6, 3, 10, 0),
                category=None,
                risk_level="高风险谣言",
                keywords=None,
                is_high_risk=False,
            ),
        ]
        self.db.add_all(detections)
        self.db.flush()
        self.db.add(
            Report(
                id=1,
                detection_id=1,
                user_id=2,
                report_title="报告一",
                html_path="one.html",
                pdf_path="one.pdf",
            )
        )
        self.db.commit()

    def _knowledge(
        self,
        item_id: int,
        title: str,
        category: str,
        truth_label: str,
        vector_status: str,
    ) -> KnowledgeItem:
        return KnowledgeItem(
            id=item_id,
            title=title,
            content="content",
            category=category,
            truth_label=truth_label,
            vector_sync_status=vector_status,
        )

    def _detection(
        self,
        record_id: int,
        user_id: int | None,
        created_at: datetime,
        category: str | None,
        risk_level: str,
        keywords: str | None,
        is_high_risk: bool = False,
    ) -> DetectionRecord:
        return DetectionRecord(
            id=record_id,
            user_id=user_id,
            input_title=f"新闻 {record_id}",
            input_content="content",
            category=category,
            keywords=keywords,
            final_score=70,
            evidence_score=70,
            llm_score=70,
            rule_score=70,
            risk_level=risk_level,
            judgement_result="需要核查",
            is_high_risk=is_high_risk,
            created_at=created_at,
        )


if __name__ == "__main__":
    unittest.main()
