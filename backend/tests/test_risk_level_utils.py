import unittest

from app.core.constants import (
    RISK_LEVEL_HIGH,
    RISK_LEVEL_RUMOR,
    RISK_LEVEL_SUSPICIOUS,
    RISK_LEVEL_TRUSTED,
)
from app.utils.risk_level import get_risk_level_from_score


class RiskLevelUtilsTestCase(unittest.TestCase):
    def test_get_risk_level_from_score_keeps_existing_boundaries(self) -> None:
        cases = (
            (100, RISK_LEVEL_TRUSTED),
            (80, RISK_LEVEL_TRUSTED),
            (79.99, RISK_LEVEL_SUSPICIOUS),
            (60, RISK_LEVEL_SUSPICIOUS),
            (59.99, RISK_LEVEL_RUMOR),
            (40, RISK_LEVEL_RUMOR),
            (39.99, RISK_LEVEL_HIGH),
            (0, RISK_LEVEL_HIGH),
        )

        for score, expected_risk_level in cases:
            with self.subTest(score=score):
                self.assertEqual(get_risk_level_from_score(score), expected_risk_level)


if __name__ == "__main__":
    unittest.main()
