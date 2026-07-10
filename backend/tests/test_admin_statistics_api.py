import os
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.deps import get_current_admin
from app.db.session import get_db
from app.main import app
from app.services.statistics_service import StatisticsRangeError


def _db_override():
    return Mock()


def _admin_override():
    return SimpleNamespace(id=1, username="admin", role="admin", status="active")


class _FakeRedisClient:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def get(self, key: str):
        return self.values.get(key)

    async def set(self, key: str, value: str, ex: int):
        self.values[key] = value
        return True


STATISTICS_ENDPOINTS = [
    "/api/admin/statistics/overview",
    "/api/admin/statistics/trend",
    "/api/admin/statistics/risk-distribution",
    "/api/admin/statistics/category-distribution",
    "/api/admin/statistics/keywords",
    "/api/admin/statistics/user-activity",
    "/api/admin/statistics/knowledge-overview",
]


class AdminStatisticsApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_redis_enabled = os.environ.get("REDIS_ENABLED")
        self.previous_cache_prefix = os.environ.get("CACHE_KEY_PREFIX")
        app.dependency_overrides[get_db] = _db_override
        app.dependency_overrides[get_current_admin] = _admin_override
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        if self.previous_redis_enabled is None:
            os.environ.pop("REDIS_ENABLED", None)
        else:
            os.environ["REDIS_ENABLED"] = self.previous_redis_enabled
        if self.previous_cache_prefix is None:
            os.environ.pop("CACHE_KEY_PREFIX", None)
        else:
            os.environ["CACHE_KEY_PREFIX"] = self.previous_cache_prefix
        get_settings.cache_clear()

    @patch("app.api.v1.admin_statistics.get_statistics_overview")
    def test_admin_can_read_overview(self, mocked_overview) -> None:
        mocked_overview.return_value = {
            "total_detections": 10,
            "today_detections": 2,
            "total_users": 3,
            "total_knowledge": 4,
            "total_high_risk": 1,
            "total_reports": 5,
        }

        response = self.client.get("/api/admin/statistics/overview")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["total_reports"], 5)

    @patch("app.api.v1.admin_statistics.get_statistics_overview")
    def test_overview_uses_redis_cache_when_enabled(self, mocked_overview) -> None:
        os.environ["REDIS_ENABLED"] = "true"
        os.environ["CACHE_KEY_PREFIX"] = "testapp"
        get_settings.cache_clear()
        redis_client = _FakeRedisClient()
        mocked_overview.side_effect = [
            {
                "total_detections": 10,
                "today_detections": 2,
                "total_users": 3,
                "total_knowledge": 4,
                "total_high_risk": 1,
                "total_reports": 5,
            },
            {
                "total_detections": 99,
                "today_detections": 99,
                "total_users": 99,
                "total_knowledge": 99,
                "total_high_risk": 99,
                "total_reports": 99,
            },
        ]

        with patch("app.core.cache.redis_manager", SimpleNamespace(client=redis_client)):
            first = self.client.get("/api/admin/statistics/overview")
            second = self.client.get("/api/admin/statistics/overview")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["data"]["total_reports"], 5)
        self.assertEqual(second.json()["data"]["total_reports"], 5)
        self.assertEqual(mocked_overview.call_count, 1)

    @patch("app.api.v1.admin_statistics.get_detection_trend")
    def test_trend_forwards_days_and_date_range(self, mocked_trend) -> None:
        mocked_trend.return_value = {
            "dates": ["2026-06-01", "2026-06-02"],
            "counts": [1, 2],
        }

        response = self.client.get(
            "/api/admin/statistics/trend"
            "?days=30&start_date=2026-06-01&end_date=2026-06-02"
        )

        self.assertEqual(response.status_code, 200)
        args = mocked_trend.call_args.args
        self.assertEqual(args[1], 30)
        self.assertEqual(args[2], date(2026, 6, 1))
        self.assertEqual(args[3], date(2026, 6, 2))

    def test_distribution_keyword_activity_and_knowledge_responses(self) -> None:
        cases = [
            (
                "app.api.v1.admin_statistics.get_risk_distribution",
                "/api/admin/statistics/risk-distribution",
                [{"name": "高风险谣言", "value": 2}],
            ),
            (
                "app.api.v1.admin_statistics.get_category_distribution",
                "/api/admin/statistics/category-distribution",
                [{"name": "社会", "value": 3}],
            ),
            (
                "app.api.v1.admin_statistics.get_keyword_statistics",
                "/api/admin/statistics/keywords?limit=5",
                [{"keyword": "官方", "count": 4}],
            ),
            (
                "app.api.v1.admin_statistics.get_user_activity",
                "/api/admin/statistics/user-activity",
                {"dates": ["2026-06-01"], "active_users": [2]},
            ),
            (
                "app.api.v1.admin_statistics.get_knowledge_overview",
                "/api/admin/statistics/knowledge-overview",
                {
                    "total_knowledge": 1,
                    "category_distribution": [{"name": "社会", "value": 1}],
                    "truth_label_distribution": [{"name": "可信", "value": 1}],
                    "vector_status_distribution": [{"name": "synced", "value": 1}],
                },
            ),
        ]

        for target, url, payload in cases:
            with self.subTest(url=url), patch(target, return_value=payload):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["data"], payload)

    @patch("app.api.v1.admin_statistics.get_detection_trend")
    def test_invalid_range_returns_422(self, mocked_trend) -> None:
        mocked_trend.side_effect = StatisticsRangeError("开始日期不能晚于结束日期")

        response = self.client.get("/api/admin/statistics/trend")

        self.assertEqual(response.status_code, 422)
        self.assertIn("开始日期", response.json()["message"])

    def test_normal_user_cannot_access_statistics_endpoints(self) -> None:
        def forbidden_admin():
            raise HTTPException(status_code=403, detail="Admin permission required")

        app.dependency_overrides[get_current_admin] = forbidden_admin

        for url in STATISTICS_ENDPOINTS:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_unauthenticated_user_cannot_access_statistics_endpoints(self) -> None:
        app.dependency_overrides.pop(get_current_admin, None)

        for url in STATISTICS_ENDPOINTS:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 401)


if __name__ == "__main__":
    unittest.main()
