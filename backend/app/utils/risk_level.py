from app.core.constants import (
    RISK_LEVEL_HIGH,
    RISK_LEVEL_RUMOR,
    RISK_LEVEL_SUSPICIOUS,
    RISK_LEVEL_TRUSTED,
    RUMOR_SCORE_THRESHOLD,
    SUSPICIOUS_SCORE_THRESHOLD,
    TRUSTED_SCORE_THRESHOLD,
)


def get_risk_level_from_score(score: float) -> str:
    score_value = float(score)
    if score_value >= TRUSTED_SCORE_THRESHOLD:
        return RISK_LEVEL_TRUSTED
    if score_value >= SUSPICIOUS_SCORE_THRESHOLD:
        return RISK_LEVEL_SUSPICIOUS
    if score_value >= RUMOR_SCORE_THRESHOLD:
        return RISK_LEVEL_RUMOR
    return RISK_LEVEL_HIGH
