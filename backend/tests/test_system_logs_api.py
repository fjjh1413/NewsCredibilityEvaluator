import unittest
from datetime import datetime
from types import SimpleNamespace

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.deps import get_current_admin
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.user import User


def _admin_override():
    return SimpleNamespace(id=99, username="admin", role="admin", status="active")


class SystemLogsApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.SessionLocal = sessionmaker(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self._create_system_logs_table()
        self._seed_data()

        def override_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_admin] = _admin_override
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_admin_can_list_logs_with_filters(self) -> None:
        response = self.client.get(
            "/api/admin/logs?page=1&page_size=10"
            "&module=auth&action=login&user_id=1"
            "&date_from=2026-01-01T00:00:00&date_to=2026-01-02T23:59:59"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["page"], 1)
        self.assertEqual(data["page_size"], 10)
        item = data["items"][0]
        self.assertEqual(item["user_id"], 1)
        self.assertEqual(item["username"], "alice")
        self.assertEqual(item["module"], "auth")
        self.assertEqual(item["action"], "login")
        self.assertEqual(item["description"], "用户登录成功")
        self.assertEqual(item["ip_address"], "203.0.113.7")

    def test_admin_logs_support_keyword_search(self) -> None:
        response = self.client.get("/api/admin/logs?keyword=高风险")

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["items"][0]["module"], "admin")

    def test_normal_user_cannot_access_admin_logs(self) -> None:
        def forbidden_admin():
            raise HTTPException(status_code=403, detail="Admin permission required")

        app.dependency_overrides[get_current_admin] = forbidden_admin

        response = self.client.get("/api/admin/logs")

        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_user_cannot_access_admin_logs(self) -> None:
        app.dependency_overrides.pop(get_current_admin, None)

        response = self.client.get("/api/admin/logs")

        self.assertEqual(response.status_code, 401)

    def _create_system_logs_table(self) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS system_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NULL,
                        action VARCHAR(100) NOT NULL,
                        module VARCHAR(100) NOT NULL,
                        description TEXT NULL,
                        ip_address VARCHAR(50) NULL,
                        created_at DATETIME NOT NULL
                    )
                    """
                )
            )

    def _seed_data(self) -> None:
        with self.SessionLocal() as db:
            db.add(
                User(
                    id=1,
                    username="alice",
                    password_hash="hashed",
                    email="alice@example.com",
                    role="user",
                    status="active",
                )
            )
            db.commit()
            db.execute(
                text(
                    """
                    INSERT INTO system_logs
                        (user_id, action, module, description, ip_address, created_at)
                    VALUES
                        (:user_id, :action, :module, :description, :ip_address, :created_at)
                    """
                ),
                [
                    {
                        "user_id": 1,
                        "action": "login",
                        "module": "auth",
                        "description": "用户登录成功",
                        "ip_address": "203.0.113.7",
                        "created_at": datetime(2026, 1, 1, 8, 0, 0),
                    },
                    {
                        "user_id": 99,
                        "action": "review",
                        "module": "admin",
                        "description": "管理员审核高风险记录 record_id=5",
                        "ip_address": "203.0.113.8",
                        "created_at": datetime(2026, 1, 3, 8, 0, 0),
                    },
                ],
            )
            db.commit()


if __name__ == "__main__":
    unittest.main()
