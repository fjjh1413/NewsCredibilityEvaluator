import unittest
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from unittest.mock import Mock

from app.db.base import Base
from app.models.user import User


class SystemLogServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        self.SessionLocal = sessionmaker(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.db = self.SessionLocal()
        self.db.add(
            User(
                id=1,
                username="alice",
                password_hash="hashed",
                email="alice@example.com",
                role="user",
                status="active",
            )
        )
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_record_system_log_persists_audit_event(self) -> None:
        from app.services.system_log_service import record_system_log

        log = record_system_log(
            self.db,
            user_id=1,
            module="auth",
            action="login",
            description="用户登录成功",
            ip_address="203.0.113.7",
        )

        self.assertIsNotNone(log)
        self.assertEqual(log.user_id, 1)
        self.assertEqual(log.module, "auth")
        self.assertEqual(log.action, "login")
        self.assertEqual(log.description, "用户登录成功")
        self.assertEqual(log.ip_address, "203.0.113.7")

    def test_record_system_log_persists_structured_context_and_redacts_metadata(self) -> None:
        from app.services.system_log_service import record_system_log

        log = record_system_log(
            self.db,
            user_id=1,
            module="admin",
            action="update_user_role",
            description="role changed",
            ip_address="203.0.113.8",
            request_id="req-123",
            target_type="user",
            target_id=1,
            result_status="success",
            metadata_json={
                "before": {"role": "user"},
                "after": {"role": "admin"},
                "access_token": "secret-token",
                "items": list(range(25)),
            },
        )

        self.assertIsNotNone(log)
        self.assertEqual(log.request_id, "req-123")
        self.assertEqual(log.target_type, "user")
        self.assertEqual(log.target_id, "1")
        self.assertEqual(log.result_status, "success")
        self.assertEqual(log.metadata_json["before"]["role"], "user")
        self.assertEqual(log.metadata_json["after"]["role"], "admin")
        self.assertEqual(log.metadata_json["access_token"], "[redacted]")
        self.assertEqual(len(log.metadata_json["items"]), 20)

    def test_record_system_log_uses_request_id_context_by_default(self) -> None:
        from app.core.logging import request_id_context
        from app.services.system_log_service import record_system_log

        token = request_id_context.set("ctx-request-id")
        try:
            log = record_system_log(
                self.db,
                user_id=1,
                module="auth",
                action="login",
            )
        finally:
            request_id_context.reset(token)

        self.assertIsNotNone(log)
        self.assertEqual(log.request_id, "ctx-request-id")

    def test_record_system_log_accepts_user_object(self) -> None:
        from app.services.system_log_service import record_system_log

        log = record_system_log(
            self.db,
            user=SimpleNamespace(id=1),
            module="detection",
            action="detect_news",
            description="完成新闻检测 detection_id=12",
        )

        self.assertIsNotNone(log)
        self.assertEqual(log.user_id, 1)
        self.assertEqual(log.module, "detection")

    def test_record_system_log_does_not_block_business_flow_on_database_error(self) -> None:
        from app.services.system_log_service import record_system_log

        db = Mock()
        db.add.side_effect = SQLAlchemyError("database unavailable")

        with self.assertLogs("app.services.system_log_service", level="ERROR"):
            log = record_system_log(
                db,
                user_id=1,
                module="auth",
                action="login",
                description="用户登录成功",
            )

        self.assertIsNone(log)
        db.rollback.assert_called_once()


if __name__ == "__main__":
    unittest.main()
