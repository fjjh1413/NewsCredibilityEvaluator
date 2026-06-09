import os
import unittest

from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.main import create_app


class CorsConfigTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_origins = os.environ.get("BACKEND_CORS_ORIGINS")

    def tearDown(self) -> None:
        if self.previous_origins is None:
            os.environ.pop("BACKEND_CORS_ORIGINS", None)
        else:
            os.environ["BACKEND_CORS_ORIGINS"] = self.previous_origins
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

    def _cors_options(self) -> dict:
        app = create_app()
        for middleware in app.user_middleware:
            if middleware.cls is CORSMiddleware:
                return middleware.kwargs
        self.fail("CORSMiddleware is not configured")


if __name__ == "__main__":
    unittest.main()
