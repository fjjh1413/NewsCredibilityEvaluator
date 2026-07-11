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
                            "supporting_spans": [
                                {"text": "title chunk", "matched_terms": ["title"]}
                            ],
                        }
                    ],
                    "supporting_spans": [
                        {"text": "title chunk", "matched_terms": ["title"]}
                    ],
                    "score_components": {
                        "dense_score": 0.88,
                        "lexical_score": 0.2,
                        "exact_score": 0.0,
                        "fusion_strategy": "rrf",
                        "final_score": 0.666,
                    },
                    "query_match_count": 2,
                    "query_hits": [{"query_index": 0, "rank": 1}],
                    "retrieval_queries": ["title: Chunked evidence"],
                    "retrieval_query_count": 2,
                    "retrieval_query_strategy": "claim_aware_multi_query",
                    "multi_query_rrf_score": 0.9,
                    "rerank_stage": "rule",
                    "rule_rerank_score": 0.82,
                    "rerank_order": 1,
                    "index_version": "v2",
                }
            ]
        )

        self.assertEqual(evidence[0]["knowledge_id"], 11)
        self.assertEqual(evidence[0]["source_url"], "https://example.com/11")
        self.assertEqual(evidence[0]["publish_time"], "2026-01-01")
        self.assertEqual(evidence[0]["index_version"], "v2")
        self.assertEqual(evidence[0]["chunks"][0]["chunk_id"], "knowledge:11:chunk:0")
        self.assertEqual(
            evidence[0]["chunks"][0]["supporting_spans"][0]["matched_terms"],
            ["title"],
        )
        self.assertEqual(evidence[0]["query_match_count"], 2)
        self.assertEqual(evidence[0]["retrieval_query_count"], 2)
        self.assertEqual(evidence[0]["retrieval_query_strategy"], "claim_aware_multi_query")
        self.assertEqual(evidence[0]["multi_query_rrf_score"], 0.9)
        self.assertEqual(evidence[0]["rerank_stage"], "rule")
        self.assertEqual(evidence[0]["rule_rerank_score"], 0.82)
        self.assertEqual(evidence[0]["score_components"]["dense_score"], 0.88)
        self.assertEqual(evidence[0]["score_components"]["fusion_strategy"], "rrf")


if __name__ == "__main__":
    unittest.main()
