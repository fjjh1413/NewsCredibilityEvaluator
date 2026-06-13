import os
import unittest
from unittest.mock import patch

from app.db import seed_demo_data


class DemoPasswordResolutionTestCase(unittest.TestCase):
    def test_demo_password_env_var_takes_priority(self) -> None:
        with patch.dict(
            os.environ,
            {
                "DEMO_PASSWORD": "from-demo-password",
                "ADMIN_DEMO_PASSWORD": "from-admin-demo-password",
            },
            clear=True,
        ):
            password, generated = seed_demo_data.resolve_demo_password()

        self.assertEqual(password, "from-demo-password")
        self.assertFalse(generated)

    def test_admin_demo_password_env_var_is_fallback(self) -> None:
        with patch.dict(
            os.environ,
            {"ADMIN_DEMO_PASSWORD": "from-admin-demo-password"},
            clear=True,
        ):
            password, generated = seed_demo_data.resolve_demo_password()

        self.assertEqual(password, "from-admin-demo-password")
        self.assertFalse(generated)

    def test_random_password_is_generated_when_env_vars_are_missing(self) -> None:
        with (
            patch.dict(os.environ, {}, clear=True),
            patch(
                "app.db.seed_demo_data.secrets.token_urlsafe",
                return_value="generated-demo-password",
            ) as token_urlsafe,
        ):
            password, generated = seed_demo_data.resolve_demo_password()

        self.assertEqual(password, "generated-demo-password")
        self.assertTrue(generated)
        token_urlsafe.assert_called_once()


if __name__ == "__main__":
    unittest.main()
