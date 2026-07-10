import unittest
from unittest.mock import patch

from app.services.detection_service import _record_stage_latency


class DetectionStageLatencyTestCase(unittest.TestCase):
    @patch("app.services.detection_service.time.perf_counter")
    def test_record_stage_latency_rounds_elapsed_milliseconds(self, mocked_perf) -> None:
        mocked_perf.return_value = 12.3456
        stage_latency_ms: dict[str, float] = {}

        _record_stage_latency(stage_latency_ms, "rag", 10.0)

        self.assertEqual(stage_latency_ms["rag"], 2345.6)


if __name__ == "__main__":
    unittest.main()
