import unittest

from app.services.detection_service import _format_evidence_list


class DetectionRagV2FieldsTestCase(unittest.TestCase):
    def test_format_evidence_list_preserves_v2_retrieval_fields(self) -> None:
        evidence = _format_evidence_list(
            [
                {
                    "metadata": {
                        "knowledge_id": 11,
                        "title": "Chunked evidence",
                        "summary": "summary",
                        "category": "society",
                        "truth_label": "false",
                        "source_name": "official",
                        "source_url": "https://example.com/11",
                        "publish_time": "2026-01-01",
                        "risk_level": "high",
                        "index_version": "v2",
                    },
                    "similarity_score": 0.88,
                    "chunks": [
                        {
                            "chunk_id": "knowledge:11:chunk:0",
                            "chunk_type": "title_summary",
                            "document": "title chunk",
                            "similarity_score": 0.88,
                        }
                    ],
                    "score_components": {
                        "dense_score": 0.88,
                        "lexical_score": 0.2,
                        "exact_score": 0.0,
                        "final_score": 0.666,
                    },
                    "index_version": "v2",
                }
            ]
        )

        self.assertEqual(evidence[0]["knowledge_id"], 11)
        self.assertEqual(evidence[0]["source_url"], "https://example.com/11")
        self.assertEqual(evidence[0]["publish_time"], "2026-01-01")
        self.assertEqual(evidence[0]["index_version"], "v2")
        self.assertEqual(evidence[0]["chunks"][0]["chunk_id"], "knowledge:11:chunk:0")
        self.assertEqual(evidence[0]["score_components"]["dense_score"], 0.88)


if __name__ == "__main__":
    unittest.main()
