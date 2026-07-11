import unittest

from app.services.rag.reranker import rerank_parent_results


class RagRerankerTestCase(unittest.TestCase):
    def _result(
        self,
        knowledge_id: int,
        *,
        similarity_score: float,
        source_name: str = "source",
        query_match_count: int = 1,
        span_count: int = 0,
        fusion_score: float = 0.0,
    ) -> dict:
        spans = [
            {"text": f"supporting span {index}", "matched_terms": ["claim"]}
            for index in range(span_count)
        ]
        return {
            "metadata": {
                "knowledge_id": knowledge_id,
                "title": f"Evidence {knowledge_id}",
                "source_name": source_name,
            },
            "similarity_score": similarity_score,
            "query_match_count": query_match_count,
            "supporting_spans": spans,
            "chunks": [{"supporting_spans": spans}],
            "score_components": {
                "final_score": fusion_score,
                "rrf_score": fusion_score,
            },
        }

    def test_rule_rerank_promotes_claim_supported_consensus_evidence(self) -> None:
        results = [
            self._result(1, similarity_score=0.92, query_match_count=1, span_count=0),
            self._result(
                2,
                similarity_score=0.72,
                query_match_count=3,
                span_count=2,
                fusion_score=0.9,
            ),
        ]

        reranked = rerank_parent_results(
            results,
            query_text="claim-aware query",
            top_k=2,
            model_enabled=False,
        )

        self.assertEqual(reranked[0]["metadata"]["knowledge_id"], 2)
        self.assertEqual(reranked[0]["rerank_stage"], "rule")
        self.assertGreater(reranked[0]["rule_rerank_score"], reranked[1]["rule_rerank_score"])
        self.assertEqual(reranked[0]["rerank_original_rank"], 2)

    def test_rule_rerank_applies_source_diversity_penalty(self) -> None:
        results = [
            self._result(1, similarity_score=0.9, source_name="same"),
            self._result(2, similarity_score=0.88, source_name="same"),
            self._result(3, similarity_score=0.84, source_name="different"),
        ]

        reranked = rerank_parent_results(results, query_text="query", top_k=3)

        self.assertEqual(reranked[0]["metadata"]["knowledge_id"], 1)
        self.assertEqual(reranked[1]["metadata"]["knowledge_id"], 3)
        self.assertLess(reranked[2]["diversity_adjusted_rerank_score"], reranked[2]["rule_rerank_score"])

    def test_optional_model_reranker_can_override_rule_order(self) -> None:
        results = [
            self._result(1, similarity_score=0.9),
            self._result(2, similarity_score=0.6),
        ]

        def model_reranker(query_text: str, candidates: list[dict]) -> list[dict]:
            self.assertEqual(query_text, "query")
            return [
                {"knowledge_id": 2, "score": 0.99, "reason": "model says direct match"},
                {"knowledge_id": 1, "score": 0.10},
            ]

        reranked = rerank_parent_results(
            results,
            query_text="query",
            top_k=2,
            model_enabled=True,
            model_reranker=model_reranker,
        )

        self.assertEqual(reranked[0]["metadata"]["knowledge_id"], 2)
        self.assertEqual(reranked[0]["rerank_stage"], "model")
        self.assertEqual(reranked[0]["model_rerank_reason"], "model says direct match")


if __name__ == "__main__":
    unittest.main()
