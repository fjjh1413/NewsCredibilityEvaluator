"""Tests for deterministic evidence arbitration quality controls."""

from __future__ import annotations

import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.schemas.detection import DetectNewsRequest
from app.services.detection_service import detect_news_credibility
from app.services.detection_service import validate_and_apply_llm_ranking
from app.services.evidence_arbitration_quality import (
    apply_arbitration_quality_controls,
    extract_core_claims,
    summarize_arbitration_quality,
)
from app.services.llm_service import build_evidence_arbitration_prompt


def _vector_result(knowledge_id: int, score: float) -> dict:
    return {
        "metadata": {
            "knowledge_id": knowledge_id,
            "title": f"Evidence {knowledge_id}",
            "summary": "Official evidence confirms the main claim.",
            "category": "society",
            "truth_label": "credible",
            "source_name": "official bureau",
            "source_url": "https://gov.example/evidence",
            "risk_level": "trusted",
            "vector_sync_status": "synced",
        },
        "similarity_score": score,
    }


class CoreClaimExtractionTests(unittest.TestCase):
    def test_extract_core_claims_returns_stable_claim_ids(self) -> None:
        claims = extract_core_claims(
            title="Official notice: transit policy starts next Monday",
            content=(
                "The city transport bureau announced a new transit policy. "
                "The policy starts next Monday. Commuters can use the mobile app."
            ),
            max_claims=3,
        )

        self.assertEqual([claim["claim_id"] for claim in claims], ["c1", "c2", "c3"])
        self.assertIn("transit policy", claims[0]["text"].lower())


class ArbitrationQualityControlTests(unittest.TestCase):
    def test_quality_controls_calibrate_authoritative_and_duplicate_evidence(self) -> None:
        ranked = [
            {
                "candidate_id": "web:official",
                "title": "Official bureau notice",
                "source_name": "City Transport Bureau",
                "source_url": "https://gov.example/news/policy",
                "summary": "Official notice confirms the policy starts next Monday.",
                "publish_time": "2026-07-09",
                "quality_score": 80,
                "relevance_score": 95,
                "stance": "support",
                "claim_ids": ["c1", "c2"],
            },
            {
                "candidate_id": "web:copy",
                "title": "Official bureau notice",
                "source_name": "Unknown repost",
                "source_url": "https://blog.example/repost",
                "summary": "Official notice confirms the policy starts next Monday.",
                "publish_time": "2026-07-09",
                "quality_score": 80,
                "relevance_score": 92,
                "stance": "support",
                "claim_ids": ["c1"],
            },
        ]
        claims = [
            {"claim_id": "c1", "text": "The policy was announced."},
            {"claim_id": "c2", "text": "The policy starts next Monday."},
        ]

        result = apply_arbitration_quality_controls(
            ranked=ranked,
            rejected=[],
            claims=claims,
            source_url="https://gov.example/news/policy",
        )

        adjusted = result["ranked"]
        self.assertGreater(
            adjusted[0]["calibrated_quality_score"],
            adjusted[1]["calibrated_quality_score"],
        )
        self.assertTrue(adjusted[1]["is_near_duplicate"])
        self.assertEqual(result["quality"]["claim_coverage"], 100.0)
        self.assertEqual(result["quality"]["unique_source_count"], 2)

    def test_contradiction_signal_is_reported_for_high_quality_counterevidence(self) -> None:
        ranked = [
            {
                "candidate_id": "web:official-denial",
                "title": "Official denial",
                "source_name": "National Health Commission",
                "source_url": "https://gov.example/denial",
                "summary": "The authority explicitly denies the viral claim.",
                "quality_score": 90,
                "relevance_score": 95,
                "stance": "contradict",
                "claim_ids": ["c1"],
            },
            {
                "candidate_id": "web:social",
                "title": "Viral claim",
                "source_name": "Social media account",
                "source_url": "https://social.example/post",
                "summary": "A social media post repeats the viral claim.",
                "quality_score": 60,
                "relevance_score": 80,
                "stance": "support",
                "claim_ids": ["c1"],
            },
        ]

        result = apply_arbitration_quality_controls(
            ranked=ranked,
            rejected=[],
            claims=[{"claim_id": "c1", "text": "The viral health claim is true."}],
            source_url=None,
        )

        quality = result["quality"]
        self.assertTrue(quality["has_high_quality_contradiction"])
        self.assertGreater(
            quality["contradict_weight"],
            quality["support_weight"],
        )
        self.assertEqual(result["ranked"][0]["candidate_id"], "web:official-denial")

    def test_quality_summary_marks_uncovered_claims(self) -> None:
        quality = summarize_arbitration_quality(
            ranked=[
                {
                    "candidate_id": "kb:1",
                    "calibrated_quality_score": 70,
                    "stance": "neutral",
                    "claim_ids": ["c1"],
                    "canonical_source": "kb:1",
                }
            ],
            claims=[
                {"claim_id": "c1", "text": "Covered"},
                {"claim_id": "c2", "text": "Uncovered"},
            ],
        )

        self.assertEqual(quality["claim_coverage"], 50.0)
        self.assertEqual(quality["uncovered_claim_ids"], ["c2"])


class ArbitrationContractIntegrationTests(unittest.TestCase):
    def test_prompt_includes_core_claim_contract(self) -> None:
        prompt = build_evidence_arbitration_prompt(
            title="Policy starts next Monday",
            content="The transport bureau says the policy starts next Monday.",
            evidence_list=[{"candidate_id": "kb:1", "title": "Official notice"}],
            claims=[{"claim_id": "c1", "text": "Policy starts next Monday."}],
        )

        self.assertIn('"claim_id": "c1"', prompt)
        self.assertIn("claim_ids", prompt)

    def test_validated_ranking_preserves_claim_ids(self) -> None:
        result = validate_and_apply_llm_ranking(
            candidates=[
                {
                    "candidate_id": "kb:1",
                    "title": "Official notice",
                    "summary": "The notice confirms the policy.",
                }
            ],
            arbitration={
                "ranked_evidence": [
                    {
                        "candidate_id": "kb:1",
                        "relevance_score": 91,
                        "quality_score": 88,
                        "stance": "support",
                        "claim_ids": ["c1"],
                        "reason": "Directly confirms the claim.",
                    }
                ],
                "rejected_evidence": [],
            },
        )

        self.assertEqual(result["errors"], [])
        self.assertEqual(result["ranked"][0]["claim_ids"], ["c1"])

    def test_detection_service_returns_backend_arbitration_quality(self) -> None:
        with (
            patch("app.services.detection_service.search_similar_knowledge") as mocked_search,
            patch("app.services.detection_service.analyze_news_credibility") as mocked_llm,
            patch("app.services.detection_service.calculate_rule_score") as mocked_rule,
            patch("app.services.detection_service.save_detection_record") as mocked_save,
            patch("app.services.detection_service.get_default_prompt_content") as mocked_prompt,
        ):
            mocked_search.return_value = [_vector_result(1, 0.8)]
            mocked_llm.return_value = {
                "llm_score": 78,
                "risk_level": "trusted",
                "reason": "Evidence supports the claim.",
                "evidence_quality": {
                    "coverage": 80,
                    "consistency": 85,
                    "score": 82,
                    "assessment": "Evidence is sufficient.",
                },
                "evidence_arbitration": {
                    "ranked_evidence": [
                        {
                            "candidate_id": "kb:1",
                            "relevance_score": 90,
                            "quality_score": 86,
                            "stance": "support",
                            "claim_ids": ["c1"],
                            "reason": "Directly supports the main claim.",
                        }
                    ],
                    "rejected_evidence": [],
                },
                "similar_news": [],
                "risk_points": [],
                "keywords": ["policy"],
                "suggestion": "Keep monitoring official updates.",
            }
            mocked_rule.return_value = {"rule_score": 80, "hit_rules": []}
            mocked_save.return_value = SimpleNamespace(
                id=321,
                created_at=datetime(2026, 7, 10, 12, 0, 0),
            )
            mocked_prompt.return_value = "Configured prompt {title} {content} {evidence_list}"

            result = detect_news_credibility(
                db=Mock(),
                payload=DetectNewsRequest(
                    title="Policy starts next Monday",
                    content="The transport bureau says the policy starts next Monday.",
                    source_url="https://gov.example/news/policy",
                ),
                current_user=SimpleNamespace(id=7, role="user"),
            )

        self.assertTrue(mocked_llm.call_args.kwargs["claims"])
        self.assertTrue(result["core_claims"])
        self.assertIn("claim_coverage", result["arbitration_quality"])
        self.assertIn("backend_arbitration_quality", result["evidence_quality"])
        self.assertIsNotNone(result["evidence_list"][0]["calibrated_quality_score"])


if __name__ == "__main__":
    unittest.main()
