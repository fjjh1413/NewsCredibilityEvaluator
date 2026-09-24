import json
import unittest
from types import SimpleNamespace

from app.services.detection_detail_service import (
    read_detection_analysis_payload,
    restore_detection_detail_payload,
)


class DetectionDetailServiceTests(unittest.TestCase):
    def test_reads_json_and_dictionary_payloads(self) -> None:
        payload = {"core_claims": [{"claim_id": "claim-1", "text": "主张"}]}

        self.assertEqual(
            read_detection_analysis_payload(
                SimpleNamespace(analysis_payload=json.dumps(payload, ensure_ascii=False))
            ),
            payload,
        )
        self.assertEqual(
            read_detection_analysis_payload(SimpleNamespace(analysis_payload=payload)),
            payload,
        )

    def test_invalid_or_non_object_payloads_fall_back_safely(self) -> None:
        for raw_payload in (None, "", "{broken", "[]", ["unexpected"]):
            with self.subTest(raw_payload=raw_payload):
                self.assertEqual(
                    read_detection_analysis_payload(
                        SimpleNamespace(analysis_payload=raw_payload)
                    ),
                    {},
                )

    def test_restores_only_public_detail_fields(self) -> None:
        record = SimpleNamespace(
            analysis_payload={
                "core_claims": [{"claim_id": "claim-1", "text": "主张"}],
                "rag_query_count": 3,
                "stage_latency_ms": {"rag_search": 20.0},
                "index_version": "v2",
                "retrieval_version": "hybrid",
                "candidate_parent_count": 2,
                "raw_prompt": "private model prompt must not leak",
                "internal_debug": {"credential": "private fixture"},
            }
        )

        detail = restore_detection_detail_payload({"id": 7}, record)

        self.assertEqual(detail["core_claims"][0]["claim_id"], "claim-1")
        self.assertEqual(detail["rag_query_count"], 3)
        self.assertEqual(detail["stage_latency_ms"], {"rag_search": 20.0})
        self.assertEqual(detail["index_version"], "v2")
        self.assertEqual(detail["retrieval_version"], "hybrid")
        self.assertEqual(detail["candidate_parent_count"], 2)
        self.assertEqual(detail["assessment_status"], "legacy")
        self.assertNotIn("raw_prompt", detail)
        self.assertNotIn("internal_debug", detail)


if __name__ == "__main__":
    unittest.main()
