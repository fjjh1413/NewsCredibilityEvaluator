import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services.rag.retrieval import search_similar_knowledge_v2


class RagRetrievalV2TestCase(unittest.TestCase):
    def _settings(self) -> SimpleNamespace:
        return SimpleNamespace(
            rag_dense_top_n=50,
            rag_parent_top_k=15,
            rag_chunks_per_parent=2,
            rag_lexical_enabled=True,
            rag_mmr_enabled=True,
        )

    def _metadata(self, knowledge_id: int, title: str) -> dict:
        return {
            "knowledge_id": knowledge_id,
            "title": title,
            "summary": f"{title} summary",
            "category": "society",
            "truth_label": "false",
            "source_name": "Source A",
            "source_url": f"https://example.com/{knowledge_id}",
            "publish_time": "",
            "risk_level": "high",
            "vector_sync_status": "synced",
            "index_version": "v2",
        }

    @patch("app.services.rag.retrieval.get_settings")
    @patch("app.services.rag.retrieval._search_lexical_candidates")
    @patch("app.services.rag.retrieval.search_knowledge_chunk_vectors")
    def test_search_aggregates_chunks_by_parent_and_caps_chunks(
        self,
        mocked_dense,
        mocked_lexical,
        mocked_settings,
    ) -> None:
        mocked_settings.return_value = self._settings()
        mocked_dense.return_value = [
            {
                "chunk_id": "knowledge:1:chunk:0",
                "document": "title chunk",
                "metadata": {
                    **self._metadata(1, "First"),
                    "chunk_id": "knowledge:1:chunk:0",
                    "chunk_index": 0,
                    "chunk_type": "title_summary",
                },
                "similarity_score": 0.91,
            },
            {
                "chunk_id": "knowledge:1:chunk:1",
                "document": "content chunk",
                "metadata": {
                    **self._metadata(1, "First"),
                    "chunk_id": "knowledge:1:chunk:1",
                    "chunk_index": 1,
                    "chunk_type": "content",
                },
                "similarity_score": 0.87,
            },
            {
                "chunk_id": "knowledge:1:chunk:2",
                "document": "lower chunk",
                "metadata": {
                    **self._metadata(1, "First"),
                    "chunk_id": "knowledge:1:chunk:2",
                    "chunk_index": 2,
                    "chunk_type": "content",
                },
                "similarity_score": 0.6,
            },
        ]
        mocked_lexical.return_value = []

        results = search_similar_knowledge_v2(object(), "query text", top_k=10)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["metadata"]["knowledge_id"], 1)
        self.assertEqual(len(results[0]["chunks"]), 2)
        self.assertEqual(results[0]["chunks"][0]["chunk_id"], "knowledge:1:chunk:0")
        self.assertEqual(results[0]["index_version"], "v2")
        self.assertGreater(results[0]["score_components"]["dense_score"], 0.9)

    @patch("app.services.rag.retrieval.get_settings")
    @patch("app.services.rag.retrieval._search_lexical_candidates")
    @patch("app.services.rag.retrieval.search_knowledge_chunk_vectors")
    def test_search_merges_lexical_only_candidates(
        self,
        mocked_dense,
        mocked_lexical,
        mocked_settings,
    ) -> None:
        mocked_settings.return_value = self._settings()
        mocked_dense.return_value = []
        mocked_lexical.return_value = [
            {
                "metadata": self._metadata(2, "Lexical"),
                "lexical_score": 0.8,
                "exact_score": 0.3,
            }
        ]

        results = search_similar_knowledge_v2(object(), "Lexical query", top_k=10)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["metadata"]["knowledge_id"], 2)
        self.assertEqual(results[0]["chunks"], [])
        self.assertEqual(results[0]["score_components"]["lexical_score"], 0.8)


if __name__ == "__main__":
    unittest.main()
