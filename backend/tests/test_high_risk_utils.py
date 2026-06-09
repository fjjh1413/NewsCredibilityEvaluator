import importlib
import unittest

from app.utils.high_risk import should_mark_high_risk


HIGH_RISK_LEVEL = "\u9ad8\u98ce\u9669\u8c23\u8a00"


class HighRiskUtilsTestCase(unittest.TestCase):
    def test_high_risk_threshold_constant_is_not_exported(self) -> None:
        constants = importlib.import_module("app.core.constants")
        removed_name = "HIGH_RISK" + "_SCORE_THRESHOLD"
        self.assertFalse(hasattr(constants, removed_name))

    def test_unparseable_final_score_is_marked_high_risk(self) -> None:
        for final_score in (None, "", "N/A"):
            with self.subTest(final_score=final_score):
                self.assertTrue(should_mark_high_risk(final_score, "low"))

    def test_score_below_40_is_marked_high_risk(self) -> None:
        self.assertTrue(should_mark_high_risk(39.99, "low"))

    def test_score_40_is_not_high_risk_by_score_alone(self) -> None:
        self.assertFalse(should_mark_high_risk(40, "low"))

    def test_high_risk_level_is_marked_even_with_high_score(self) -> None:
        self.assertTrue(should_mark_high_risk(95, HIGH_RISK_LEVEL))


if __name__ == "__main__":
    unittest.main()
