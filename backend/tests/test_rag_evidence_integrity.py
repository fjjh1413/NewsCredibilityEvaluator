"""Cross-stage checks use real temporary SQL records and mocked vector I/O."""

import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.knowledge_item import KnowledgeItem
from app.schemas.web_search import WebEvidenceItem
from app.services.knowledge_service import search_similar_knowledge
from app.services.rag.fusion import fuse_ranked_parent_results
from app.services.rag.retrieval import search_similar_knowledge_v2
from app.services.rag.vector_index import knowledge_revision_hash
from app.services.web.web_search_service import merge_evidence, should_trigger_web_search


class RagEvidenceIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        KnowledgeItem.__table__.create(self.engine)
        self.db = Session(self.engine)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)
        self.settings = SimpleNamespace(
            rag_index_version="v2", rag_dense_top_n=50, rag_parent_top_k=15,
            rag_chunks_per_parent=2, rag_lexical_enabled=False, rag_mmr_enabled=False,
            rag_fusion_strategy="rrf", rag_rrf_rank_constant=60,
            rag_supporting_spans_enabled=True, rag_supporting_span_count=2,
            rag_rule_rerank_enabled=True, rag_model_rerank_enabled=False,
        )
        settings_patch = patch("app.services.rag.retrieval.get_settings", return_value=self.settings)
        settings_patch.start()
        self.addCleanup(settings_patch.stop)
        dense_patch = patch("app.services.rag.retrieval.search_knowledge_chunk_vectors")
        self.dense = dense_patch.start()
        self.addCleanup(dense_patch.stop)

    def _item(self, title="Bridge reopened", status="synced"):
        item = KnowledgeItem(
            title=title, content="The bridge reopened after inspection.",
            summary="Bridge inspection notice", category="society", truth_label="true",
            source_name="Transport authority", source_url="https://example.org/bridge",
            risk_level="low", vector_sync_status=status,
        )
        self.db.add(item)
        self.db.commit()
        return item

    def _hit(self, item, cosine=0.2):
        return {
            "chunk_id": f"knowledge:{item.id}:chunk:0",
            "document": item.content,
            "metadata": {
                "knowledge_id": item.id, "index_version": "v2",
                "parent_revision": knowledge_revision_hash(item),
                "chunk_index": 0, "chunk_type": "content",
            },
            "similarity_score": max(0, cosine), "raw_cosine_score": cosine,
        }

    def test_deleted_changed_pending_and_unversioned_vectors_do_not_escape(self):
        current = self._item()
        changed = self._item("Changed")
        deleted = self._item("Deleted")
        pending = self._item("Pending", "pending")
        unversioned = self._item("Legacy")
        hits = [self._hit(item) for item in (current, changed, deleted, pending, unversioned)]
        changed.content = "The bridge remains closed."
        self.db.delete(deleted)
        hits[-1]["metadata"].pop("parent_revision")
        self.db.commit()
        self.dense.return_value = hits

        results = search_similar_knowledge_v2(self.db, "bridge")

        self.assertEqual([row["metadata"]["knowledge_id"] for row in results], [current.id])
        self.assertEqual(results[0]["metadata"]["source_url"], current.source_url)

    def test_parent_filter_is_rechecked_against_current_database(self):
        item = self._item()
        self.dense.return_value = [self._hit(item)]
        self.assertEqual(search_similar_knowledge_v2(self.db, "bridge", category="health"), [])

    def test_current_lexical_result_never_inherits_stale_dense_chunks(self):
        item = self._item()
        self.dense.return_value = [self._hit(item, 0.95)]
        item.content = "The bridge is still closed."
        item.summary = "Bridge remains closed"
        item.vector_sync_status = "pending"
        self.db.commit()
        self.settings.rag_lexical_enabled = True
        results = search_similar_knowledge_v2(self.db, "bridge")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["metadata"]["summary"], "Bridge remains closed")
        self.assertEqual(results[0]["chunks"], [])
        self.assertIsNone(results[0]["raw_cosine_score"])
        self.assertTrue(should_trigger_web_search(results, True))

    def test_v2_fusion_rerank_then_web_merge_keeps_cosine_and_current_context(self):
        item = self._item()
        self.dense.return_value = [self._hit(item, 0.2)]
        retrieved = search_similar_knowledge_v2(self.db, "bridge reopened")
        fused = fuse_ranked_parent_results(
            [retrieved, deepcopy(retrieved)], top_k=10,
            query_texts=["bridge reopened", "inspection"],
        )
        # Build the application-facing shape without calling the detection
        # workflow (the end-to-end API regression covers that mapping).
        local = [{**row, **row["metadata"]} for row in fused]
        self.assertEqual(local[0]["raw_cosine_score"], 0.2)
        self.assertEqual(local[0]["similarity_score"], 0.2)
        self.assertEqual(local[0]["fusion_score"], 1.0)
        self.assertIn("rerank_score", local[0])
        self.assertTrue(should_trigger_web_search(local, True))
        merged = merge_evidence(local, [WebEvidenceItem(
            title="Live notice", url="https://example.net/notice", summary="Inspection update"
        )])
        self.assertEqual(merged[0]["index_version"], "v2")
        self.assertEqual(merged[0]["chunks"], local[0]["chunks"])
        self.assertTrue(merged[0]["supporting_spans"])
        self.assertEqual(merged[0]["query_match_count"], 2)
        self.assertEqual(merged[0]["raw_cosine_score"], 0.2)
        self.assertEqual(merged[0]["fusion_score"], 1.0)

    def test_hybrid_v1_fallback_cannot_resurrect_stale_v2_chunks(self):
        item = self._item()
        self.dense.return_value = [self._hit(item)]
        item.content = "Corrected current content"
        self.db.commit()
        self.settings.rag_index_version = "hybrid"
        with patch("app.services.knowledge_service.get_settings", return_value=self.settings), \
             patch("app.services.knowledge_service.search_knowledge_vectors", return_value=self.dense.return_value):
            self.assertEqual(search_similar_knowledge(self.db, "bridge"), [])

    def test_revision_is_changed_by_evidence_updates_not_sync_timestamps(self):
        item = self._item()
        before = knowledge_revision_hash(item)
        item.vector_sync_status = "pending"
        item.vector_sync_error = "provider unavailable"
        self.assertEqual(knowledge_revision_hash(item), before)
        item.source_url = "https://example.org/corrected"
        self.assertNotEqual(knowledge_revision_hash(item), before)


if __name__ == "__main__":
    unittest.main()
