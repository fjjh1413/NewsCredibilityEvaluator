import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services.rag.retrieval import search_similar_knowledge_v2
from app.services.rag.vector_index import knowledge_revision_hash


class RagRetrievalV2TestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.parents = {}
        loader = patch("app.services.rag.retrieval._load_current_parents")
        self.mocked_parents = loader.start()
        self.mocked_parents.side_effect = lambda _db, ids: {
            key: item for key, item in self.parents.items() if key in ids
        }
        self.addCleanup(loader.stop)

    def _settings(self) -> SimpleNamespace:
        return SimpleNamespace(
            rag_dense_top_n=50,
            rag_parent_top_k=15,
            rag_chunks_per_parent=2,
            rag_lexical_enabled=True,
            rag_mmr_enabled=True,
            rag_fusion_strategy="rrf",
            rag_rrf_rank_constant=60,
            rag_supporting_spans_enabled=True,
            rag_supporting_span_count=2,
            rag_rule_rerank_enabled=False,
        )

    def _metadata(self, knowledge_id: int, title: str) -> dict:
        metadata = {
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
        item = SimpleNamespace(id=knowledge_id, **{key: value for key, value in metadata.items() if key != "knowledge_id"})
        self.parents[knowledge_id] = item
        metadata["parent_revision"] = knowledge_revision_hash(item)
        return metadata

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
        self.assertEqual(results[0]["raw_cosine_score"], 0.91)
        self.assertEqual(results[0]["similarity_score"], 0.91)
        self.assertNotEqual(results[0]["fusion_score"], 0.91)

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
        self.assertIsNone(results[0]["raw_cosine_score"])
        self.assertIsNone(results[0]["similarity_score"])

    @patch("app.services.rag.retrieval.get_settings")
    @patch("app.services.rag.retrieval._search_lexical_candidates")
    @patch("app.services.rag.retrieval.search_knowledge_chunk_vectors")
    def test_rrf_fusion_prioritizes_cross_signal_consensus(
        self,
        mocked_dense,
        mocked_lexical,
        mocked_settings,
    ) -> None:
        mocked_settings.return_value = self._settings()
        mocked_dense.return_value = [
            {
                "chunk_id": "knowledge:1:chunk:0",
                "document": "dense only",
                "metadata": {
                    **self._metadata(1, "Dense"),
                    "chunk_id": "knowledge:1:chunk:0",
                    "chunk_index": 0,
                    "chunk_type": "content",
                },
                "similarity_score": 0.95,
            },
            {
                "chunk_id": "knowledge:2:chunk:0",
                "document": "dense and lexical",
                "metadata": {
                    **self._metadata(2, "Hybrid"),
                    "chunk_id": "knowledge:2:chunk:0",
                    "chunk_index": 0,
                    "chunk_type": "content",
                },
                "similarity_score": 0.30,
            },
        ]
        mocked_lexical.return_value = [
            {
                "metadata": self._metadata(2, "Hybrid"),
                "lexical_score": 0.9,
                "exact_score": 0.0,
            }
        ]

        results = search_similar_knowledge_v2(object(), "Hybrid query", top_k=10)

        self.assertEqual(results[0]["metadata"]["knowledge_id"], 2)
        self.assertEqual(results[0]["score_components"]["fusion_strategy"], "rrf")
        self.assertEqual(results[0]["score_components"]["dense_rank"], 2)
        self.assertEqual(results[0]["score_components"]["lexical_rank"], 1)

    @patch("app.services.rag.retrieval.get_settings")
    @patch("app.services.rag.retrieval._search_lexical_candidates")
    @patch("app.services.rag.retrieval.search_knowledge_chunk_vectors")
    def test_weighted_sum_strategy_keeps_score_blending_available(
        self,
        mocked_dense,
        mocked_lexical,
        mocked_settings,
    ) -> None:
        settings = self._settings()
        settings.rag_fusion_strategy = "weighted_sum"
        mocked_settings.return_value = settings
        mocked_dense.return_value = [
            {
                "chunk_id": "knowledge:1:chunk:0",
                "document": "dense only",
                "metadata": {
                    **self._metadata(1, "Dense"),
                    "chunk_id": "knowledge:1:chunk:0",
                    "chunk_index": 0,
                    "chunk_type": "content",
                },
                "similarity_score": 0.95,
            },
            {
                "chunk_id": "knowledge:2:chunk:0",
                "document": "lexical too",
                "metadata": {
                    **self._metadata(2, "Hybrid"),
                    "chunk_id": "knowledge:2:chunk:0",
                    "chunk_index": 0,
                    "chunk_type": "content",
                },
                "similarity_score": 0.30,
            },
        ]
        mocked_lexical.return_value = [
            {
                "metadata": self._metadata(2, "Hybrid"),
                "lexical_score": 0.9,
                "exact_score": 0.0,
            }
        ]

        results = search_similar_knowledge_v2(object(), "Hybrid query", top_k=10)

        self.assertEqual(results[0]["metadata"]["knowledge_id"], 1)
        self.assertEqual(
            results[0]["score_components"]["fusion_strategy"],
            "weighted_sum",
        )


if __name__ == "__main__":
    unittest.main()
