import unittest
from types import SimpleNamespace

from app.core.assessment import stored_assessment


class StoredAssessmentTests(unittest.TestCase):
    def test_old_high_scores_do_not_override_failed_or_uncovered_analysis(self):
        record = SimpleNamespace(final_score=99, evidence_matches=[object()])
        for coverage, expected in ((0, "insufficient_evidence"), (101, "degraded"),
                                   (True, "degraded"), (float("nan"), "degraded")):
            with self.subTest(coverage=coverage):
                status, _ = stored_assessment(record, {"arbitration_status": "ok",
                    "quality_status": "ok", "evidence_quality": {"coverage": coverage}})
                self.assertEqual(status, expected)
        status, _ = stored_assessment(record, {"arbitration_status": "provider_error"})
        self.assertEqual(status, "degraded")

    def test_missing_historical_diagnostics_cannot_be_claimed_completed(self):
        record = SimpleNamespace(final_score=99, evidence_matches=[object()])
        status, _ = stored_assessment(record, {"arbitration_status": "ok", "quality_status": "ok"})
        self.assertEqual(status, "legacy")
        record.evidence_matches = []
        status, _ = stored_assessment(record, {"arbitration_status": "ok", "quality_status": "ok"})
        self.assertEqual(status, "insufficient_evidence")


if __name__ == "__main__":
    unittest.main()
