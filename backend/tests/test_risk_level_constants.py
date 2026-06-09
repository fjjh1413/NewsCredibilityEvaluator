import importlib
import importlib.util
import unittest

from app.services.detection_service import build_final_risk_level
from app.utils.high_risk import should_mark_high_risk
from app.utils.risk_level import get_risk_level_from_score


class RiskLevelConstantsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.assertIsNotNone(
            importlib.util.find_spec("app.core.constants"),
            "app.core.constants should define shared risk level thresholds",
        )
        self.constants = importlib.import_module("app.core.constants")

    def test_constants_define_expected_levels_and_thresholds(self) -> None:
        self.assertEqual(self.constants.RISK_LEVEL_TRUSTED, "可信新闻")
        self.assertEqual(self.constants.RISK_LEVEL_SUSPICIOUS, "存疑信息")
        self.assertEqual(self.constants.RISK_LEVEL_RUMOR, "疑似谣言")
        self.assertEqual(self.constants.RISK_LEVEL_HIGH, "高风险谣言")
        self.assertEqual(self.constants.TRUSTED_SCORE_THRESHOLD, 80)
        self.assertEqual(self.constants.SUSPICIOUS_SCORE_THRESHOLD, 60)
        self.assertEqual(self.constants.RUMOR_SCORE_THRESHOLD, 40)
        removed_name = "HIGH_RISK" + "_SCORE_THRESHOLD"
        self.assertFalse(hasattr(self.constants, removed_name))

    def test_score_boundaries_keep_existing_risk_levels(self) -> None:
        cases = (
            (80, "可信新闻"),
            (60, "存疑信息"),
            (40, "疑似谣言"),
            (39.99, "高风险谣言"),
        )

        for score, expected_risk_level in cases:
            with self.subTest(score=score):
                self.assertEqual(build_final_risk_level(score), expected_risk_level)
                self.assertEqual(get_risk_level_from_score(score), expected_risk_level)

    def test_high_risk_marking_boundaries_keep_existing_behavior(self) -> None:
        self.assertFalse(should_mark_high_risk(40, "疑似谣言"))
        self.assertTrue(should_mark_high_risk(39.99, "疑似谣言"))
        self.assertTrue(should_mark_high_risk(95, "高风险谣言"))


if __name__ == "__main__":
    unittest.main()
