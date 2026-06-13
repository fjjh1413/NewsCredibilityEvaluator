import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from app.core.deps import get_current_admin, get_current_user
from app.db.session import get_db
from app.main import app


def _db_override():
    return Mock()


def _user_override():
    return SimpleNamespace(id=1, username="user", role="user", status="active")


def _admin_override():
    return SimpleNamespace(id=99, username="admin", role="admin", status="active")


def _history_record(record_id: int, user_id: int = 1):
    return SimpleNamespace(
        id=record_id,
        user_id=user_id,
        input_title=f"Detection {record_id}",
        final_score=68.5,
        risk_level="存疑信息",
        is_high_risk=False,
        created_at=datetime(2026, 1, 2, 8, 0, 0),
        updated_at=datetime(2026, 1, 2, 8, 0, 0),
    )


def _detail_record(record_id: int, user_id: int = 1):
    return SimpleNamespace(
        id=record_id,
        user_id=user_id,
        input_title=f"Detection {record_id}",
        input_content="News content",
        category="society",
        keywords="news,test",
        final_score=68.5,
        evidence_score=70,
        llm_score=65,
        rule_score=72,
        risk_level="存疑信息",
        judgement_result="需要进一步核查",
        reason="证据不足。",
        risk_points=["来源不明确"],
        suggestion="查看官方通报。",
        is_high_risk=False,
        report_url=None,
        created_at=datetime(2026, 1, 2, 8, 0, 0),
        updated_at=datetime(2026, 1, 2, 8, 0, 0),
        evidence_matches=[
            SimpleNamespace(
                id=1,
                detection_id=record_id,
                knowledge_id=10,
                title="Evidence title",
                summary="summary",
                source_name="official",
                similarity_score=0.83,
                rank_order=1,
                created_at=datetime(2026, 1, 2, 8, 0, 1),
                updated_at=datetime(2026, 1, 2, 8, 0, 1),
            )
        ],
    )


class DetectionHistoryApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[get_db] = _db_override
        app.dependency_overrides[get_current_user] = _user_override
        app.dependency_overrides[get_current_admin] = _admin_override
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    @patch("app.api.v1.detect.get_detection_history")
    def test_user_can_read_own_history(self, mocked_history) -> None:
        mocked_history.return_value = ([_history_record(1)], 1)

        response = self.client.get("/api/detect/history?page=1&page_size=10")

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["items"][0]["id"], 1)
        self.assertEqual(mocked_history.call_args.kwargs["current_user"].id, 1)

    @patch("app.api.v1.detect.get_detection_history")
    def test_user_history_passes_keyword_filter(self, mocked_history) -> None:
        mocked_history.return_value = ([_history_record(1)], 1)

        response = self.client.get("/api/detect/history?keyword=official")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mocked_history.call_args.kwargs["keyword"], "official")

    @patch("app.api.v1.detect.get_detection_detail")
    def test_user_detail_returns_evidence_matches(self, mocked_detail) -> None:
        mocked_detail.return_value = _detail_record(1)

        response = self.client.get("/api/detect/1")

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["id"], 1)
        self.assertEqual(data["evidence_matches"][0]["title"], "Evidence title")

    @patch("app.api.v1.detect.get_detection_detail")
    def test_user_detail_returns_404_when_not_owned_or_missing(self, mocked_detail) -> None:
        mocked_detail.return_value = None

        response = self.client.get("/api/detect/999")

        self.assertEqual(response.status_code, 404)

    @patch("app.api.v1.admin_detections.get_detection_history")
    def test_admin_list_supports_filters(self, mocked_history) -> None:
        mocked_history.return_value = ([_history_record(2, user_id=2)], 1)

        response = self.client.get(
            "/api/admin/detections"
            "?risk_level=存疑信息"
            "&keyword=official"
            "&date_from=2026-01-01T00:00:00"
            "&date_to=2026-01-03T00:00:00"
            "&user_id=2"
        )

        self.assertEqual(response.status_code, 200)
        kwargs = mocked_history.call_args.kwargs
        self.assertEqual(kwargs["current_user"].role, "admin")
        self.assertEqual(kwargs["risk_level"], "存疑信息")
        self.assertEqual(kwargs["keyword"], "official")
        self.assertEqual(kwargs["user_id"], 2)
        self.assertIsNotNone(kwargs["date_from"])
        self.assertIsNotNone(kwargs["date_to"])

    @patch("app.api.v1.admin_detections.get_detection_detail")
    def test_admin_can_read_any_detail(self, mocked_detail) -> None:
        mocked_detail.return_value = _detail_record(2, user_id=2)

        response = self.client.get("/api/admin/detections/2")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["id"], 2)

    @patch("app.api.v1.admin_detections.delete_detection_record")
    def test_admin_can_delete_detection(self, mocked_delete) -> None:
        mocked_delete.return_value = True

        response = self.client.delete("/api/admin/detections/2")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["id"], 2)
        mocked_delete.assert_called_once()

    @patch("app.api.v1.admin_detections.delete_detection_record")
    def test_admin_delete_returns_404_when_missing(self, mocked_delete) -> None:
        mocked_delete.return_value = False

        response = self.client.delete("/api/admin/detections/999")

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
