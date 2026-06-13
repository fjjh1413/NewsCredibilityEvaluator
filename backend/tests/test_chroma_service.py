import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services import chroma_service
from app.services.chroma_service import (
    ChromaServiceError,
    build_knowledge_metadata,
    build_knowledge_vector_id,
    delete_knowledge_item_vector,
    normalize_top_k,
    search_knowledge_vectors,
    upsert_knowledge_item_vector,
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


class FailingQueryCollection:
    def query(self, **kwargs):
        raise RuntimeError("stale query handle")


class UpsertCollection:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.kwargs = None

    def upsert(self, **kwargs) -> None:
        self.kwargs = kwargs
        if self.should_fail:
            raise RuntimeError("stale upsert handle")


class DeleteCollection:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.kwargs = None

    def delete(self, **kwargs) -> None:
        self.kwargs = kwargs
        if self.should_fail:
            raise RuntimeError("stale delete handle")


class FakeClient:
    def __init__(self, collection) -> None:
        self.collection = collection
        self.collection_kwargs = None

    def get_or_create_collection(self, **kwargs):
        self.collection_kwargs = kwargs
        return self.collection


class FakePersistentClientFactory:
    def __init__(self, collections) -> None:
        self.collections = list(collections)
        self.clients = []

    def __call__(self, path: str):
        client = FakeClient(self.collections[len(self.clients)])
        client.path = path
        self.clients.append(client)
        return client


class ChromaServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        chroma_service._clients.clear()
        chroma_service._collections.clear()

    def tearDown(self) -> None:
        chroma_service._clients.clear()
        chroma_service._collections.clear()

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

    @patch("app.services.chroma_service.embed_text", return_value=[0.1, 0.2])
    @patch("app.services.chroma_service.get_knowledge_collection")
    def test_search_knowledge_vectors_formats_results(
        self,
        mocked_collection,
        mocked_embed,
    ) -> None:
        mocked_collection.return_value = FakeCollection()

        results = search_knowledge_vectors("Test", top_k=3)

        self.assertEqual(results[0]["vector_id"], "knowledge:1")
        self.assertEqual(results[0]["metadata"]["knowledge_id"], 1)
        self.assertEqual(results[0]["distance"], 0.25)
        self.assertEqual(results[0]["similarity_score"], 0.75)

    @patch("app.services.chroma_service.get_chroma_persist_dir", return_value="persist-a")
    def test_reset_cache_helpers_clear_cached_clients_and_collections(
        self,
        mocked_persist_dir,
    ) -> None:
        chroma_service._clients["persist-a"] = object()
        chroma_service._clients["persist-b"] = object()
        chroma_service._collections[("persist-a", "knowledge_items")] = object()
        chroma_service._collections[("persist-b", "knowledge_items")] = object()
        chroma_service._collections[("persist-a", "other")] = object()

        chroma_service.reset_collection_cache("knowledge_items")

        self.assertNotIn(("persist-a", "knowledge_items"), chroma_service._collections)
        self.assertNotIn(("persist-b", "knowledge_items"), chroma_service._collections)
        self.assertIn(("persist-a", "other"), chroma_service._collections)
        self.assertIn("persist-a", chroma_service._clients)

        chroma_service.reset_chroma_cache()

        self.assertEqual(chroma_service._clients, {})
        self.assertEqual(chroma_service._collections, {})

    @patch("app.services.chroma_service.embed_text", return_value=[0.1, 0.2])
    @patch("app.services.chroma_service.get_chroma_persist_dir")
    @patch("app.services.chroma_service._import_chromadb")
    def test_query_failure_clears_cache_and_retries_once(
        self,
        mocked_import,
        mocked_persist_dir,
        mocked_embed,
    ) -> None:
        mocked_persist_dir.return_value = "test-persist"
        factory = FakePersistentClientFactory([FailingQueryCollection(), FakeCollection()])
        mocked_import.return_value = SimpleNamespace(PersistentClient=factory)

        results = search_knowledge_vectors("Test", top_k=3)

        self.assertEqual(results[0]["vector_id"], "knowledge:1")
        self.assertEqual(len(factory.clients), 2)
        self.assertIs(chroma_service._clients["test-persist"], factory.clients[1])
        self.assertIs(
            chroma_service._collections[("test-persist", "knowledge_items")],
            factory.clients[1].collection,
        )

    @patch("app.services.chroma_service.embed_text", return_value=[0.1, 0.2])
    @patch("app.services.chroma_service.get_chroma_persist_dir")
    @patch("app.services.chroma_service._import_chromadb")
    def test_upsert_failure_clears_cache_and_retries_once(
        self,
        mocked_import,
        mocked_persist_dir,
        mocked_embed,
    ) -> None:
        mocked_persist_dir.return_value = "test-persist"
        successful_collection = UpsertCollection()
        factory = FakePersistentClientFactory(
            [UpsertCollection(should_fail=True), successful_collection]
        )
        mocked_import.return_value = SimpleNamespace(PersistentClient=factory)
        item = SimpleNamespace(
            id=1,
            title="Test",
            category="society",
            truth_label="credible",
            source_name="official",
            risk_level="low",
        )

        vector_id = upsert_knowledge_item_vector(item, "title: Test")

        self.assertEqual(vector_id, "knowledge:1")
        self.assertEqual(len(factory.clients), 2)
        self.assertEqual(successful_collection.kwargs["ids"], ["knowledge:1"])

    @patch("app.services.chroma_service.get_chroma_persist_dir")
    @patch("app.services.chroma_service._import_chromadb")
    def test_delete_failure_clears_cache_and_retries_once(
        self,
        mocked_import,
        mocked_persist_dir,
    ) -> None:
        mocked_persist_dir.return_value = "test-persist"
        successful_collection = DeleteCollection()
        factory = FakePersistentClientFactory(
            [DeleteCollection(should_fail=True), successful_collection]
        )
        mocked_import.return_value = SimpleNamespace(PersistentClient=factory)
        item = SimpleNamespace(id=1, vector_id="knowledge:1")

        delete_knowledge_item_vector(item)

        self.assertEqual(len(factory.clients), 2)
        self.assertEqual(successful_collection.kwargs["ids"], ["knowledge:1"])

    @patch("app.services.chroma_service.embed_text", return_value=[0.1, 0.2])
    @patch("app.services.chroma_service.get_chroma_persist_dir")
    @patch("app.services.chroma_service._import_chromadb")
    def test_query_retry_failure_raises_clear_error(
        self,
        mocked_import,
        mocked_persist_dir,
        mocked_embed,
    ) -> None:
        mocked_persist_dir.return_value = "test-persist"
        factory = FakePersistentClientFactory(
            [FailingQueryCollection(), FailingQueryCollection()]
        )
        mocked_import.return_value = SimpleNamespace(PersistentClient=factory)

        with self.assertRaisesRegex(
            ChromaServiceError,
            "Failed to query knowledge vectors after retry",
        ):
            search_knowledge_vectors("Test", top_k=3)

        self.assertEqual(len(factory.clients), 2)


if __name__ == "__main__":
    unittest.main()
