import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services.rag.vector_index import (
    build_knowledge_chunk_vector_id,
    delete_knowledge_item_chunk_vectors,
    search_knowledge_chunk_vectors,
    upsert_knowledge_item_chunk_vectors,
)


class FakeCollection:
    def __init__(self) -> None:
        self.upsert_kwargs = None
        self.delete_kwargs = None
        self.query_kwargs = None

    def upsert(self, **kwargs) -> None:
        self.upsert_kwargs = kwargs

    def delete(self, **kwargs) -> None:
        self.delete_kwargs = kwargs

    def query(self, **kwargs):
        self.query_kwargs = kwargs
        return {
            "ids": [["knowledge:3:chunk:0", "knowledge:3:chunk:1"]],
            "documents": [["title: Example", "content: Body"]],
            "metadatas": [[
                {
                    "knowledge_id": 3,
                    "chunk_id": "knowledge:3:chunk:0",
                    "chunk_index": 0,
                    "chunk_type": "title_summary",
                    "title": "Example",
                    "summary": "Summary",
                    "category": "society",
                    "truth_label": "false",
                    "source_name": "Source",
                    "source_url": "https://example.com",
                    "risk_level": "high",
                    "vector_sync_status": "synced",
                    "index_version": "v2",
                },
                {
                    "knowledge_id": 3,
                    "chunk_id": "knowledge:3:chunk:1",
                    "chunk_index": 1,
                    "chunk_type": "content",
                    "title": "Example",
                    "summary": "Summary",
                    "category": "society",
                    "truth_label": "false",
                    "source_name": "Source",
                    "source_url": "https://example.com",
                    "risk_level": "high",
                    "vector_sync_status": "synced",
                    "index_version": "v2",
                },
            ]],
            "distances": [[0.2, 0.4]],
        }


class RagVectorIndexTestCase(unittest.TestCase):
    def _item(self):
        return SimpleNamespace(
            id=3,
            title="Example",
            content="Body paragraph. " * 30,
            category="society",
            truth_label="false",
            source_name="Source",
            source_url="https://example.com",
            publish_time=None,
            summary="Summary",
            keywords="alpha,beta",
            debunking_explanation="Debunked",
            risk_level="high",
            vector_sync_status="synced",
        )

    def test_build_knowledge_chunk_vector_id(self) -> None:
        self.assertEqual(build_knowledge_chunk_vector_id(8, 2), "knowledge:8:chunk:2")

    @patch("app.services.rag.vector_index.embed_texts")
    @patch("app.services.rag.vector_index._run_knowledge_collection_operation")
    def test_upsert_knowledge_item_chunk_vectors_batches_embeddings(
        self,
        mocked_operation,
        mocked_embed_texts,
    ) -> None:
        collection = FakeCollection()
        mocked_operation.side_effect = lambda _message, operation: operation(collection)
        mocked_embed_texts.return_value = [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]

        vector_ids = upsert_knowledge_item_chunk_vectors(
            self._item(),
            chunk_size=120,
            chunk_overlap=20,
        )

        self.assertGreaterEqual(len(vector_ids), 3)
        self.assertEqual(len(mocked_embed_texts.call_args.args[0]), len(vector_ids))
        self.assertEqual(collection.upsert_kwargs["ids"], vector_ids)
        self.assertTrue(
            all(
                metadata["index_version"] == "v2"
                for metadata in collection.upsert_kwargs["metadatas"]
            )
        )

    @patch("app.services.rag.vector_index._run_knowledge_collection_operation")
    def test_delete_knowledge_item_chunk_vectors_deletes_by_parent_and_version(
        self,
        mocked_operation,
    ) -> None:
        collection = FakeCollection()
        mocked_operation.side_effect = lambda _message, operation: operation(collection)

        delete_knowledge_item_chunk_vectors(self._item())

        self.assertEqual(
            collection.delete_kwargs["where"],
            {"$and": [{"knowledge_id": 3}, {"index_version": "v2"}]},
        )

    @patch("app.services.rag.vector_index.embed_text", return_value=[0.1, 0.2])
    @patch("app.services.rag.vector_index._run_knowledge_collection_operation")
    def test_search_knowledge_chunk_vectors_formats_scores_and_metadata(
        self,
        mocked_operation,
        mocked_embed_text,
    ) -> None:
        collection = FakeCollection()
        mocked_operation.side_effect = lambda _message, operation: operation(collection)

        results = search_knowledge_chunk_vectors("example query", top_n=2)

        self.assertEqual(results[0]["chunk_id"], "knowledge:3:chunk:0")
        self.assertEqual(results[0]["metadata"]["knowledge_id"], 3)
        self.assertEqual(results[0]["similarity_score"], 0.8)
        self.assertEqual(collection.query_kwargs["n_results"], 2)
        self.assertEqual(collection.query_kwargs["where"], {"index_version": "v2"})


if __name__ == "__main__":
    unittest.main()
