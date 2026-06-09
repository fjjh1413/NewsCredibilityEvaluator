from datetime import datetime
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1 import admin_knowledge
from app.models.knowledge_item import KnowledgeItem
from app.schemas.knowledge import KnowledgeCreate, KnowledgeOut, KnowledgeUpdate
from app.services.chroma_service import ChromaServiceError
from app.services.knowledge_service import (
    KnowledgeVectorSyncError,
    create_knowledge_item,
    delete_knowledge_item,
    search_similar_knowledge,
    update_knowledge_item,
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

    def test_knowledge_out_accepts_delete_failed_vector_status(self) -> None:
        now = datetime(2026, 1, 1)

        result = KnowledgeOut.model_validate(
            {
                "id": 1,
                "title": "Test title",
                "content": "Test content",
                "category": "society",
                "truth_label": "credible",
                "source_name": "official",
                "source_url": None,
                "publish_time": None,
                "summary": "summary",
                "keywords": "test",
                "debunking_explanation": None,
                "risk_level": "low",
                "admin_note": None,
                "vector_id": "knowledge:1",
                "vector_sync_status": "delete_failed",
                "vector_sync_error": "MySQL delete failed",
                "created_at": now,
                "updated_at": now,
            }
        )

        self.assertEqual(result.vector_sync_status, "delete_failed")

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

        def update_state(
            db,
            db_item,
            status,
            vector_id=None,
            error=None,
            auto_commit=True,
        ):
            db_item.vector_sync_status = status
            db_item.vector_id = vector_id or db_item.vector_id
            db_item.vector_sync_error = error
            return db_item

        mocked_update_state.side_effect = update_state

        result = create_knowledge_item(Mock(), _payload())

        self.assertEqual(result.vector_sync_status, "failed")
        self.assertIn("temporary Chroma failure", result.vector_sync_error)

    @patch("app.services.knowledge_service.upsert_knowledge_item_vector")
    @patch("app.services.knowledge_service.knowledge_crud.update_knowledge_vector_state")
    @patch("app.services.knowledge_service.knowledge_crud.update_knowledge_item")
    @patch("app.services.knowledge_service.get_knowledge_item")
    def test_update_commits_after_chroma_sync_succeeds(
        self,
        mocked_get,
        mocked_update,
        mocked_update_state,
        mocked_upsert,
    ) -> None:
        db = Mock()
        item = _knowledge_item(
            title="Old title",
            content="Old content",
            vector_id="knowledge:1",
            vector_sync_status="synced",
        )
        mocked_get.return_value = item
        mocked_upsert.return_value = "knowledge:1"

        def update_db(db_arg, db_item, item_in, auto_commit=True):
            self.assertFalse(auto_commit)
            db_item.title = item_in.title
            db_item.vector_sync_status = "pending"
            db_item.vector_sync_error = None
            return db_item

        def update_state(
            db_arg,
            db_item,
            status,
            vector_id=None,
            error=None,
            auto_commit=True,
        ):
            self.assertFalse(auto_commit)
            db_item.vector_sync_status = status
            db_item.vector_id = vector_id or db_item.vector_id
            db_item.vector_sync_error = error
            return db_item

        mocked_update.side_effect = update_db
        mocked_update_state.side_effect = update_state

        result = update_knowledge_item(db, 1, KnowledgeUpdate(title="New title"))

        self.assertEqual(result.title, "New title")
        self.assertEqual(result.vector_sync_status, "synced")
        mocked_update.assert_called_once()
        mocked_update_state.assert_called_once()
        db.commit.assert_called_once()
        db.refresh.assert_called_once_with(item)
        db.rollback.assert_not_called()

    @patch("app.services.knowledge_service.upsert_knowledge_item_vector")
    @patch("app.services.knowledge_service.knowledge_crud.update_knowledge_vector_state")
    @patch("app.services.knowledge_service.knowledge_crud.update_knowledge_item")
    @patch("app.services.knowledge_service.get_knowledge_item")
    def test_update_chroma_failure_rolls_back_mysql_and_raises(
        self,
        mocked_get,
        mocked_update,
        mocked_update_state,
        mocked_upsert,
    ) -> None:
        db = Mock()
        item = _knowledge_item(
            title="Old title",
            content="Old content",
            vector_id="knowledge:1",
            vector_sync_status="synced",
        )
        mocked_get.return_value = item
        mocked_upsert.side_effect = ChromaServiceError("temporary Chroma failure")

        def update_db(db_arg, db_item, item_in, auto_commit=True):
            db_item.title = item_in.title
            db_item.vector_sync_status = "pending"
            db_item.vector_sync_error = None
            return db_item

        def update_state(
            db_arg,
            db_item,
            status,
            vector_id=None,
            error=None,
            auto_commit=True,
        ):
            db_item.vector_sync_status = status
            db_item.vector_id = vector_id or db_item.vector_id
            db_item.vector_sync_error = error
            return db_item

        mocked_update.side_effect = update_db
        mocked_update_state.side_effect = update_state

        with self.assertRaisesRegex(KnowledgeVectorSyncError, "update failed"):
            update_knowledge_item(db, 1, KnowledgeUpdate(title="New title"))

        mocked_update.assert_called_once()
        mocked_update_state.assert_called_once()
        db.rollback.assert_called_once()
        db.commit.assert_not_called()
        db.refresh.assert_not_called()

    def test_update_chroma_failure_keeps_persisted_mysql_content(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        KnowledgeItem.__table__.create(bind=engine)
        session_factory = sessionmaker(bind=engine)
        db = session_factory()
        db.add(
            KnowledgeItem(
                id=1,
                title="Old title",
                content="Old content",
                truth_label="credible",
                vector_id="knowledge:1",
                vector_sync_status="synced",
                vector_sync_error=None,
            )
        )
        db.commit()

        with patch(
            "app.services.knowledge_service.upsert_knowledge_item_vector",
            side_effect=ChromaServiceError("temporary Chroma failure"),
        ):
            with self.assertRaisesRegex(KnowledgeVectorSyncError, "update failed"):
                update_knowledge_item(
                    db,
                    1,
                    KnowledgeUpdate(title="New title", content="New content"),
                )

        db.close()
        verify_db = session_factory()
        persisted_item = (
            verify_db.query(KnowledgeItem).filter(KnowledgeItem.id == 1).first()
        )

        self.assertIsNotNone(persisted_item)
        self.assertEqual(persisted_item.title, "Old title")
        self.assertEqual(persisted_item.content, "Old content")
        self.assertEqual(persisted_item.vector_sync_status, "synced")
        self.assertIsNone(persisted_item.vector_sync_error)

        verify_db.close()
        engine.dispose()

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
        def keep_item(
            db,
            db_item,
            status,
            vector_id=None,
            error=None,
            auto_commit=True,
        ):
            return db_item

        mocked_update_state.side_effect = keep_item

        with self.assertRaises(KnowledgeVectorSyncError):
            delete_knowledge_item(Mock(), 1)

        mocked_delete_db.assert_not_called()
        mocked_update_state.assert_called_once()

    @patch("app.services.knowledge_service.delete_knowledge_item_vector")
    @patch("app.services.knowledge_service.knowledge_crud.delete_knowledge_item")
    @patch("app.services.knowledge_service.get_knowledge_item")
    def test_delete_success_deletes_vector_then_mysql_record(
        self,
        mocked_get,
        mocked_delete_db,
        mocked_delete_vector,
    ) -> None:
        item = _knowledge_item(vector_id="knowledge:1")
        events: list[str] = []
        mocked_get.return_value = item
        mocked_delete_vector.side_effect = lambda deleted_item: events.append("vector")
        mocked_delete_db.side_effect = lambda db, deleted_item: events.append("mysql")

        delete_knowledge_item(Mock(), 1)

        self.assertEqual(events, ["vector", "mysql"])
        mocked_delete_vector.assert_called_once_with(item)
        mocked_delete_db.assert_called_once()

    @patch("app.services.knowledge_service.upsert_knowledge_item_vector")
    @patch("app.services.knowledge_service.knowledge_crud.get_knowledge_item")
    @patch("app.services.knowledge_service.knowledge_crud.delete_knowledge_item")
    @patch("app.services.knowledge_service.delete_knowledge_item_vector")
    @patch("app.services.knowledge_service.knowledge_crud.update_knowledge_vector_state")
    @patch("app.services.knowledge_service.get_knowledge_item")
    def test_delete_mysql_failure_restores_chroma_vector_and_marks_delete_failed(
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

        def update_state(
            db,
            db_item,
            status,
            vector_id=None,
            error=None,
            auto_commit=True,
        ):
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
        self.assertEqual(item.vector_sync_status, "delete_failed")
        self.assertIn("mysql delete failed", item.vector_sync_error.lower())

    @patch("app.services.knowledge_service.upsert_knowledge_item_vector")
    @patch("app.services.knowledge_service.knowledge_crud.get_knowledge_item")
    @patch("app.services.knowledge_service.knowledge_crud.delete_knowledge_item")
    @patch("app.services.knowledge_service.delete_knowledge_item_vector")
    @patch("app.services.knowledge_service.knowledge_crud.update_knowledge_vector_state")
    @patch("app.services.knowledge_service.get_knowledge_item")
    def test_delete_mysql_failure_marks_delete_failed_when_restore_fails(
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

        def update_state(
            db,
            db_item,
            status,
            vector_id=None,
            error=None,
            auto_commit=True,
        ):
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
        self.assertEqual(item.vector_sync_status, "delete_failed")
        self.assertIn("restore failed", item.vector_sync_error)

    @patch("app.services.knowledge_service.upsert_knowledge_item_vector")
    @patch("app.services.knowledge_service.knowledge_crud.get_knowledge_item")
    @patch("app.services.knowledge_service.knowledge_crud.delete_knowledge_item")
    @patch("app.services.knowledge_service.delete_knowledge_item_vector")
    @patch("app.services.knowledge_service.knowledge_crud.update_knowledge_vector_state")
    @patch("app.services.knowledge_service.get_knowledge_item")
    def test_delete_mysql_failure_restored_vector_raises_when_status_mark_fails(
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
        mocked_update_state.side_effect = RuntimeError("status write failed")

        with self.assertRaisesRegex(
            KnowledgeVectorSyncError,
            "vector was restored",
        ):
            delete_knowledge_item(Mock(), 1)

        mocked_delete_vector.assert_called_once_with(item)
        mocked_delete_db.assert_called_once()
        mocked_upsert.assert_called_once()
        mocked_update_state.assert_called_once()

    @patch(
        "app.api.v1.admin_knowledge.delete_knowledge_item",
        side_effect=KnowledgeVectorSyncError("MySQL delete failed; vector was restored"),
    )
    def test_delete_api_returns_conflict_when_delete_service_fails(
        self,
        mocked_delete_service,
    ) -> None:
        response = admin_knowledge.delete_knowledge(
            id=1,
            db=Mock(),
            current_admin=Mock(),
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(json.loads(response.body)["code"], 409)
        mocked_delete_service.assert_called_once()

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
