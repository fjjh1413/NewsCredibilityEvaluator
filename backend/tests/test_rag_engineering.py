import unittest

from app.services.rag.contextual_compression import add_supporting_spans_to_results
from app.services.rag.fusion import (
    fuse_ranked_parent_results,
    normalized_rrf_score,
)
from app.services.rag.query_planner import build_claim_aware_queries


class RagEngineeringTestCase(unittest.TestCase):
    def test_normalized_rrf_score_is_rank_based_and_calibrated(self) -> None:
        weights = {"dense": 0.70, "lexical": 0.25, "exact": 0.05}

        top_dense = normalized_rrf_score(
            {"dense": 1},
            weights=weights,
            rank_constant=60,
        )
        later_dense = normalized_rrf_score(
            {"dense": 5},
            weights=weights,
            rank_constant=60,
        )
        top_hybrid = normalized_rrf_score(
            {"dense": 1, "lexical": 1},
            weights=weights,
            rank_constant=60,
            exact_score=1.0,
        )

        self.assertAlmostEqual(top_dense, 0.70, places=6)
        self.assertGreater(top_dense, later_dense)
        self.assertAlmostEqual(top_hybrid, 1.0, places=6)

    def test_fuse_ranked_parent_results_rewards_cross_query_consensus(self) -> None:
        first_query_results = [
            {
                "metadata": {"knowledge_id": 1, "title": "A", "index_version": "v2"},
                "similarity_score": 0.95,
                "chunks": [{"chunk_id": "a-1", "document": "A first"}],
                "score_components": {"dense_score": 0.95},
            },
            {
                "metadata": {"knowledge_id": 2, "title": "B", "index_version": "v2"},
                "similarity_score": 0.62,
                "chunks": [{"chunk_id": "b-1", "document": "B first"}],
                "score_components": {"dense_score": 0.62},
            },
        ]
        second_query_results = [
            {
                "metadata": {"knowledge_id": 2, "title": "B", "index_version": "v2"},
                "similarity_score": 0.71,
                "chunks": [{"chunk_id": "b-2", "document": "B second"}],
                "score_components": {"dense_score": 0.71},
            },
            {
                "metadata": {"knowledge_id": 3, "title": "C", "index_version": "v2"},
                "similarity_score": 0.70,
                "chunks": [{"chunk_id": "c-1", "document": "C first"}],
                "score_components": {"dense_score": 0.70},
            },
        ]

        fused = fuse_ranked_parent_results(
            [first_query_results, second_query_results],
            top_k=3,
            rank_constant=60,
        )

        self.assertEqual(fused[0]["metadata"]["knowledge_id"], 2)
        self.assertEqual(fused[0]["query_match_count"], 2)
        self.assertGreaterEqual(fused[0]["similarity_score"], 0.71)
        self.assertEqual(
            {chunk["chunk_id"] for chunk in fused[0]["chunks"]},
            {"b-1", "b-2"},
        )
        self.assertIn("multi_query_rrf_score", fused[0]["score_components"])

    def test_build_claim_aware_queries_deduplicates_and_caps_claims(self) -> None:
        claims = [
            {"claim_id": "c1", "text": "Official says the bridge reopened today."},
            {"claim_id": "c2", "claim": "Official says the bridge reopened today."},
            {"claim_id": "c3", "text": "Traffic resumed after safety inspection."},
        ]

        queries = build_claim_aware_queries(
            title="Bridge reopened",
            content="Long article body",
            claims=claims,
            max_queries=3,
        )

        self.assertEqual(len(queries), 3)
        self.assertTrue(queries[0].startswith("title: Bridge reopened"))
        self.assertEqual(
            queries[1],
            "claim c1: Official says the bridge reopened today.",
        )
        self.assertEqual(
            queries[2],
            "claim c3: Traffic resumed after safety inspection.",
        )

    def test_add_supporting_spans_keeps_results_and_adds_chunk_spans(self) -> None:
        results = [
            {
                "metadata": {"knowledge_id": 1, "title": "Bridge notice"},
                "document": "Fallback document",
                "chunks": [
                    {
                        "chunk_id": "chunk-1",
                        "document": (
                            "The official transport notice says the bridge reopened "
                            "after a safety inspection."
                        ),
                    }
                ],
            }
        ]

        compressed = add_supporting_spans_to_results(
            results,
            query_texts=["bridge reopened safety inspection"],
            max_spans_per_result=2,
        )

        self.assertEqual(results[0]["chunks"][0].get("supporting_spans"), None)
        spans = compressed[0]["chunks"][0]["supporting_spans"]
        self.assertTrue(spans)
        self.assertIn("bridge", spans[0]["matched_terms"])
        self.assertIn("supporting_spans", compressed[0])


if __name__ == "__main__":
    unittest.main()
