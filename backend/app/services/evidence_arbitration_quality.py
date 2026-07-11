"""Deterministic quality controls for LLM evidence arbitration.

The LLM decides relevance and stance; this module calibrates that decision with
auditable backend signals: claim coverage, source quality, freshness, duplicate
evidence, source diversity, and contradiction strength.
"""

from __future__ import annotations

import hashlib
import math
import re
from datetime import date, datetime
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import urlparse

from app.utils.text_cleaner import clean_text


AUTHORITY_HINTS = (
    "gov",
    "government",
    "official",
    "commission",
    "ministry",
    "bureau",
    "authority",
    "agency",
    "department",
    "court",
    "hospital",
    "university",
    "institute",
    "新华社",
    "人民日报",
    "央视",
    "卫健委",
    "公安",
    "法院",
    "政府",
    "官方",
)
LOW_TRUST_HINTS = (
    "social",
    "weibo",
    "wechat",
    "tiktok",
    "douyin",
    "forum",
    "blog",
    "unknown",
    "自媒体",
    "网友",
    "网传",
)
CLAIM_SPLIT_RE = re.compile(r"[。！？!?；;\n]+|(?<=[.!?])\s+")
TOKEN_RE = re.compile(r"[A-Za-z0-9_]{2,}|[\u4e00-\u9fff]{2,}")


def extract_core_claims(
    title: str,
    content: str,
    max_claims: int = 5,
) -> list[dict[str, str]]:
    """Extract stable claim candidates without calling an LLM.

    This is intentionally conservative. It gives arbitration a claim map for
    coverage checks; it is not a full natural-language claim parser.
    """
    seen: set[str] = set()
    claims: list[dict[str, str]] = []
    fragments = [
        clean_text(title, max_length=240),
        *_split_sentences(clean_text(content, max_length=3000)),
    ]
    for fragment in fragments:
        text = _normalize_space(fragment)
        if len(text) < 8:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        claims.append({"claim_id": f"c{len(claims) + 1}", "text": text[:240]})
        if len(claims) >= max_claims:
            break
    return claims


def apply_arbitration_quality_controls(
    ranked: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
    claims: list[dict[str, str]],
    source_url: str | None,
) -> dict[str, Any]:
    """Calibrate ranked evidence and return adjusted evidence plus quality."""
    prepared: list[dict[str, Any]] = []
    seen_fingerprints: list[str] = []

    for item in ranked:
        evidence = dict(item)
        canonical_source = canonicalize_source(evidence)
        source_reliability = source_reliability_score(evidence, source_url)
        freshness = freshness_score(evidence)
        extraction_confidence = extraction_confidence_score(evidence)
        duplicate_penalty, fingerprint = _duplicate_penalty(evidence, seen_fingerprints)
        seen_fingerprints.append(fingerprint)

        raw_quality = _bounded_float(evidence.get("quality_score"), default=0.0)
        calibrated = raw_quality * source_reliability * freshness * extraction_confidence * duplicate_penalty
        evidence["canonical_source"] = canonical_source
        evidence["source_reliability_score"] = round(source_reliability * 100, 2)
        evidence["freshness_score"] = round(freshness * 100, 2)
        evidence["extraction_confidence_score"] = round(extraction_confidence * 100, 2)
        evidence["diversity_penalty"] = round(duplicate_penalty * 100, 2)
        evidence["is_near_duplicate"] = duplicate_penalty < 1.0
        evidence["claim_ids"] = normalize_claim_ids(evidence.get("claim_ids"), claims)
        evidence["calibrated_quality_score"] = round(_clamp(calibrated, 0.0, 100.0), 2)
        evidence["calibrated_evidence_score"] = round(
            _clamp(
                _bounded_float(evidence.get("relevance_score"), default=0.0) * 0.55
                + evidence["calibrated_quality_score"] * 0.45,
                0.0,
                100.0,
            ),
            2,
        )
        prepared.append(evidence)

    prepared.sort(
        key=lambda item: (
            item.get("calibrated_evidence_score", 0),
            item.get("relevance_score", 0),
        ),
        reverse=True,
    )
    for index, evidence in enumerate(prepared, start=1):
        evidence["rank_order"] = index

    quality = summarize_arbitration_quality(prepared, claims)
    return {
        "ranked": prepared,
        "rejected": rejected,
        "quality": quality,
    }


def summarize_arbitration_quality(
    ranked: list[dict[str, Any]],
    claims: list[dict[str, str]],
) -> dict[str, Any]:
    claim_ids = [claim["claim_id"] for claim in claims if claim.get("claim_id")]
    covered = {
        claim_id
        for evidence in ranked
        for claim_id in normalize_claim_ids(evidence.get("claim_ids"), claims)
    }
    uncovered = [claim_id for claim_id in claim_ids if claim_id not in covered]
    claim_coverage = 100.0 if not claim_ids else round((len(claim_ids) - len(uncovered)) / len(claim_ids) * 100, 2)

    unique_sources = {
        str(evidence.get("canonical_source") or canonicalize_source(evidence))
        for evidence in ranked
    }
    duplicate_count = sum(1 for evidence in ranked if evidence.get("is_near_duplicate"))

    support_weight = _stance_weight(ranked, "support")
    contradict_weight = _stance_weight(ranked, "contradict")
    neutral_weight = _stance_weight(ranked, "neutral")

    return {
        "claim_coverage": claim_coverage,
        "uncovered_claim_ids": uncovered,
        "unique_source_count": len([source for source in unique_sources if source]),
        "near_duplicate_count": duplicate_count,
        "support_weight": round(support_weight, 2),
        "contradict_weight": round(contradict_weight, 2),
        "neutral_weight": round(neutral_weight, 2),
        "has_high_quality_contradiction": contradict_weight >= 70 and contradict_weight > support_weight,
    }


def normalize_claim_ids(value: Any, claims: list[dict[str, str]]) -> list[str]:
    allowed = {claim["claim_id"] for claim in claims if claim.get("claim_id")}
    if not allowed:
        return []
    if isinstance(value, str):
        raw_items = re.split(r"[,，\s]+", value)
    elif isinstance(value, list):
        raw_items = value
    else:
        raw_items = []
    result: list[str] = []
    for item in raw_items:
        claim_id = clean_text(item, max_length=20)
        if claim_id in allowed and claim_id not in result:
            result.append(claim_id)
    return result


def canonicalize_source(evidence: dict[str, Any]) -> str:
    url = clean_text(evidence.get("source_url") or evidence.get("url"), max_length=500)
    if url:
        parsed = urlparse(url)
        host = parsed.netloc.lower().removeprefix("www.")
        path = parsed.path.rstrip("/")
        if host:
            return f"{host}{path}"
    source_name = clean_text(evidence.get("source_name"), max_length=100)
    if source_name:
        return source_name.lower()
    candidate_id = clean_text(evidence.get("candidate_id"), max_length=100)
    return candidate_id or _content_fingerprint(evidence)


def source_reliability_score(evidence: dict[str, Any], source_url: str | None) -> float:
    text = " ".join(
        clean_text(evidence.get(key), max_length=300).lower()
        for key in ("source_name", "source_url", "url", "title")
    )
    score = 0.82
    if any(hint in text for hint in AUTHORITY_HINTS):
        score += 0.15
    if any(hint in text for hint in LOW_TRUST_HINTS):
        score -= 0.18
    evidence_host = urlparse(clean_text(evidence.get("source_url"), max_length=500)).netloc.lower()
    input_host = urlparse(clean_text(source_url, max_length=500)).netloc.lower() if source_url else ""
    if evidence_host and input_host and evidence_host == input_host:
        score += 0.05
    return _clamp(score, 0.45, 1.05)


def freshness_score(evidence: dict[str, Any]) -> float:
    raw = clean_text(evidence.get("publish_time") or evidence.get("published_at"), max_length=50)
    if not raw:
        return 0.92
    parsed = _parse_date(raw)
    if parsed is None:
        return 0.88
    age_days = abs((date.today() - parsed).days)
    if age_days <= 30:
        return 1.0
    if age_days <= 365:
        return 0.94
    if age_days <= 365 * 3:
        return 0.86
    return 0.75


def extraction_confidence_score(evidence: dict[str, Any]) -> float:
    title = clean_text(evidence.get("title"), max_length=300)
    summary = clean_text(evidence.get("summary") or evidence.get("content"), max_length=2000)
    source = clean_text(evidence.get("source_name"), max_length=100)
    url = clean_text(evidence.get("source_url") or evidence.get("url"), max_length=500)

    score = 0.72
    if title:
        score += 0.08
    if len(summary) >= 80:
        score += 0.12
    elif summary:
        score += 0.06
    if source:
        score += 0.04
    if url:
        score += 0.04
    return _clamp(score, 0.55, 1.0)


def _duplicate_penalty(evidence: dict[str, Any], seen_fingerprints: list[str]) -> tuple[float, str]:
    fingerprint = _content_fingerprint(evidence)
    for previous in seen_fingerprints:
        if previous == fingerprint:
            return 0.72, fingerprint
        if SequenceMatcher(None, previous, fingerprint).ratio() >= 0.92:
            return 0.8, fingerprint
    return 1.0, fingerprint


def _content_fingerprint(evidence: dict[str, Any]) -> str:
    text = _normalize_space(
        " ".join(
            clean_text(evidence.get(key), max_length=1000)
            for key in ("title", "summary", "content")
        ).lower()
    )
    tokens = TOKEN_RE.findall(text)
    if tokens:
        return " ".join(tokens[:80])
    candidate_id = clean_text(evidence.get("candidate_id"), max_length=100)
    return hashlib.sha256(candidate_id.encode("utf-8")).hexdigest()[:16]


def _stance_weight(ranked: list[dict[str, Any]], stance: str) -> float:
    values = [
        _bounded_float(evidence.get("calibrated_evidence_score"), default=0.0)
        for evidence in ranked
        if str(evidence.get("stance") or "").lower() == stance
    ]
    return max(values) if values else 0.0


def _split_sentences(text: str) -> list[str]:
    return [part.strip() for part in CLAIM_SPLIT_RE.split(text or "") if part.strip()]


def _normalize_space(text: Any) -> str:
    return re.sub(r"\s+", " ", clean_text(text, max_length=None)).strip()


def _bounded_float(value: Any, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(number):
        return default
    return _clamp(number, 0.0, 100.0)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _parse_date(value: str) -> date | None:
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value[:19], fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None
