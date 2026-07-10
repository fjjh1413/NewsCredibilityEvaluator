import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services.knowledge_service import search_similar_knowledge


class RagV2HybridFallbackTestCase(unittest.TestCase):
    @patch("app.services.knowledge_service.knowledge_crud.get_knowledge_item")
    @patch("app.services.knowledge_service.search_knowledge_vectors")
    @patch("app.services.knowledge_service.search_similar_knowledge_v2")
    @patch("app.services.knowledge_service.get_settings")
    def test_hybrid_falls_back_to_v1_when_v2_has_no_results(
        self,
        mocked_settings,
        mocked_v2,
        mocked_v1_search,
        mocked_get_item,
    ) -> None:
        mocked_settings.return_value = SimpleNamespace(rag_index_version="hybrid")
        mocked_v2.return_value = []
        mocked_v1_search.return_value = [
            {
                "vector_id": "knowledge:9",
                "metadata": {"knowledge_id": 9},
                "similarity_score": 0.7,
            }
        ]
        mocked_get_item.return_value = SimpleNamespace(
            id=9,
            title="Fallback",
            summary="Fallback summary",
            category="society",
            truth_label="false",
            source_name="Source",
            risk_level="high",
            vector_sync_status="synced",
        )

        results = search_similar_knowledge(object(), "query", top_k=10)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["metadata"]["knowledge_id"], 9)
        mocked_v2.assert_called_once()
        mocked_v1_search.assert_called_once()


if __name__ == "__main__":
    unittest.main()
