import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from app.api.v1 import auth as auth_api
from app.api.v1 import detect as detect_api
from app.core.deps import get_current_admin
from app.db.session import get_db
from app.main import app


VALID_NEWS_CONTENT = "News content with enough detail for validation."


def _db_override():
    return Mock()


def _admin_override():
    return SimpleNamespace(id=99, username="admin", role="admin", status="active")


def _user(
    user_id: int = 1,
    username: str = "alice",
    role: str = "user",
    status: str = "active",
):
    return SimpleNamespace(
        id=user_id,
        username=username,
        email=f"{username}@example.com",
        role=role,
        status=status,
        created_at="2026-01-01T08:00:00",
        updated_at="2026-01-01T08:00:00",
    )


def _optional_user_override():
    return _user(7, username="detector")


def _clear_rate_limiters() -> None:
    for limiter_name in ("login_rate_limiter", "register_rate_limiter"):
        limiter = getattr(auth_api, limiter_name, None)
        if limiter is not None:
            limiter.clear()
    detector_limiter = getattr(detect_api, "detector_rate_limiter", None)
    if detector_limiter is not None:
        detector_limiter.clear()


class SystemLogEventsApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _clear_rate_limiters()
        app.dependency_overrides[get_db] = _db_override
        app.dependency_overrides[get_current_admin] = _admin_override
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        _clear_rate_limiters()

    @patch.object(auth_api, "create_access_token", return_value="fixed-token")
    @patch.object(auth_api, "authenticate_user")
    def test_successful_login_records_audit_event(
        self,
        mocked_authenticate,
        mocked_create_token,
    ) -> None:
        mocked_authenticate.return_value = _user(1)

        with patch("app.api.v1.auth.record_system_log", create=True) as mocked_log:
            response = self.client.post(
                "/api/auth/login",
                json={"username": "alice", "password": "super-secret"},
                headers={"X-Forwarded-For": "203.0.113.7"},
            )

        self.assertEqual(response.status_code, 200)
        mocked_log.assert_called_once()
        kwargs = mocked_log.call_args.kwargs
        self.assertEqual(kwargs["user_id"], 1)
        self.assertEqual(kwargs["module"], "auth")
        self.assertEqual(kwargs["action"], "login")
        self.assertEqual(kwargs["ip_address"], "testclient")
        self.assertNotIn("super-secret", kwargs["description"])
        mocked_create_token.assert_called_once()

    @patch("app.api.v1.detect.detect_news_credibility")
    def test_successful_detection_records_audit_event(self, mocked_detect) -> None:
        app.dependency_overrides[detect_api.get_optional_current_user] = (
            _optional_user_override
        )
        mocked_detect.return_value = {
            "detection_id": 12,
            "final_score": 76,
            "evidence_score": 70,
            "llm_score": 70,
            "rule_score": 80,
            "risk_level": "存疑信息",
            "judgement_result": "该新闻存在一定疑点，建议进一步核查",
            "reason": "证据部分支持。",
            "risk_points": ["来源需要核查"],
            "keywords": ["官方通报"],
            "evidence_list": [],
            "similar_news": [],
            "suggestion": "继续关注权威信息。",
            "agent_steps": [],
            "disclaimer": "检测结果仅供参考。",
        }

        with patch("app.api.v1.detect.record_system_log", create=True) as mocked_log:
            response = self.client.post(
                "/api/detect/news",
                json={"title": "News title", "content": VALID_NEWS_CONTENT},
                headers={"X-Forwarded-For": "203.0.113.9"},
            )

        self.assertEqual(response.status_code, 200)
        mocked_log.assert_called_once()
        kwargs = mocked_log.call_args.kwargs
        self.assertEqual(kwargs["user_id"], 7)
        self.assertEqual(kwargs["module"], "detection")
        self.assertEqual(kwargs["action"], "detect_news")
        self.assertEqual(kwargs["ip_address"], "testclient")
        self.assertIn("detection_id=12", kwargs["description"])
        self.assertIn("risk_level=存疑信息", kwargs["description"])
        self.assertNotIn(VALID_NEWS_CONTENT, kwargs["description"])

    @patch("app.api.v1.admin_users.get_admin_user")
    @patch("app.api.v1.admin_users.disable_admin_user")
    def test_admin_user_disable_records_audit_event(
        self,
        mocked_disable,
        mocked_get_user,
    ) -> None:
        disabled_user = _user(1, status="disabled")
        mocked_disable.return_value = disabled_user
        mocked_get_user.return_value = (disabled_user, 2)

        with patch("app.api.v1.admin_users.record_system_log", create=True) as mocked_log:
            response = self.client.post(
                "/api/admin/users/1/disable",
                headers={"X-Forwarded-For": "203.0.113.10"},
            )

        self.assertEqual(response.status_code, 200)
        mocked_log.assert_called_once()
        kwargs = mocked_log.call_args.kwargs
        self.assertEqual(kwargs["user_id"], 99)
        self.assertEqual(kwargs["module"], "admin")
        self.assertEqual(kwargs["action"], "disable_user")
        self.assertEqual(kwargs["ip_address"], "testclient")
        self.assertIn("target_user_id=1", kwargs["description"])


if __name__ == "__main__":
    unittest.main()
