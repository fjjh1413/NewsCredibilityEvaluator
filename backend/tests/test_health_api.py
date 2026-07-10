import os
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.redis_client import RedisHealthStatus
from app.main import create_app


VALID_SECRET_KEY = "health-api-secret-key-0000000000000000000001"


class HealthApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_env = {
            name: os.environ.get(name)
            for name in (
                "SECRET_KEY",
                "REDIS_ENABLED",
                "REDIS_REQUIRED",
                "BACKEND_CORS_ORIGINS",
                "LOG_FORMAT",
            )
        }
        os.environ["SECRET_KEY"] = VALID_SECRET_KEY
        os.environ["BACKEND_CORS_ORIGINS"] = "*"
        os.environ["LOG_FORMAT"] = "json"
        get_settings.cache_clear()

    def tearDown(self) -> None:
        for name, value in self.previous_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        get_settings.cache_clear()

    def test_ready_returns_ok_when_redis_is_disabled(self) -> None:
        os.environ["REDIS_ENABLED"] = "false"
        os.environ["REDIS_REQUIRED"] = "false"
        get_settings.cache_clear()

        response = TestClient(create_app()).get("/api/ready")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["data"]["status"], "ok")
        self.assertEqual(body["data"]["checks"]["redis"]["status"], "disabled")

    def test_ready_returns_503_when_required_redis_is_unavailable(self) -> None:
        os.environ["REDIS_ENABLED"] = "true"
        os.environ["REDIS_REQUIRED"] = "true"
        get_settings.cache_clear()

        with patch(
            "app.api.v1.health.redis_manager.health",
            new=AsyncMock(
                return_value=RedisHealthStatus(
                    enabled=True,
                    status="unavailable",
                    message="redis down",
                )
            ),
        ):
            response = TestClient(create_app()).get("/api/ready")

        self.assertEqual(response.status_code, 503)
        body = response.json()
        self.assertEqual(body["data"]["status"], "degraded")
        self.assertEqual(body["data"]["checks"]["redis"]["status"], "unavailable")

    def test_health_response_propagates_request_id(self) -> None:
        os.environ["REDIS_ENABLED"] = "false"
        os.environ["REDIS_REQUIRED"] = "false"
        get_settings.cache_clear()

        response = TestClient(create_app()).get(
            "/api/health",
            headers={"X-Request-ID": "test-request-id-123"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["x-request-id"], "test-request-id-123")

    def test_metrics_endpoint_exposes_http_request_metrics(self) -> None:
        os.environ["REDIS_ENABLED"] = "false"
        os.environ["REDIS_REQUIRED"] = "false"
        get_settings.cache_clear()

        client = TestClient(create_app())
        health_response = client.get("/api/health")
        metrics_response = client.get("/api/metrics")

        self.assertEqual(health_response.status_code, 200)
        self.assertEqual(metrics_response.status_code, 200)
        self.assertIn("text/plain", metrics_response.headers["content-type"])
        self.assertIn("http_requests_total", metrics_response.text)
        self.assertIn('route="/api/health"', metrics_response.text)


if __name__ == "__main__":
    unittest.main()
