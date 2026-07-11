"""Tests for the AI engineering evaluation gate.

The gate is intentionally offline: it evaluates captured detection outputs and
does not call the database, network, or any model provider.
"""

from __future__ import annotations

import unittest

from evaluation.ai_engineering.metrics import (
    context_precision_at_k,
    context_recall_at_k,
    evaluate_cases,
    rag_hit_at_k,
    reciprocal_rank_at_k,
    validate_prediction_contract,
)


def _prediction(**overrides) -> dict:
    base = {
        "risk_level": "high_risk",
        "final_score": 28,
        "evidence_list": [
            {"evidence_id": "kb:official-denial", "source": "local"},
            {"evidence_id": "web:mainstream-followup", "source": "web"},
        ],
        "candidate_evidence_list": [
            {"evidence_id": "kb:official-denial", "source": "local"},
            {"evidence_id": "kb:old-similar-case", "source": "local"},
            {"evidence_id": "web:mainstream-followup", "source": "web"},
        ],
        "arbitration_status": "accepted",
        "quality_status": "ok",
        "arbitration_quality": {
            "claim_coverage": 100,
            "unique_source_count": 2,
            "near_duplicate_count": 0,
            "has_high_quality_contradiction": False,
        },
        "stage_latency_ms": {
            "keyword_extraction": 12,
            "rag_search": 31,
            "llm_analysis": 220,
        },
    }
    base.update(overrides)
    return base


def _case(case_id: str, **overrides) -> dict:
    base = {
        "case_id": case_id,
        "input": {
            "title": "Synthetic case",
            "content": "A compact fixture that represents a captured detect result.",
        },
        "expected": {
            "risk_level": "high_risk",
            "score_range": [0, 45],
            "relevant_evidence_ids": [
                "kb:official-denial",
                "web:mainstream-followup",
            ],
        },
        "prediction": _prediction(),
    }
    base.update(overrides)
    return base


class RetrievalMetricTests(unittest.TestCase):
    def test_context_precision_rewards_ranked_relevant_evidence(self) -> None:
        score = context_precision_at_k(
            retrieved_ids=["noise", "rel-a", "rel-b"],
            relevant_ids={"rel-a", "rel-b"},
            k=3,
        )

        self.assertAlmostEqual(score, ((1 / 2) + (2 / 3)) / 2, places=4)

    def test_context_recall_counts_relevant_evidence_found(self) -> None:
        score = context_recall_at_k(
            retrieved_ids=["rel-a", "noise", "rel-b"],
            relevant_ids={"rel-a", "rel-b", "rel-c"},
            k=3,
        )

        self.assertAlmostEqual(score, 2 / 3, places=4)

    def test_rag_hit_and_reciprocal_rank_capture_first_relevant_parent(self) -> None:
        retrieved_ids = ["noise", "parent-2", "parent-3"]
        relevant_ids = {"parent-2", "parent-9"}

        self.assertEqual(rag_hit_at_k(retrieved_ids, relevant_ids, k=3), 1.0)
        self.assertAlmostEqual(
            reciprocal_rank_at_k(retrieved_ids, relevant_ids, k=3),
            0.5,
            places=4,
        )


class PredictionContractTests(unittest.TestCase):
    def test_valid_prediction_contract(self) -> None:
        errors = validate_prediction_contract(_prediction())

        self.assertEqual(errors, [])

    def test_invalid_prediction_reports_actionable_fields(self) -> None:
        errors = validate_prediction_contract({
            "risk_level": "",
            "final_score": 120,
            "evidence_list": [],
        })

        self.assertIn("risk_level", errors)
        self.assertIn("final_score", errors)
        self.assertIn("evidence_list", errors)
        self.assertIn("arbitration_status", errors)


class EvaluateCasesTests(unittest.TestCase):
    def test_evaluate_cases_returns_metrics_gate_and_per_case_rows(self) -> None:
        cases = [
            _case("AI-001"),
            _case(
                "AI-002",
                expected={
                    "risk_level": "medium_risk",
                    "score_range": [46, 74],
                    "relevant_evidence_ids": ["kb:weak-signal"],
                },
                prediction=_prediction(
                    risk_level="medium_risk",
                    final_score=61,
                    evidence_list=[
                        {"evidence_id": "kb:weak-signal", "source": "local"},
                        {"evidence_id": "kb:background", "source": "local"},
                    ],
                    candidate_evidence_list=[
                        {"evidence_id": "kb:weak-signal", "source": "local"},
                        {"evidence_id": "kb:background", "source": "local"},
                    ],
                    stage_latency_ms={"rag_search": 20, "llm_analysis": 180},
                ),
            ),
        ]

        summary = evaluate_cases(cases)

        self.assertTrue(summary["gate"]["passed"])
        self.assertEqual(summary["metrics"]["total_cases"], 2)
        self.assertEqual(summary["metrics"]["risk_level_accuracy"], 1.0)
        self.assertEqual(summary["metrics"]["contract_valid_rate"], 1.0)
        self.assertEqual(summary["metrics"]["arbitration_quality_present_rate"], 1.0)
        self.assertEqual(summary["metrics"]["claim_coverage_avg"], 100)
        self.assertEqual(summary["metrics"]["rag_hit_rate_at_k"], 1.0)
        self.assertGreater(summary["metrics"]["rag_mrr_at_k"], 0)
        self.assertEqual(summary["metrics"]["rag_empty_rate"], 0.0)
        self.assertEqual(len(summary["per_case"]), 2)

    def test_evaluate_cases_reports_parent_recall_and_claim_coverage(self) -> None:
        case = _case(
            "RAG-CLAIMS",
            expected={
                "risk_level": "high_risk",
                "score_range": [0, 45],
                "relevant_parent_ids": ["11", "22"],
                "required_claim_ids": ["c1", "c2"],
            },
            prediction=_prediction(
                candidate_evidence_list=[
                    {
                        "knowledge_id": 11,
                        "candidate_id": "kb:11",
                        "claim_ids": ["c1"],
                    },
                    {
                        "knowledge_id": 33,
                        "candidate_id": "kb:33",
                        "claim_ids": [],
                    },
                ],
            ),
        )

        summary = evaluate_cases([case], gates={"min_context_recall_at_k": 0.0})

        self.assertEqual(summary["metrics"]["parent_recall_at_k"], 0.5)
        self.assertEqual(summary["metrics"]["rag_claim_coverage_at_k"], 0.5)
        self.assertEqual(summary["per_case"][0]["parent_recall_at_k"], 0.5)
        self.assertEqual(summary["per_case"][0]["rag_claim_coverage_at_k"], 0.5)

    def test_gate_fails_with_metric_specific_reason(self) -> None:
        bad_case = _case(
            "AI-BAD",
            prediction=_prediction(
                risk_level="low_risk",
                final_score=88,
                evidence_list=[{"evidence_id": "noise", "source": "local"}],
                candidate_evidence_list=[{"evidence_id": "noise", "source": "local"}],
            ),
        )

        summary = evaluate_cases([bad_case])

        self.assertFalse(summary["gate"]["passed"])
        failed_metrics = {failure["metric"] for failure in summary["gate"]["failures"]}
        self.assertIn("risk_level_accuracy", failed_metrics)
        self.assertIn("context_recall_at_k", failed_metrics)


if __name__ == "__main__":
    unittest.main()
