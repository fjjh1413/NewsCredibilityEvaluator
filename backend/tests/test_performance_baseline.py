import os
import unittest

from sqlalchemy import create_engine, text

from app.core.config import get_settings
from app.core.observability import instrument_sqlalchemy_engine, metrics_response


class PerformanceBaselineConfigTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_env = {
            name: os.environ.get(name)
            for name in (
                "OTEL_TRACING_ENABLED",
                "OTEL_SERVICE_NAME",
                "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
                "OTEL_EXPORTER_OTLP_ENDPOINT",
                "OTEL_TRACE_SAMPLE_RATIO",
            )
        }

    def tearDown(self) -> None:
        for name, value in self.previous_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        get_settings.cache_clear()

    def test_tracing_defaults_to_disabled(self) -> None:
        for name in self.previous_env:
            os.environ.pop(name, None)
        get_settings.cache_clear()

        settings = get_settings()

        self.assertFalse(settings.otel_tracing_enabled)
        self.assertEqual(settings.otel_trace_sample_ratio, 0.10)
        self.assertEqual(
            settings.otel_exporter_otlp_traces_endpoint,
            "http://127.0.0.1:4318/v1/traces",
        )

    def test_tracing_sample_ratio_is_clamped(self) -> None:
        os.environ["OTEL_TRACING_ENABLED"] = "true"
        os.environ["OTEL_TRACE_SAMPLE_RATIO"] = "2.5"
        get_settings.cache_clear()

        settings = get_settings()

        self.assertTrue(settings.otel_tracing_enabled)
        self.assertEqual(settings.otel_trace_sample_ratio, 1.0)


class DatabaseMetricTestCase(unittest.TestCase):
    def test_sqlalchemy_engine_records_query_duration_metric(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        instrument_sqlalchemy_engine(engine)

        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        body = metrics_response().body.decode("utf-8")

        self.assertIn("db_query_duration_seconds_bucket", body)
        self.assertIn('db_system="sqlite"', body)
        self.assertIn('operation="SELECT"', body)
        self.assertIn('status="ok"', body)


if __name__ == "__main__":
    unittest.main()
