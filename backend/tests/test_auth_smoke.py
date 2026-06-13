import os
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from app.api.v1 import auth as auth_api
from app.core.config import get_settings
from app.core.security import get_password_hash
from app.db.session import get_db
from app.main import app


def _override_db():
    return Mock()


def _clear_auth_rate_limiters() -> None:
    for limiter_name in ("login_rate_limiter", "register_rate_limiter"):
        rate_limiter = getattr(auth_api, limiter_name, None)
        if rate_limiter is not None:
            rate_limiter.clear()


class AuthSmokeTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _clear_auth_rate_limiters()
        self.previous_secret_key = os.environ.get("SECRET_KEY")
        os.environ["SECRET_KEY"] = "test-secret-for-auth-smoke"
        get_settings.cache_clear()

        self.users_by_id = {}
        self.users_by_username = {}
        self.users_by_email = {}

        def get_user_by_username(db, username):
            return self.users_by_username.get(username)

        def get_user_by_email(db, email):
            if not email:
                return None
            return self.users_by_email.get(email)

        def get_user_by_id(db, user_id):
            return self.users_by_id.get(user_id)

        def create_user(db, user_in, password_hash, role="user", status="active"):
            user_id = len(self.users_by_id) + 1
            now = datetime.now(timezone.utc)
            user = SimpleNamespace(
                id=user_id,
                username=user_in.username,
                email=user_in.email,
                password_hash=password_hash,
                role=role,
                status=status,
                created_at=now,
                updated_at=now,
            )
            self.users_by_id[user_id] = user
            self.users_by_username[user.username] = user
            if user.email:
                self.users_by_email[user.email] = user
            return user

        self._create_user = create_user
        self.patchers = [
            patch(
                "app.services.auth_service.user_crud.get_user_by_username",
                side_effect=get_user_by_username,
            ),
            patch(
                "app.services.auth_service.user_crud.get_user_by_email",
                side_effect=get_user_by_email,
            ),
            patch(
                "app.services.auth_service.user_crud.create_user",
                side_effect=create_user,
            ),
            patch("app.core.deps.get_user_by_id", side_effect=get_user_by_id),
        ]
        for patcher in self.patchers:
            patcher.start()

        app.dependency_overrides[get_db] = _override_db
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        _clear_auth_rate_limiters()
        for patcher in reversed(self.patchers):
            patcher.stop()
        if self.previous_secret_key is None:
            os.environ.pop("SECRET_KEY", None)
        else:
            os.environ["SECRET_KEY"] = self.previous_secret_key
        get_settings.cache_clear()

    def test_register_login_me_and_admin_ping_smoke(self) -> None:
        register_response = self.client.post(
            "/api/auth/register",
            json={
                "username": "normal_user",
                "password": "secret123",
                "email": "normal@example.com",
                "role": "admin",
                "status": "disabled",
            },
        )

        self.assertEqual(register_response.status_code, 200)
        created_user = self.users_by_username["normal_user"]
        self.assertEqual(created_user.role, "user")
        self.assertEqual(created_user.status, "active")
        self.assertNotEqual(created_user.password_hash, "secret123")

        login_response = self.client.post(
            "/api/auth/login",
            json={"username": "normal_user", "password": "secret123"},
        )

        self.assertEqual(login_response.status_code, 200)
        user_token = login_response.json()["data"]["access_token"]

        me_response = self.client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.json()["data"]["username"], "normal_user")

        unauthenticated_me_response = self.client.get("/api/auth/me")
        self.assertEqual(unauthenticated_me_response.status_code, 401)

        user_admin_ping_response = self.client.get(
            "/api/admin/ping",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        self.assertEqual(user_admin_ping_response.status_code, 403)

        admin = SimpleNamespace(
            username="admin_user",
            email="admin@example.com",
        )
        created_admin = self._create_user(
            Mock(),
            admin,
            get_password_hash("admin123"),
            role="admin",
            status="active",
        )
        self.assertEqual(created_admin.role, "admin")

        admin_login_response = self.client.post(
            "/api/auth/login",
            json={"username": "admin_user", "password": "admin123"},
        )
        self.assertEqual(admin_login_response.status_code, 200)
        admin_token = admin_login_response.json()["data"]["access_token"]

        admin_ping_response = self.client.get(
            "/api/admin/ping",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        self.assertEqual(admin_ping_response.status_code, 200)

    def test_disabled_user_cannot_login_or_reuse_existing_token(self) -> None:
        user_input = SimpleNamespace(
            username="disabled_user",
            email="disabled@example.com",
        )
        user = self._create_user(
            Mock(),
            user_input,
            get_password_hash("secret123"),
            role="user",
            status="active",
        )
        login_response = self.client.post(
            "/api/auth/login",
            json={"username": "disabled_user", "password": "secret123"},
        )
        token = login_response.json()["data"]["access_token"]

        user.status = "disabled"

        disabled_login_response = self.client.post(
            "/api/auth/login",
            json={"username": "disabled_user", "password": "secret123"},
        )
        disabled_me_response = self.client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(disabled_login_response.status_code, 403)
        self.assertEqual(disabled_me_response.status_code, 403)

    @patch("app.api.v1.auth.authenticate_user")
    def test_login_rate_limits_sixth_request_for_same_ip(self, mocked_authenticate) -> None:
        mocked_authenticate.side_effect = auth_api.InvalidCredentialsError(
            "invalid credentials"
        )

        responses = [
            self.client.post(
                "/api/auth/login",
                json={"username": "missing_user", "password": "secret123"},
                headers={"X-Forwarded-For": "198.51.100.10"},
            )
            for _ in range(6)
        ]

        self.assertEqual(
            [response.status_code for response in responses[:5]],
            [401, 401, 401, 401, 401],
        )
        self.assertEqual(responses[5].status_code, 429)
        self.assertEqual(mocked_authenticate.call_count, 5)

    @patch("app.api.v1.auth.register_user")
    def test_register_rate_limits_third_request_for_same_ip(self, mocked_register) -> None:
        def register_user(db, payload):
            return SimpleNamespace(
                id=mocked_register.call_count,
                username=payload.username,
                email=payload.email,
                role="user",
            )

        mocked_register.side_effect = register_user

        responses = [
            self.client.post(
                "/api/auth/register",
                json={
                    "username": f"rate_limited_user_{index}",
                    "password": "secret123",
                    "email": f"rate_limited_user_{index}@example.com",
                },
                headers={"X-Forwarded-For": "198.51.100.20"},
            )
            for index in range(3)
        ]

        self.assertEqual([response.status_code for response in responses[:2]], [200, 200])
        self.assertEqual(responses[2].status_code, 429)
        self.assertEqual(mocked_register.call_count, 2)


if __name__ == "__main__":
    unittest.main()
