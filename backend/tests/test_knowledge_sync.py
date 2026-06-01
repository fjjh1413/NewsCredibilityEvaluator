import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from pydantic import ValidationError

from app.schemas.knowledge import KnowledgeCreate
from app.services.chroma_service import ChromaServiceError
from app.services.knowledge_service import (
    KnowledgeVectorSyncError,
    create_knowledge_item,
    delete_knowledge_item,
    search_similar_knowledge,
)


def _knowledge_item(**overrides):
    data = {
        "id": 1,
        "title": "Test title",
        "content": "Test content",
        "category": "society",
        "summary": "summary",
        "keywords": "test",
        "truth_label": "credible",
        "debunking_explanation": None,
        "source_name": "official",
        "risk_level": "low",
        "vector_id": None,
        "vector_sync_status": "pending",
        "vector_sync_error": None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _payload() -> KnowledgeCreate:
    return KnowledgeCreate(
        title="Test title",
        content="Test content",
        truth_label="credible",
    )


class KnowledgeSyncTestCase(unittest.TestCase):
    def test_knowledge_create_rejects_vector_id(self) -> None:
        with self.assertRaises(ValidationError):
            KnowledgeCreate(
                title="Test title",
                content="Test content",
                truth_label="credible",
                vector_id="knowledge:999",
            )

    @patch("app.services.knowledge_service.upsert_knowledge_item_vector")
    @patch("app.services.knowledge_service.knowledge_crud.update_knowledge_vector_state")
    @patch("app.services.knowledge_service.knowledge_crud.create_knowledge_item")
    def test_create_records_failed_status_when_chroma_sync_fails(
        self,
        mocked_create,
        mocked_update_state,
        mocked_upsert,
    ) -> None:
        item = _knowledge_item()
        mocked_create.return_value = item
        mocked_upsert.side_effect = ChromaServiceError("temporary Chroma failure")

        def update_state(db, db_item, status, vector_id=None, error=None):
            db_item.vector_sync_status = status
            db_item.vector_id = vector_id or db_item.vector_id
            db_item.vector_sync_error = error
            return db_item

        mocked_update_state.side_effect = update_state

        result = create_knowledge_item(Mock(), _payload())

        self.assertEqual(result.vector_sync_status, "failed")
        self.assertIn("temporary Chroma failure", result.vector_sync_error)

    @patch("app.services.knowledge_service.delete_knowledge_item_vector")
    @patch("app.services.knowledge_service.knowledge_crud.delete_knowledge_item")
    @patch("app.services.knowledge_service.knowledge_crud.update_knowledge_vector_state")
    @patch("app.services.knowledge_service.get_knowledge_item")
    def test_delete_failure_keeps_mysql_record(
        self,
        mocked_get,
        mocked_update_state,
        mocked_delete_db,
        mocked_delete_vector,
    ) -> None:
        item = _knowledge_item(vector_id="knowledge:1")
        mocked_get.return_value = item
        mocked_delete_vector.side_effect = ChromaServiceError("delete failed")
        mocked_update_state.side_effect = lambda db, db_item, status, vector_id=None, error=None: db_item

        with self.assertRaises(KnowledgeVectorSyncError):
            delete_knowledge_item(Mock(), 1)

        mocked_delete_db.assert_not_called()
        mocked_update_state.assert_called_once()

    @patch("app.services.knowledge_service.upsert_knowledge_item_vector")
    @patch("app.services.knowledge_service.knowledge_crud.get_knowledge_item")
    @patch("app.services.knowledge_service.knowledge_crud.delete_knowledge_item")
    @patch("app.services.knowledge_service.delete_knowledge_item_vector")
    @patch("app.services.knowledge_service.knowledge_crud.update_knowledge_vector_state")
    @patch("app.services.knowledge_service.get_knowledge_item")
    def test_delete_mysql_failure_restores_chroma_vector(
        self,
        mocked_get,
        mocked_update_state,
        mocked_delete_vector,
        mocked_delete_db,
        mocked_get_db_item,
        mocked_upsert,
    ) -> None:
        item = _knowledge_item(vector_id="knowledge:1", vector_sync_status="synced")
        mocked_get.return_value = item
        mocked_delete_db.side_effect = RuntimeError("mysql delete failed")
        mocked_get_db_item.return_value = item
        mocked_upsert.return_value = "knowledge:1"

        def update_state(db, db_item, status, vector_id=None, error=None):
            db_item.vector_sync_status = status
            db_item.vector_id = vector_id or db_item.vector_id
            db_item.vector_sync_error = error
            return db_item

        mocked_update_state.side_effect = update_state

        with self.assertRaisesRegex(
            KnowledgeVectorSyncError,
            "vector was restored",
        ):
            delete_knowledge_item(Mock(), 1)

        mocked_delete_vector.assert_called_once_with(item)
        mocked_delete_db.assert_called_once()
        mocked_upsert.assert_called_once()
        self.assertEqual(item.vector_sync_status, "synced")
        self.assertIsNone(item.vector_sync_error)

    @patch("app.services.knowledge_service.upsert_knowledge_item_vector")
    @patch("app.services.knowledge_service.knowledge_crud.get_knowledge_item")
    @patch("app.services.knowledge_service.knowledge_crud.delete_knowledge_item")
    @patch("app.services.knowledge_service.delete_knowledge_item_vector")
    @patch("app.services.knowledge_service.knowledge_crud.update_knowledge_vector_state")
    @patch("app.services.knowledge_service.get_knowledge_item")
    def test_delete_mysql_failure_marks_failed_when_restore_fails(
        self,
        mocked_get,
        mocked_update_state,
        mocked_delete_vector,
        mocked_delete_db,
        mocked_get_db_item,
        mocked_upsert,
    ) -> None:
        item = _knowledge_item(vector_id="knowledge:1", vector_sync_status="synced")
        mocked_get.return_value = item
        mocked_delete_db.side_effect = RuntimeError("mysql delete failed")
        mocked_get_db_item.return_value = item
        mocked_upsert.side_effect = ChromaServiceError("restore failed")

        def update_state(db, db_item, status, vector_id=None, error=None):
            db_item.vector_sync_status = status
            db_item.vector_id = vector_id or db_item.vector_id
            db_item.vector_sync_error = error
            return db_item

        mocked_update_state.side_effect = update_state

        with self.assertRaisesRegex(
            KnowledgeVectorSyncError,
            "vector restore failed",
        ):
            delete_knowledge_item(Mock(), 1)

        mocked_delete_vector.assert_called_once_with(item)
        mocked_delete_db.assert_called_once()
        mocked_upsert.assert_called_once()
        self.assertEqual(item.vector_sync_status, "failed")
        self.assertIn("restore failed", item.vector_sync_error)

    @patch("app.services.knowledge_service.search_knowledge_vectors")
    @patch("app.services.knowledge_service.knowledge_crud.get_knowledge_item")
    def test_search_limits_top_k_and_filters_deleted_mysql_records(
        self,
        mocked_get_item,
        mocked_search,
    ) -> None:
        mocked_search.return_value = [
            {
                "vector_id": "knowledge:1",
                "document": "title: existing",
                "metadata": {"knowledge_id": 1},
                "distance": 0.1,
                "similarity_score": 0.9,
            },
            {
                "vector_id": "knowledge:2",
                "document": "title: deleted",
                "metadata": {"knowledge_id": 2},
                "distance": 0.2,
                "similarity_score": 0.8,
            },
        ]
        mocked_get_item.side_effect = [
            _knowledge_item(id=1, title="Existing"),
            None,
        ]

        results = search_similar_knowledge(Mock(), "query", top_k=999)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["metadata"]["knowledge_id"], 1)
        self.assertEqual(mocked_search.call_args.kwargs["top_k"], 50)


if __name__ == "__main__":
    unittest.main()
