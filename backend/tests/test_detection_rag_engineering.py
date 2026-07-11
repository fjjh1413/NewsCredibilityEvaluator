import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.services.detection_service import _search_top10_evidence


class DetectionRagEngineeringTestCase(unittest.TestCase):
    def _settings(self) -> SimpleNamespace:
        return SimpleNamespace(
            rag_claim_aware_enabled=True,
            rag_claim_query_count=3,
            rag_rrf_rank_constant=60,
            rag_supporting_spans_enabled=True,
            rag_supporting_span_count=2,
        )

    def _result(self, knowledge_id: int, score: float, text: str) -> dict:
        return {
            "metadata": {
                "knowledge_id": knowledge_id,
                "title": f"Evidence {knowledge_id}",
                "summary": text,
                "source_name": "official",
                "index_version": "v2",
            },
            "document": text,
            "similarity_score": score,
            "chunks": [{"chunk_id": f"chunk-{knowledge_id}", "document": text}],
            "score_components": {"dense_score": score},
        }

    @patch("app.services.detection_service.get_settings")
    @patch("app.services.detection_service.search_similar_knowledge")
    def test_search_top10_evidence_uses_claim_aware_multi_query_fusion(
        self,
        mocked_search,
        mocked_get_settings,
    ) -> None:
        mocked_get_settings.return_value = self._settings()
        mocked_search.side_effect = [
            [
                self._result(
                    1,
                    0.92,
                    "The official notice says the bridge reopened.",
                )
            ],
            [
                self._result(
                    2,
                    0.78,
                    "Traffic resumed after a bridge safety inspection.",
                )
            ],
            [
                self._result(
                    2,
                    0.80,
                    "The safety inspection was completed before reopening.",
                )
            ],
        ]

        results = _search_top10_evidence(
            db=Mock(),
            title="Bridge reopened",
            content="The bridge reopened after safety inspection.",
            claims=[
                {
                    "claim_id": "c1",
                    "text": "The bridge reopened after official notice.",
                },
                {
                    "claim_id": "c2",
                    "text": "Traffic resumed after safety inspection.",
                },
            ],
        )

        self.assertEqual(mocked_search.call_count, 3)
        self.assertEqual(results[0]["metadata"]["knowledge_id"], 2)
        self.assertEqual(results[0]["query_match_count"], 2)
        self.assertIn("retrieval_queries", results[0])
        self.assertIn("supporting_spans", results[0]["chunks"][0])
        self.assertIn("multi_query_rrf_score", results[0]["score_components"])


if __name__ == "__main__":
    unittest.main()
