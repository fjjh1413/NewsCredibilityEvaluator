import unittest
from datetime import datetime
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.detection_record import DetectionRecord
from app.models.user import User
from app.schemas.user import AdminUserRoleUpdate
from app.services.admin_user_service import (
    AdminUserLastAdminError,
    AdminUserNotFoundError,
    AdminUserSelfOperationError,
    disable_admin_user,
    enable_admin_user,
    list_admin_users,
    update_admin_user_role,
)


class AdminUserServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        self.addCleanup(self.engine.dispose)
        TestingSessionLocal = sessionmaker(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.db = TestingSessionLocal()
        self.addCleanup(self.db.close)

    def test_list_supports_keyword_role_status_and_real_detection_counts(self) -> None:
        admin = self._add_user(1, "root_admin", "root@example.com", role="admin")
        active_user = self._add_user(2, "alice", "alice@example.com")
        self._add_user(3, "bob", "bob@example.com", status="disabled")
        self._add_detection(active_user.id, "Alice news 1")
        self._add_detection(active_user.id, "Alice news 2")

        keyword_items, keyword_total = list_admin_users(
            self.db,
            page=1,
            page_size=20,
            keyword="alice@",
        )
        role_items, role_total = list_admin_users(
            self.db,
            page=1,
            page_size=20,
            role="admin",
        )
        status_items, status_total = list_admin_users(
            self.db,
            page=1,
            page_size=20,
            status="disabled",
        )

        self.assertEqual(keyword_total, 1)
        self.assertEqual(keyword_items[0][0].id, active_user.id)
        self.assertEqual(keyword_items[0][1], 2)
        self.assertEqual(role_total, 1)
        self.assertEqual(role_items[0][0].id, admin.id)
        self.assertEqual(status_total, 1)
        self.assertEqual(status_items[0][0].username, "bob")

    def test_admin_can_disable_and_enable_normal_user(self) -> None:
        admin = self._add_user(1, "admin", "admin@example.com", role="admin")
        user = self._add_user(2, "user", "user@example.com")

        disabled = disable_admin_user(self.db, user.id, admin)
        disabled_status = disabled.status
        enabled = enable_admin_user(self.db, user.id)

        self.assertEqual(disabled_status, "disabled")
        self.assertEqual(enabled.status, "active")

    def test_repeated_enable_is_idempotent(self) -> None:
        user = self._add_user(1, "user", "user@example.com")

        enabled = enable_admin_user(self.db, user.id)

        self.assertEqual(enabled.status, "active")

    def test_current_admin_cannot_disable_self(self) -> None:
        admin = self._add_user(1, "admin", "admin@example.com", role="admin")

        with self.assertRaises(AdminUserSelfOperationError):
            disable_admin_user(self.db, admin.id, admin)

    def test_last_active_admin_cannot_be_disabled(self) -> None:
        admin = self._add_user(1, "admin", "admin@example.com", role="admin")
        outside_admin = SimpleNamespace(id=99, role="admin")

        with self.assertRaises(AdminUserLastAdminError):
            disable_admin_user(self.db, admin.id, outside_admin)

    def test_current_admin_cannot_downgrade_self(self) -> None:
        admin = self._add_user(1, "admin", "admin@example.com", role="admin")

        with self.assertRaises(AdminUserSelfOperationError):
            update_admin_user_role(
                self.db,
                admin.id,
                AdminUserRoleUpdate(role="user"),
                admin,
            )

    def test_last_admin_cannot_be_downgraded(self) -> None:
        admin = self._add_user(1, "admin", "admin@example.com", role="admin")
        outside_admin = SimpleNamespace(id=99, role="admin")

        with self.assertRaises(AdminUserLastAdminError):
            update_admin_user_role(
                self.db,
                admin.id,
                AdminUserRoleUpdate(role="user"),
                outside_admin,
            )

    def test_missing_user_returns_not_found(self) -> None:
        admin = self._add_user(1, "admin", "admin@example.com", role="admin")

        with self.assertRaises(AdminUserNotFoundError):
            disable_admin_user(self.db, 999, admin)

    def _add_user(
        self,
        user_id: int,
        username: str,
        email: str,
        role: str = "user",
        status: str = "active",
    ) -> User:
        now = datetime(2026, 1, 1, 8, 0, 0)
        user = User(
            id=user_id,
            username=username,
            email=email,
            password_hash="secret-hash",
            role=role,
            status=status,
            created_at=now,
            updated_at=now,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def _add_detection(self, user_id: int, title: str) -> None:
        record = DetectionRecord(
            user_id=user_id,
            input_title=title,
            input_content="content",
            final_score=80,
            evidence_score=80,
            llm_score=80,
            rule_score=80,
            risk_level="可信新闻",
            judgement_result="可信",
            is_high_risk=False,
        )
        self.db.add(record)
        self.db.commit()


if __name__ == "__main__":
    unittest.main()
