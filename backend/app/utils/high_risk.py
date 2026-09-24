from typing import Any

from app.core.constants import RISK_LEVEL_HIGH, RUMOR_SCORE_THRESHOLD
from app.core.assessment import UNKNOWN_RISK_LEVEL


def should_mark_high_risk(final_score: Any, risk_level: Any) -> bool:
    if str(risk_level or "").strip() == UNKNOWN_RISK_LEVEL:
        return False
    try:
        score = float(final_score)
    except (TypeError, ValueError):
        return True

    return score < RUMOR_SCORE_THRESHOLD or str(risk_level or "").strip() == RISK_LEVEL_HIGH
