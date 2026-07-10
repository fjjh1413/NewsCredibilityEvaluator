import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services import knowledge_service


class RagV2KnowledgeSyncTestCase(unittest.TestCase):
    def _settings(self, version: str = "v2") -> SimpleNamespace:
        return SimpleNamespace(
            rag_index_version=version,
            rag_chunk_size=180,
            rag_chunk_overlap=30,
        )

    def _item(self) -> SimpleNamespace:
        return SimpleNamespace(
            id=5,
            title="Title",
            content="Content",
            vector_id=None,
        )

    @patch("app.services.knowledge_service._mark_vector_synced")
    @patch("app.services.knowledge_service.upsert_knowledge_item_chunk_vectors")
    @patch("app.services.knowledge_service.get_settings")
    def test_sync_uses_v2_chunk_index_when_configured(
        self,
        mocked_settings,
        mocked_upsert_chunks,
        mocked_mark_synced,
    ) -> None:
        item = self._item()
        mocked_settings.return_value = self._settings("v2")
        mocked_upsert_chunks.return_value = [
            "knowledge:5:chunk:0",
            "knowledge:5:chunk:1",
        ]
        mocked_mark_synced.return_value = item

        result = knowledge_service._sync_knowledge_vector(object(), item)

        self.assertIs(result, item)
        mocked_upsert_chunks.assert_called_once_with(
            item,
            chunk_size=180,
            chunk_overlap=30,
        )
        mocked_mark_synced.assert_called_once()
        self.assertEqual(mocked_mark_synced.call_args.args[2], "knowledge:5:v2")

    @patch("app.services.knowledge_service._mark_vector_synced")
    @patch("app.services.knowledge_service.upsert_knowledge_item_vector")
    @patch("app.services.knowledge_service.get_settings")
    def test_sync_keeps_v1_single_vector_as_default(
        self,
        mocked_settings,
        mocked_upsert_v1,
        mocked_mark_synced,
    ) -> None:
        item = self._item()
        mocked_settings.return_value = self._settings("v1")
        mocked_upsert_v1.return_value = "knowledge:5"
        mocked_mark_synced.return_value = item

        result = knowledge_service._sync_knowledge_vector(object(), item)

        self.assertIs(result, item)
        mocked_upsert_v1.assert_called_once()
        self.assertEqual(mocked_mark_synced.call_args.args[2], "knowledge:5")

    @patch("app.services.knowledge_service.delete_knowledge_item_chunk_vectors")
    @patch("app.services.knowledge_service.delete_knowledge_item_vector")
    @patch("app.services.knowledge_service.get_settings")
    def test_delete_vector_uses_active_index_version(
        self,
        mocked_settings,
        mocked_delete_v1,
        mocked_delete_v2,
    ) -> None:
        item = self._item()

        mocked_settings.return_value = self._settings("v2")
        knowledge_service._delete_vector_for_item(item)
        mocked_delete_v2.assert_called_once_with(item)
        mocked_delete_v1.assert_not_called()

        mocked_settings.return_value = self._settings("v1")
        knowledge_service._delete_vector_for_item(item)
        mocked_delete_v1.assert_called_once_with(item)


if __name__ == "__main__":
    unittest.main()
