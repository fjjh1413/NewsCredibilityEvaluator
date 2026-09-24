import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.services.rag.index_audit import audit_rag_v2_index


class RagIndexAuditTestCase(unittest.TestCase):
    def _item(self, knowledge_id: int, title: str = "Indexed item") -> SimpleNamespace:
        return SimpleNamespace(
            id=knowledge_id,
            title=title,
            content="Body paragraph. " * 40,
            category="society",
            truth_label="credible",
            source_name="official",
            source_url="https://example.com",
            publish_time=None,
            summary="summary",
            keywords="keyword",
            debunking_explanation=None,
            risk_level="low",
            vector_sync_status="synced",
        )

    @patch("app.services.rag.index_audit.fetch_rag_v2_parent_chunks")
    @patch("app.services.rag.index_audit.knowledge_crud.get_all_knowledge_items")
    def test_audit_reports_missing_extra_and_stale_chunks(
        self,
        mocked_items,
        mocked_fetch_chunks,
    ) -> None:
        item = self._item(7)
        mocked_items.return_value = [item]
        mocked_fetch_chunks.return_value = [
            {
                "id": "knowledge:7:chunk:0",
                "document": "stale old document",
                "metadata": {
                    "knowledge_id": 7,
                    "chunk_id": "knowledge:7:chunk:0",
                    "chunk_index": 0,
                    "chunk_type": "title_summary",
                    "index_version": "v2",
                    "content_hash": "old-hash",
                },
            },
            {
                "id": "knowledge:7:chunk:999",
                "document": "extra document",
                "metadata": {
                    "knowledge_id": 7,
                    "chunk_id": "knowledge:7:chunk:999",
                    "chunk_index": 999,
                    "chunk_type": "content",
                    "index_version": "v2",
                    "content_hash": "extra-hash",
                },
            },
        ]

        summary = audit_rag_v2_index(Mock(), sample_limit=10)

        self.assertEqual(summary["status"], "failed")
        self.assertEqual(summary["total_items"], 1)
        self.assertEqual(summary["items_with_issues"], 1)
        issue_types = set(summary["issues_by_type"])
        self.assertIn("missing_chunk", issue_types)
        self.assertIn("extra_chunk", issue_types)
        self.assertIn("stale_chunk", issue_types)
        self.assertEqual(summary["items"][0]["knowledge_id"], 7)

    @patch("app.services.rag.index_audit.fetch_rag_v2_parent_chunks")
    @patch("app.services.rag.index_audit.knowledge_crud.get_all_knowledge_items")
    def test_audit_passes_when_expected_and_actual_chunks_match(
        self,
        mocked_items,
        mocked_fetch_chunks,
    ) -> None:
        item = self._item(3)
        mocked_items.return_value = [item]

        def fetch_chunks(knowledge_id: int) -> list[dict]:
            from app.services.rag.index_audit import expected_chunk_records_for_item

            return [
                {
                    "id": record["chunk_id"],
                    "document": record["content_hash"],
                    "metadata": {
                        "knowledge_id": knowledge_id,
                        "chunk_id": record["chunk_id"],
                        "chunk_index": record["chunk_index"],
                        "index_version": "v2",
                        "content_hash": record["content_hash"],
                        "parent_revision": record["parent_revision"],
                    },
                }
                for record in expected_chunk_records_for_item(item)
            ]

        mocked_fetch_chunks.side_effect = fetch_chunks

        summary = audit_rag_v2_index(Mock(), sample_limit=10)

        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["issue_count"], 0)
        self.assertEqual(summary["items_with_issues"], 0)


if __name__ == "__main__":
    unittest.main()
