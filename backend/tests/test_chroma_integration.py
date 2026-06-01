import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services import chroma_service


class ChromaIntegrationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        try:
            import chromadb  # noqa: F401
        except ImportError:
            self.skipTest("chromadb is not installed")

    def test_upsert_search_and_delete_vector(self) -> None:
        item = SimpleNamespace(
            id=1,
            title="Verified news",
            category="society",
            truth_label="credible",
            source_name="official",
            risk_level="low",
            vector_id="knowledge:1",
        )

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            chroma_service._clients.clear()
            chroma_service._collections.clear()
            with patch("app.services.chroma_service.get_chroma_persist_dir", return_value=tmp_dir):
                vector_id = chroma_service.upsert_knowledge_item_vector(
                    item,
                    "title: Verified news\ncontent: official statement",
                )
                results = chroma_service.search_knowledge_vectors("official news", top_k=1)

                self.assertEqual(vector_id, "knowledge:1")
                self.assertEqual(results[0]["metadata"]["knowledge_id"], 1)

                chroma_service.delete_knowledge_item_vector(item)
                results_after_delete = chroma_service.search_knowledge_vectors(
                    "official news",
                    top_k=1,
                )

                self.assertEqual(results_after_delete, [])

            chroma_service._clients.clear()
            chroma_service._collections.clear()


if __name__ == "__main__":
    unittest.main()
