import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.deps import get_current_admin
from app.db.session import get_db
from app.main import app
from app.services.high_risk_service import HighRiskConflictError, HighRiskNotFoundError


def _db_override():
    return Mock()


def _admin_override():
    return SimpleNamespace(id=1, username="admin", role="admin", status="active")


def _public_item():
    return {
        "id": 1,
        "title": "公开高风险新闻",
        "summary": "仅公开摘要",
        "category": "社会",
        "final_score": 20,
        "risk_level": "高风险谣言",
        "keywords": ["网传"],
        "published_at": datetime(2026, 6, 4, 10, 0, 0),
    }


def _admin_detail():
    return {
        "id": 1,
        "user_id": 2,
        "input_title": "高风险新闻",
        "input_content": "管理员可见的完整正文",
        "category": "社会",
        "keywords": ["网传"],
        "final_score": 20,
        "evidence_score": 30,
        "llm_score": 20,
        "rule_score": 25,
        "risk_level": "高风险谣言",
        "judgement_result": "存在较高风险",
        "reason": "需要核查",
        "risk_points": ["来源不明"],
        "suggestion": "查阅权威来源",
        "is_high_risk": True,
        "review_status": "approved",
        "is_public": False,
        "admin_remark": "内部备注",
        "created_at": datetime(2026, 6, 3, 10, 0, 0),
        "reviewed_at": datetime(2026, 6, 4, 10, 0, 0),
        "reviewed_by": 1,
        "evidence_matches": [],
    }


class HighRiskApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[get_db] = _db_override
        app.dependency_overrides[get_current_admin] = _admin_override
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    @patch("app.api.v1.high_risk.list_public_high_risk")
    def test_public_list_is_accessible_and_has_no_internal_fields(self, mocked_list) -> None:
        mocked_list.return_value = ([_public_item()], 1)

        response = self.client.get("/api/high-risk/public")

        self.assertEqual(response.status_code, 200)
        item = response.json()["data"]["items"][0]
        self.assertNotIn("input_content", item)
        self.assertNotIn("admin_remark", item)
        self.assertNotIn("review_status", item)
        self.assertNotIn("is_public", item)

    def test_public_statistics_endpoints(self) -> None:
        cases = [
            (
                "app.api.v1.high_risk.list_public_high_risk_ranking",
                "/api/high-risk/ranking",
                {"items": [_public_item()]},
            ),
            (
                "app.api.v1.high_risk.get_public_high_risk_keywords",
                "/api/high-risk/keywords",
                [{"keyword": "网传", "count": 2}],
            ),
            (
                "app.api.v1.high_risk.get_public_high_risk_categories",
                "/api/high-risk/category-distribution",
                [{"category": "社会", "count": 2}],
            ),
        ]
        for target, url, expected in cases:
            return_value = expected["items"] if isinstance(expected, dict) else expected
            with self.subTest(url=url), patch(target, return_value=return_value):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                data = response.json()["data"]
                if url.endswith("/ranking"):
                    self.assertEqual(data["items"][0]["title"], "公开高风险新闻")
                else:
                    self.assertEqual(data, expected)

    @patch("app.api.v1.admin_high_risk.list_admin_high_risk")
    def test_admin_can_list_with_filters(self, mocked_list) -> None:
        mocked_list.return_value = ([_admin_detail()], 1)

        response = self.client.get(
            "/api/admin/high-risk?page=2&page_size=10&review_status=approved"
            "&is_public=false&keyword=新闻"
        )

        self.assertEqual(response.status_code, 200)
        kwargs = mocked_list.call_args.kwargs
        self.assertEqual(kwargs["page"], 2)
        self.assertEqual(kwargs["review_status"], "approved")
        self.assertFalse(kwargs["is_public"])

    @patch("app.api.v1.admin_high_risk.get_admin_high_risk_detail")
    def test_admin_can_read_detail(self, mocked_detail) -> None:
        mocked_detail.return_value = _admin_detail()

        response = self.client.get("/api/admin/high-risk/1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["input_content"], "管理员可见的完整正文")

    @patch("app.api.v1.admin_high_risk.update_high_risk_review")
    def test_admin_can_review(self, mocked_review) -> None:
        mocked_review.return_value = _admin_detail()

        response = self.client.put(
            "/api/admin/high-risk/1/review",
            json={"review_status": "approved", "admin_remark": "审核通过"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mocked_review.call_args.args[3], 1)

    @patch("app.api.v1.admin_high_risk.update_high_risk_public_status")
    def test_unapproved_record_cannot_be_published(self, mocked_update) -> None:
        mocked_update.side_effect = HighRiskConflictError("请先审核通过后再公开展示")

        response = self.client.put(
            "/api/admin/high-risk/1/public",
            json={"is_public": True},
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("请先审核通过", response.json()["message"])

    @patch("app.api.v1.admin_high_risk.get_admin_high_risk_detail")
    def test_missing_high_risk_record_returns_404(self, mocked_detail) -> None:
        mocked_detail.side_effect = HighRiskNotFoundError("高风险检测记录不存在")

        response = self.client.get("/api/admin/high-risk/999")

        self.assertEqual(response.status_code, 404)

    def test_normal_user_cannot_access_admin_high_risk(self) -> None:
        def forbidden_admin():
            raise HTTPException(status_code=403, detail="Admin permission required")

        app.dependency_overrides[get_current_admin] = forbidden_admin

        self.assertEqual(self.client.get("/api/admin/high-risk").status_code, 403)

    def test_unauthenticated_user_cannot_access_admin_high_risk(self) -> None:
        app.dependency_overrides.pop(get_current_admin, None)

        self.assertEqual(self.client.get("/api/admin/high-risk").status_code, 401)


if __name__ == "__main__":
    unittest.main()
