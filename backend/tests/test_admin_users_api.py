import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.deps import get_current_admin
from app.db.session import get_db
from app.main import app
from app.services.admin_user_service import (
    AdminUserLastAdminError,
    AdminUserNotFoundError,
    AdminUserSelfOperationError,
)


def _db_override():
    return Mock()


def _admin_override():
    return _user(99, username="current_admin", role="admin")


def _user(
    user_id: int = 1,
    username: str = "test_user",
    role: str = "user",
    status: str = "active",
):
    return SimpleNamespace(
        id=user_id,
        username=username,
        email=f"{username}@example.com",
        password_hash="must-not-leak",
        role=role,
        status=status,
        created_at=datetime(2026, 1, 1, 8, 0, 0),
        updated_at=datetime(2026, 1, 2, 8, 0, 0),
    )


class AdminUsersApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[get_db] = _db_override
        app.dependency_overrides[get_current_admin] = _admin_override
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    @patch("app.api.v1.admin_users.list_admin_users")
    def test_admin_can_list_users_with_filters_without_sensitive_fields(
        self,
        mocked_list,
    ) -> None:
        mocked_list.return_value = ([(_user(), 4)], 1)

        response = self.client.get(
            "/api/admin/users?page=2&page_size=10"
            "&keyword=test&role=user&status=active"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["items"][0]["detection_count"], 4)
        self.assertTrue(data["items"][0]["is_active"])
        self.assertNotIn("password_hash", data["items"][0])
        kwargs = mocked_list.call_args.kwargs
        self.assertEqual(kwargs["page"], 2)
        self.assertEqual(kwargs["page_size"], 10)
        self.assertEqual(kwargs["keyword"], "test")
        self.assertEqual(kwargs["role"], "user")
        self.assertEqual(kwargs["status"], "active")

    @patch("app.api.v1.admin_users.get_admin_user")
    def test_missing_user_returns_404(self, mocked_get_user) -> None:
        mocked_get_user.side_effect = AdminUserNotFoundError("用户不存在")

        response = self.client.get("/api/admin/users/999")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["message"], "用户不存在")

    @patch("app.api.v1.admin_users.get_detection_history")
    @patch("app.api.v1.admin_users.get_admin_user")
    def test_admin_can_read_user_detections(
        self,
        mocked_get_user,
        mocked_history,
    ) -> None:
        mocked_get_user.return_value = (_user(), 1)
        mocked_history.return_value = (
            [
                SimpleNamespace(
                    id=5,
                    user_id=1,
                    input_title="User news",
                    final_score=75,
                    risk_level="存疑信息",
                    is_high_risk=False,
                    created_at=datetime(2026, 1, 3, 8, 0, 0),
                    updated_at=datetime(2026, 1, 3, 8, 0, 0),
                )
            ],
            1,
        )

        response = self.client.get("/api/admin/users/1/detections?page=2&page_size=5")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["items"][0]["input_title"], "User news")
        kwargs = mocked_history.call_args.kwargs
        self.assertEqual(kwargs["user_id"], 1)
        self.assertEqual(kwargs["page"], 2)
        self.assertEqual(kwargs["page_size"], 5)

    @patch("app.api.v1.admin_users.get_admin_user")
    @patch("app.api.v1.admin_users.disable_admin_user")
    def test_admin_can_disable_normal_user(self, mocked_disable, mocked_get_user) -> None:
        disabled_user = _user(status="disabled")
        mocked_disable.return_value = disabled_user
        mocked_get_user.return_value = (disabled_user, 2)

        response = self.client.post("/api/admin/users/1/disable")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["status"], "disabled")
        self.assertEqual(mocked_disable.call_args.args[2].id, 99)

    @patch("app.api.v1.admin_users.get_admin_user")
    @patch("app.api.v1.admin_users.enable_admin_user")
    def test_admin_can_enable_normal_user(self, mocked_enable, mocked_get_user) -> None:
        enabled_user = _user(status="active")
        mocked_enable.return_value = enabled_user
        mocked_get_user.return_value = (enabled_user, 2)

        response = self.client.post("/api/admin/users/1/enable")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["status"], "active")

    @patch("app.api.v1.admin_users.disable_admin_user")
    def test_cannot_disable_current_admin(self, mocked_disable) -> None:
        mocked_disable.side_effect = AdminUserSelfOperationError(
            "不能禁用当前登录的管理员账号"
        )

        response = self.client.post("/api/admin/users/99/disable")

        self.assertEqual(response.status_code, 409)
        self.assertIn("不能禁用", response.json()["message"])

    @patch("app.api.v1.admin_users.disable_admin_user")
    def test_cannot_disable_last_admin(self, mocked_disable) -> None:
        mocked_disable.side_effect = AdminUserLastAdminError(
            "不能禁用系统中最后一个可用管理员"
        )

        response = self.client.post("/api/admin/users/1/disable")

        self.assertEqual(response.status_code, 409)
        self.assertIn("最后一个", response.json()["message"])

    @patch("app.api.v1.admin_users.update_admin_user_role")
    def test_cannot_downgrade_current_admin(self, mocked_role) -> None:
        mocked_role.side_effect = AdminUserSelfOperationError(
            "不能降级当前登录的管理员账号"
        )

        response = self.client.post(
            "/api/admin/users/99/role",
            json={"role": "user"},
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("不能降级", response.json()["message"])

    def test_invalid_role_is_rejected(self) -> None:
        response = self.client.post(
            "/api/admin/users/1/role",
            json={"role": "owner"},
        )

        self.assertEqual(response.status_code, 422)

    def test_physical_delete_endpoint_is_not_exposed(self) -> None:
        response = self.client.delete("/api/admin/users/99")

        self.assertEqual(response.status_code, 405)

    def test_normal_user_cannot_access_admin_users(self) -> None:
        def forbidden_admin():
            raise HTTPException(status_code=403, detail="Admin permission required")

        app.dependency_overrides[get_current_admin] = forbidden_admin

        response = self.client.get("/api/admin/users")

        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_user_cannot_access_admin_users(self) -> None:
        app.dependency_overrides.pop(get_current_admin, None)

        response = self.client.get("/api/admin/users")

        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
