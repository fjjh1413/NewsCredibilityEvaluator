import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services.chroma_service import (
    build_knowledge_metadata,
    build_knowledge_vector_id,
    normalize_top_k,
    search_knowledge_vectors,
)


class FakeCollection:
    def query(self, **kwargs):
        self.kwargs = kwargs
        return {
            "ids": [["knowledge:1"]],
            "documents": [["title: Test"]],
            "metadatas": [[{"knowledge_id": 1, "title": "Test"}]],
            "distances": [[0.25]],
        }


class ChromaServiceTestCase(unittest.TestCase):
    def test_build_knowledge_vector_id(self) -> None:
        item = SimpleNamespace(id=12)

        self.assertEqual(build_knowledge_vector_id(item), "knowledge:12")

    def test_normalize_top_k_limits_range(self) -> None:
        self.assertEqual(normalize_top_k(-10), 1)
        self.assertEqual(normalize_top_k(10), 10)
        self.assertEqual(normalize_top_k(999), 50)

    def test_build_knowledge_metadata_cleans_none_values(self) -> None:
        item = SimpleNamespace(
            id=1,
            title="  Test   Title ",
            category=None,
            truth_label=" credible ",
            source_name=None,
            risk_level=" low ",
        )

        metadata = build_knowledge_metadata(item)

        self.assertEqual(metadata["knowledge_id"], 1)
        self.assertEqual(metadata["title"], "Test Title")
        self.assertEqual(metadata["category"], "")
        self.assertEqual(metadata["truth_label"], "credible")
        self.assertEqual(metadata["source_name"], "")
        self.assertEqual(metadata["risk_level"], "low")

    @patch("app.services.chroma_service.get_knowledge_collection")
    def test_search_knowledge_vectors_formats_results(self, mocked_collection) -> None:
        mocked_collection.return_value = FakeCollection()

        results = search_knowledge_vectors("Test", top_k=3)

        self.assertEqual(results[0]["vector_id"], "knowledge:1")
        self.assertEqual(results[0]["metadata"]["knowledge_id"], 1)
        self.assertEqual(results[0]["distance"], 0.25)
        self.assertEqual(results[0]["similarity_score"], 0.75)


if __name__ == "__main__":
    unittest.main()
