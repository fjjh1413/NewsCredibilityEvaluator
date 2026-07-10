import os
import unittest

from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app

VALID_SECRET_KEY = "cors-config-secret-key-00000000000000000001"


class CorsConfigTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_origins = os.environ.get("BACKEND_CORS_ORIGINS")
        self.previous_app_env = os.environ.get("APP_ENV")
        self.previous_secret_key = os.environ.get("SECRET_KEY")

    def tearDown(self) -> None:
        if self.previous_origins is None:
            os.environ.pop("BACKEND_CORS_ORIGINS", None)
        else:
            os.environ["BACKEND_CORS_ORIGINS"] = self.previous_origins
        if self.previous_app_env is None:
            os.environ.pop("APP_ENV", None)
        else:
            os.environ["APP_ENV"] = self.previous_app_env
        if self.previous_secret_key is None:
            os.environ.pop("SECRET_KEY", None)
        else:
            os.environ["SECRET_KEY"] = self.previous_secret_key
        get_settings.cache_clear()

    def test_wildcard_origin_disables_credentials(self) -> None:
        os.environ["BACKEND_CORS_ORIGINS"] = "*"
        get_settings.cache_clear()

        cors_options = self._cors_options()

        self.assertEqual(cors_options["allow_origins"], ["*"])
        self.assertFalse(cors_options["allow_credentials"])

    def test_specific_origins_enable_credentials(self) -> None:
        os.environ["BACKEND_CORS_ORIGINS"] = (
            "http://localhost:5173,http://127.0.0.1:5173"
        )
        get_settings.cache_clear()

        cors_options = self._cors_options()

        self.assertEqual(
            cors_options["allow_origins"],
            ["http://localhost:5173", "http://127.0.0.1:5173"],
        )
        self.assertTrue(cors_options["allow_credentials"])

    def test_production_rejects_wildcard_origin(self) -> None:
        os.environ["APP_ENV"] = "production"
        os.environ["SECRET_KEY"] = VALID_SECRET_KEY
        os.environ["BACKEND_CORS_ORIGINS"] = "*"
        get_settings.cache_clear()

        with self.assertRaisesRegex(RuntimeError, "BACKEND_CORS_ORIGINS"):
            create_app()

    def test_production_rejects_docker_secret_placeholder(self) -> None:
        os.environ["APP_ENV"] = "production"
        os.environ["SECRET_KEY"] = "replace_with_at_least_32_random_characters"
        os.environ["BACKEND_CORS_ORIGINS"] = "https://app.example.com"
        get_settings.cache_clear()

        with self.assertRaisesRegex(RuntimeError, "placeholder"):
            create_app()

    def test_production_disables_openapi_docs_and_sets_security_headers(self) -> None:
        os.environ["APP_ENV"] = "production"
        os.environ["SECRET_KEY"] = VALID_SECRET_KEY
        os.environ["BACKEND_CORS_ORIGINS"] = "https://app.example.com"
        get_settings.cache_clear()

        app = create_app()
        route_paths = {
            route.path
            for route in app.routes
            if hasattr(route, "path")
        }

        self.assertNotIn("/docs", route_paths)
        self.assertNotIn("/redoc", route_paths)
        self.assertIsNone(app.openapi_url)

        response = TestClient(app).get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertIn("frame-ancestors 'none'", response.headers["content-security-policy"])
        self.assertIn("max-age=31536000", response.headers["strict-transport-security"])

    def _cors_options(self) -> dict:
        app = create_app()
        for middleware in app.user_middleware:
            if middleware.cls is CORSMiddleware:
                return middleware.kwargs
        self.fail("CORSMiddleware is not configured")


if __name__ == "__main__":
    unittest.main()
