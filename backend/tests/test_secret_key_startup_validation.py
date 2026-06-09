import os
import unittest
from unittest.mock import patch

from app.core.config import get_settings


VALID_SECRET_KEY = "startup-validation-secret-key-0000000001"


class SecretKeyStartupValidationTestCase(unittest.TestCase):
    def tearDown(self) -> None:
        get_settings.cache_clear()

    def test_create_app_rejects_empty_secret_key_on_startup(self) -> None:
        main_module = self._load_main_module()

        with patch.dict(os.environ, {"SECRET_KEY": ""}, clear=False):
            get_settings.cache_clear()

            with self.assertRaisesRegex(RuntimeError, "SECRET_KEY is required"):
                main_module.create_app()

    def test_create_app_rejects_placeholder_secret_key_on_startup(self) -> None:
        main_module = self._load_main_module()

        with patch.dict(os.environ, {"SECRET_KEY": "change_me"}, clear=False):
            get_settings.cache_clear()

            with self.assertRaisesRegex(RuntimeError, "placeholder"):
                main_module.create_app()

    def test_create_app_rejects_weak_secret_key_in_production(self) -> None:
        main_module = self._load_main_module()

        with patch.dict(
            os.environ,
            {"APP_ENV": "production", "SECRET_KEY": "short-secret-key"},
            clear=False,
        ):
            get_settings.cache_clear()

            with self.assertRaisesRegex(RuntimeError, "too weak for production"):
                main_module.create_app()

    def test_create_app_accepts_configured_secret_key(self) -> None:
        main_module = self._load_main_module()

        with patch.dict(os.environ, {"SECRET_KEY": VALID_SECRET_KEY}, clear=False):
            get_settings.cache_clear()
            app = main_module.create_app()

        self.assertEqual(app.title, get_settings().project_name)

    def _load_main_module(self):
        with patch.dict(os.environ, {"SECRET_KEY": VALID_SECRET_KEY}, clear=False):
            get_settings.cache_clear()
            import app.main as main_module

        return main_module


if __name__ == "__main__":
    unittest.main()
