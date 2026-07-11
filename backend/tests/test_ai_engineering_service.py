import json
import tempfile
import unittest
from pathlib import Path

from app.services.ai_engineering_service import get_ai_engineering_summary


def _case() -> dict:
    return {
        "case_id": "AI-SMOKE-001",
        "expected": {
            "risk_level": "high_risk",
            "score_range": [0, 45],
            "relevant_evidence_ids": ["kb:official-denial"],
        },
        "prediction": {
            "risk_level": "high_risk",
            "final_score": 28,
            "evidence_list": [{"evidence_id": "kb:official-denial"}],
            "candidate_evidence_list": [{"evidence_id": "kb:official-denial"}],
            "arbitration_status": "accepted",
            "quality_status": "ok",
            "stage_latency_ms": {"rag_search": 10, "llm_analysis": 20},
        },
    }


class AiEngineeringServiceTestCase(unittest.TestCase):
    def test_reads_existing_summary_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "summary.json"
            summary_path.write_text(
                json.dumps({
                    "schema_version": "ai-engineering-eval/v1",
                    "generated_at": "2026-07-11T00:00:00Z",
                    "metrics": {"total_cases": 3, "risk_level_accuracy": 1.0},
                    "gate": {"passed": True, "failures": [], "thresholds": {}},
                    "per_case": [{"case_id": "AI-SMOKE-001"}],
                }),
                encoding="utf-8",
            )

            data = get_ai_engineering_summary(
                summary_paths=[summary_path],
                sample_cases_path=Path(tmp) / "missing.jsonl",
            )

        self.assertEqual(data["source"]["type"], "summary_file")
        self.assertEqual(data["metrics"]["total_cases"], 3)
        self.assertTrue(data["gate"]["passed"])

    def test_falls_back_to_sample_cases_when_summary_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cases_path = Path(tmp) / "sample_cases.jsonl"
            cases_path.write_text(json.dumps(_case()) + "\n", encoding="utf-8")

            data = get_ai_engineering_summary(
                summary_paths=[Path(tmp) / "missing-summary.json"],
                sample_cases_path=cases_path,
            )

        self.assertEqual(data["source"]["type"], "sample_cases")
        self.assertEqual(data["metrics"]["total_cases"], 1)
        self.assertTrue(data["gate"]["passed"])


if __name__ == "__main__":
    unittest.main()
