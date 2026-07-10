import sys
import types
import unittest
from unittest.mock import Mock, patch

from app.core.config import Settings
from app.core import profiling


def _reset_profiling_state() -> None:
    profiling._PROFILING_CONFIGURED = False
    profiling._PROFILING_ENABLED = False


class ProfilingConfigTestCase(unittest.TestCase):
    def tearDown(self) -> None:
        _reset_profiling_state()

    def test_profiling_is_disabled_by_default(self) -> None:
        _reset_profiling_state()
        settings = Settings()

        profiling.configure_profiling(settings, role="backend")

        self.assertFalse(profiling.is_profiling_enabled())

    def test_configure_profiling_passes_pyroscope_options(self) -> None:
        _reset_profiling_state()
        fake_pyroscope = types.SimpleNamespace(configure=Mock())
        with (
            patch.dict(
                "os.environ",
                {
                    "PYROSCOPE_ENABLED": "true",
                    "PYROSCOPE_SERVER_ADDRESS": "http://pyroscope:4040",
                    "PYROSCOPE_APPLICATION_NAME": "newscred",
                    "PYROSCOPE_SAMPLE_RATE": "50",
                    "PYROSCOPE_BASIC_AUTH_USERNAME": "tenant-user",
                    "PYROSCOPE_BASIC_AUTH_PASSWORD": "tenant-pass",
                    "PYROSCOPE_TENANT_ID": "tenant-a",
                    "PROJECT_NAME": "newscred-backend",
                    "PROJECT_VERSION": "1.2.3",
                    "APP_ENV": "staging",
                },
                clear=True,
            ),
            patch.dict(sys.modules, {"pyroscope": fake_pyroscope}),
        ):
            settings = Settings()
            profiling.configure_profiling(settings, role="worker")

        self.assertTrue(profiling.is_profiling_enabled())
        fake_pyroscope.configure.assert_called_once()
        kwargs = fake_pyroscope.configure.call_args.kwargs
        self.assertEqual(kwargs["application_name"], "newscred.worker")
        self.assertEqual(kwargs["server_address"], "http://pyroscope:4040")
        self.assertEqual(kwargs["sample_rate"], 50)
        self.assertTrue(kwargs["oncpu"])
        self.assertTrue(kwargs["gil_only"])
        self.assertEqual(kwargs["basic_auth_username"], "tenant-user")
        self.assertEqual(kwargs["basic_auth_password"], "tenant-pass")
        self.assertEqual(kwargs["tenant_id"], "tenant-a")
        self.assertEqual(kwargs["tags"]["role"], "worker")
        self.assertEqual(kwargs["tags"]["env"], "staging")

    def test_missing_sdk_is_fatal_when_required(self) -> None:
        _reset_profiling_state()
        with (
            patch.dict(
                "os.environ",
                {
                    "PYROSCOPE_ENABLED": "true",
                    "PYROSCOPE_REQUIRED": "true",
                },
                clear=True,
            ),
            patch.dict(sys.modules, {"pyroscope": None}),
        ):
            settings = Settings()
            with self.assertRaisesRegex(RuntimeError, "pyroscope-io"):
                profiling.configure_profiling(settings, role="backend")


class ProfileBlockTestCase(unittest.TestCase):
    def tearDown(self) -> None:
        _reset_profiling_state()

    def test_profile_block_noops_when_disabled(self) -> None:
        _reset_profiling_state()
        with profiling.profile_block({"operation": "unit_test"}):
            value = "ok"

        self.assertEqual(value, "ok")

