import os
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import detect as detect_api
from app.api.v1.detect import get_db, get_optional_current_user
from app.core.config import get_settings
from app.db.base import Base
from app.main import app
from app.models.detection_task import DetectionTask
from app.models.user import User
from app.schemas.detection import DetectNewsRequest
from app.services.detection_task_service import (
    create_detection_task,
    run_detection_task,
    serialize_detection_task,
)


VALID_CONTENT = "News content with enough detail for async detection validation."


class DetectionTaskServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.SessionLocal = sessionmaker(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.db = self.SessionLocal()
        self.user = User(
            id=101,
            username="task-user",
            password_hash="hashed",
            email="task-user@example.com",
            role="user",
            status="active",
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_create_detection_task_persists_payload_snapshot(self) -> None:
        task = create_detection_task(
            db=self.db,
            payload=DetectNewsRequest(
                title="Async news title",
                content=VALID_CONTENT,
                enable_web_search=False,
            ),
            current_user=self.user,
        )

        self.assertEqual(task.status, "queued")
        self.assertEqual(task.user_id, self.user.id)
        self.assertIn('"enable_web_search": false', task.request_payload)

        data = serialize_detection_task(task)
        self.assertEqual(data["task_id"], task.id)
        self.assertEqual(data["status"], "queued")
        self.assertIsNone(data["result"])

    def test_run_detection_task_marks_success_and_stores_result(self) -> None:
        task = create_detection_task(
            db=self.db,
            payload=DetectNewsRequest(title="Async news title", content=VALID_CONTENT),
            current_user=self.user,
        )
        user_id = self.user.id

        result = {
            "detection_id": 321,
            "created_at": datetime(2026, 7, 6, 9, 30),
            "final_score": 88.0,
            "evidence_score": 90.0,
            "llm_score": 84.0,
            "rule_score": 92.0,
            "risk_level": "credible",
            "judgement_result": "credible",
            "reason": "verified",
            "risk_points": [],
            "keywords": ["async"],
            "evidence_list": [],
            "similar_news": [],
            "suggestion": "none",
            "agent_steps": [],
            "agent_trace": {
                "version": "1.0",
                "agent_name": "evidence-investigation-agent",
                "status": "completed",
                "total_latency_ms": 5.0,
                "stages": [],
                "graph_execution": {
                    "version": "1.0",
                    "graph_name": "evidence-investigation-agent",
                    "visited_nodes": ["prepare_input", "persist_result"],
                    "transitions": [
                        {
                            "source": "prepare_input",
                            "target": "persist_result",
                            "route": None,
                        },
                        {
                            "source": "persist_result",
                            "target": "__end__",
                            "route": None,
                        },
                    ],
                    "node_runs": [],
                },
            },
            "disclaimer": "for reference",
        }

        with (
            patch(
                "app.services.detection_task_service.SessionLocal",
                self.SessionLocal,
            ),
            patch(
                "app.services.detection_task_service.detect_news_credibility",
                return_value=result,
            ) as mocked_detect,
        ):
            run_detection_task(task.id, celery_task_id="celery-1")

        self.db.expire_all()
        refreshed = self.db.get(DetectionTask, task.id)
        self.assertIsNotNone(refreshed)
        self.assertEqual(refreshed.status, "succeeded")
        self.assertEqual(refreshed.celery_task_id, "celery-1")
        self.assertEqual(refreshed.detection_id, 321)
        self.assertIsNotNone(refreshed.started_at)
        self.assertIsNotNone(refreshed.finished_at)
        self.assertIn('"detection_id": 321', refreshed.result_payload)
        self.assertIn('"graph_name": "evidence-investigation-agent"', refreshed.result_payload)
        serialized = serialize_detection_task(refreshed)
        self.assertEqual(
            serialized["result"]["agent_trace"]["graph_execution"]["visited_nodes"],
            ["prepare_input", "persist_result"],
        )
        mocked_detect.assert_called_once()
        self.assertEqual(mocked_detect.call_args.kwargs["current_user"].id, user_id)

    def test_run_detection_task_marks_failed_on_error(self) -> None:
        task = create_detection_task(
            db=self.db,
            payload=DetectNewsRequest(title="Async news title", content=VALID_CONTENT),
            current_user=self.user,
        )

        with (
            patch("app.services.detection_task_service.SessionLocal", self.SessionLocal),
            patch(
                "app.services.detection_task_service.detect_news_credibility",
                side_effect=RuntimeError("boom"),
            ),
        ):
            with self.assertRaises(RuntimeError):
                run_detection_task(task.id)

        self.db.expire_all()
        refreshed = self.db.get(DetectionTask, task.id)
        self.assertEqual(refreshed.status, "failed")
        self.assertEqual(refreshed.error_message, "boom")
        self.assertIsNotNone(refreshed.finished_at)


class DetectAsyncApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_async = os.environ.get("ASYNC_DETECTION_ENABLED")
        os.environ["ASYNC_DETECTION_ENABLED"] = "true"
        get_settings.cache_clear()

        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.SessionLocal = sessionmaker(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.db = self.SessionLocal()
        self.user = User(
            id=202,
            username="api-task-user",
            password_hash="hashed",
            email="api-task-user@example.com",
            role="user",
            status="active",
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

        app.dependency_overrides[get_db] = self._override_db
        app.dependency_overrides[get_optional_current_user] = lambda: self.user
        self.client = TestClient(app)
        rate_limiter = getattr(detect_api, "detector_rate_limiter", None)
        if rate_limiter is not None:
            rate_limiter.clear()

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()
        if self.previous_async is None:
            os.environ.pop("ASYNC_DETECTION_ENABLED", None)
        else:
            os.environ["ASYNC_DETECTION_ENABLED"] = self.previous_async
        get_settings.cache_clear()

    def _override_db(self):
        yield self.db

    def test_detect_news_returns_accepted_task_when_async_enabled(self) -> None:
        with patch("app.api.v1.detect.enqueue_detection_task", return_value="celery-123"):
            response = self.client.post(
                "/api/detect/news",
                json={
                    "title": "Async news title",
                    "content": VALID_CONTENT,
                    "enable_web_search": False,
                },
            )

        self.assertEqual(response.status_code, 202)
        body = response.json()
        self.assertEqual(body["code"], 200)
        self.assertEqual(body["data"]["status"], "queued")
        self.assertEqual(body["data"]["celery_task_id"], "celery-123")

        task_id = body["data"]["task_id"]
        task = self.db.get(DetectionTask, task_id)
        self.assertIsNotNone(task)
        self.assertEqual(task.user_id, self.user.id)
        self.assertIn('"enable_web_search": false', task.request_payload)

        status_response = self.client.get(f"/api/detect/tasks/{task_id}")
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()["data"]["task_id"], task_id)
