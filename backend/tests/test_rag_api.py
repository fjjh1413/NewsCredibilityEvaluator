import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from app.core.deps import get_current_user
from app.db.session import get_db
from app.main import app


def _override_current_user():
    return SimpleNamespace(id=1, username="tester", role="user", status="active")


def _override_db():
    return Mock()


class RagApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[get_current_user] = _override_current_user
        app.dependency_overrides[get_db] = _override_db
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    @patch("app.api.v1.rag.search_similar_knowledge")
    def test_search_supports_title_content_contract(self, mocked_search) -> None:
        mocked_search.return_value = [
            {
                "metadata": {
                    "knowledge_id": 1,
                    "title": "Similar news",
                    "summary": "summary",
                    "category": "society",
                    "truth_label": "credible",
                    "source_name": "official",
                    "risk_level": "low",
                    "vector_sync_status": "synced",
                },
                "similarity_score": 0.83,
            }
        ]

        response = self.client.post(
            "/api/rag/search",
            json={
                "title": "News title",
                "content": "News content",
                "top_k": 10,
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertIn("title: News title", data["query"])
        self.assertIn("content: News content", data["query"])
        self.assertEqual(data["top_k"], 10)
        self.assertEqual(data["results"][0]["id"], 1)
        self.assertEqual(data["results"][0]["vector_sync_status"], "synced")
        self.assertNotIn("items", data)

    @patch("app.api.v1.rag.search_similar_knowledge")
    def test_search_keeps_query_compatibility(self, mocked_search) -> None:
        mocked_search.return_value = []

        response = self.client.post(
            "/api/rag/search",
            json={"query": "legacy search text", "top_k": 5},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["query"], "legacy search text")
        self.assertEqual(data["top_k"], 5)
        self.assertEqual(data["results"], [])

    @patch("app.api.v1.rag.search_similar_knowledge")
    def test_search_exposes_v2_debug_fields_without_breaking_legacy_fields(
        self,
        mocked_search,
    ) -> None:
        mocked_search.return_value = [
            {
                "metadata": {
                    "knowledge_id": 2,
                    "title": "Chunked news",
                    "summary": "summary",
                    "category": "society",
                    "truth_label": "false",
                    "source_name": "official",
                    "risk_level": "high",
                    "vector_sync_status": "synced",
                    "index_version": "v2",
                    "parent_revision": "current-revision",
                },
                "similarity_score": 0.91,
                "raw_cosine_score": 0.91,
                "fusion_score": 0.687,
                "index_version": "v2",
                "chunks": [
                    {
                        "chunk_id": "knowledge:2:chunk:0",
                        "chunk_type": "title_summary",
                        "document": "title chunk",
                        "similarity_score": 0.91,
                    }
                ],
                "score_components": {
                    "dense_score": 0.91,
                    "lexical_score": 0.2,
                    "exact_score": 0.0,
                    "final_score": 0.687,
                },
                "rerank_stage": "rule",
                "rule_rerank_score": 0.82,
                "rerank_order": 1,
            }
        ]

        response = self.client.post(
            "/api/rag/search",
            json={"query": "chunked", "top_k": 5},
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()["data"]["results"][0]
        self.assertEqual(result["id"], 2)
        self.assertEqual(result["raw_cosine_score"], 0.91)
        self.assertEqual(result["fusion_score"], 0.687)
        self.assertEqual(result["parent_revision"], "current-revision")
        self.assertEqual(result["index_version"], "v2")
        self.assertEqual(result["chunks"][0]["chunk_id"], "knowledge:2:chunk:0")
        self.assertEqual(result["score_components"]["dense_score"], 0.91)
        self.assertEqual(result["rerank_stage"], "rule")
        self.assertEqual(result["rule_rerank_score"], 0.82)

    @patch("app.api.v1.rag.search_similar_knowledge")
    def test_title_content_takes_priority_over_query(self, mocked_search) -> None:
        mocked_search.return_value = []

        response = self.client.post(
            "/api/rag/search",
            json={
                "title": "Preferred title",
                "content": "Preferred content",
                "query": "legacy text",
            },
        )

        self.assertEqual(response.status_code, 200)
        query_text = mocked_search.call_args.kwargs["query_text"]
        self.assertIn("title: Preferred title", query_text)
        self.assertIn("content: Preferred content", query_text)
        self.assertNotEqual(query_text, "legacy text")

    def test_search_rejects_empty_input(self) -> None:
        response = self.client.post("/api/rag/search", json={})

        self.assertEqual(response.status_code, 422)

    def test_search_rejects_oversized_top_k(self) -> None:
        response = self.client.post(
            "/api/rag/search",
            json={"query": "news", "top_k": 1000},
        )

        self.assertEqual(response.status_code, 422)

    @patch("app.api.v1.rag.audit_rag_v2_index")
    def test_audit_endpoint_returns_index_health_summary(self, mocked_audit) -> None:
        mocked_audit.return_value = {
            "status": "ok",
            "total_items": 2,
            "checked_items": 2,
            "items_with_issues": 0,
            "issue_count": 0,
            "issues_by_type": {},
            "items": [],
        }

        response = self.client.get("/api/rag/audit")

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["checked_items"], 2)
        mocked_audit.assert_called_once()

    @patch("app.api.v1.rag.audit_rag_v2_index")
    def test_audit_endpoint_returns_503_when_chroma_fails(self, mocked_audit) -> None:
        from app.services.chroma_service import ChromaServiceError

        mocked_audit.side_effect = ChromaServiceError("chroma down")

        response = self.client.get("/api/rag/audit")

        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
