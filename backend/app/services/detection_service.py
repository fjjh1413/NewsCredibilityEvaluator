import hashlib
import logging
import re
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.constants import (
    RISK_LEVEL_HIGH,
    RISK_LEVEL_RUMOR,
    RISK_LEVEL_SUSPICIOUS,
    RISK_LEVEL_TRUSTED,
)
from app.crud.detection_crud import save_detection_record
from app.schemas.detection import DetectionCreate, DetectNewsRequest
from app.services.knowledge_service import (
    KnowledgeVectorSyncError,
    build_rag_search_text,
    search_similar_knowledge,
)
from app.services.llm_service import LLM_FAILURE_ERROR, analyze_news_credibility
from app.services.prompt_service import get_default_prompt_content
from app.services.rule_score_service import calculate_rule_score
from app.services.web.bocha_client import BochaClient, BochaServiceError
from app.services.web.web_search_service import (
    merge_evidence,
    search_evidence,
    should_trigger_web_search,
)
from app.utils.high_risk import should_mark_high_risk
from app.utils.risk_level import get_risk_level_from_score
from app.utils.text_cleaner import clean_text

logger = logging.getLogger(__name__)


RAG_TOP_K = 10
PROMPT_EVIDENCE_LIMIT = 10


def build_agent_steps(web_triggered: bool, is_llm_degraded: bool) -> list[str]:
    """Build dynamic agent steps reflecting what actually happened."""
    steps = ["关键词提取完成"]
    if web_triggered:
        steps.append("知识库证据检索 + 联网搜索完成")
    else:
        steps.append("知识库证据检索完成")

    if is_llm_degraded:
        steps.append("LLM 分析暂不可用，已启用降级检测")
    else:
        steps.append("大模型可信度分析完成")

    steps.append("风险规则评分完成")
    steps.append("检测结果生成完成")
    return steps

DISCLAIMER = (
    "本系统为新闻可信度辅助评估工具，检测结果仅供参考，"
    "不能替代人工事实核查、权威媒体报道或官方通报。"
)

LLM_FAILURE_RISK_LEVEL = "模型调用失败"
LLM_DEGRADED_NOTICE = "LLM 分析暂不可用，本次结果基于 RAG 和规则评分降级生成。"

KEYWORD_HINTS = (
    "网传",
    "官方",
    "通报",
    "辟谣",
    "谣言",
    "不实",
    "虚假",
    "震惊",
    "疯传",
    "紧急",
    "扩散",
    "权威",
    "来源",
)


class DetectionServiceError(Exception):
    """Base exception for detection flow failures."""


class KnowledgeRetrievalFailedError(DetectionServiceError):
    pass


# ---------------------------------------------------------------------------
# evidence arbitration helpers
# ---------------------------------------------------------------------------

ARBITRATION_RETRY_PROMPT_ADDENDUM = """
==============================================================
重要：上一轮输出格式不正确。请严格按照以下要求重新输出完整 JSON：

1. evidence_arbitration 必须是 JSON 对象，包含 ranked_evidence 和 rejected_evidence 两个数组。
2. ranked_evidence 中的每条记录必须包含: candidate_id (字符串), relevance_score (0-100的数字), quality_score (0-100的数字), stance (只能是 support/contradict/neutral), reason (非空字符串)。
3. rejected_evidence 中的每条记录必须包含: candidate_id (字符串), reason (非空字符串)。
4. candidate_id 必须精确使用输入中提供的值（如 "kb:5", "web:1"），不得编造。
5. 每个 candidate_id 在 ranked_evidence 和 rejected_evidence 之间不得重复出现。
""".strip()


def build_neutral_candidate_order(
    candidates: list[dict[str, Any]],
    seed_material: str,
) -> list[dict[str, Any]]:
    """Generate a reproducible, source-neutral order for LLM input.

    Uses SHA-256 over ``seed_material + candidate_id`` so that identical
    news + identical candidates always produce the same order, but the order
    is not correlated with source type, similarity_score, or retrieval rank.
    """
    def _order_key(candidate: dict[str, Any]) -> str:
        cid = str(candidate.get("candidate_id", ""))
        raw = f"{seed_material}:{cid}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    return sorted(candidates, key=_order_key)


def validate_and_apply_llm_ranking(
    candidates: list[dict[str, Any]],
    arbitration: dict[str, Any],
) -> dict[str, Any]:
    """Validate LLM arbitration output and apply final ranking to candidates.

    Returns a dict with keys:

    * ``ranked`` — list of candidate dicts with final ``rank_order``,
      ``relevance_score``, ``quality_score``, ``stance``, ``arbitration_reason``.
    * ``rejected`` — list of candidate dicts with ``rejection_reason``.
    * ``errors`` — list of error message strings (empty on success).

    On any validation error, ``ranked`` and ``rejected`` will be empty and
    ``errors`` will describe what went wrong.  The caller must decide whether
    to retry or mark arbitration as failed.
    """
    ranked_raw: list[dict[str, Any]] = list(arbitration.get("ranked_evidence") or [])
    rejected_raw: list[dict[str, Any]] = list(arbitration.get("rejected_evidence") or [])

    candidate_map: dict[str, dict[str, Any]] = {
        str(item["candidate_id"]): item for item in candidates
    }
    errors: list[str] = []

    # ── 1. type checks ───────────────────────────────────────────────
    if not isinstance(ranked_raw, list):
        errors.append("ranked_evidence is not a list")
        return {"ranked": [], "rejected": [], "errors": errors}
    if not isinstance(rejected_raw, list):
        errors.append("rejected_evidence is not a list")
        return {"ranked": [], "rejected": [], "errors": errors}

    # ── 2. validate and collect ranked entries ────────────────────────
    ranked: list[dict[str, Any]] = []
    ranked_ids: set[str] = set()
    all_ids: set[str] = set()

    for entry in ranked_raw:
        if not isinstance(entry, dict):
            errors.append("ranked_evidence contains non-dict entry")
            continue

        cid = str(entry.get("candidate_id", ""))

        # candidate_id must exist in pool
        if not cid:
            errors.append("ranked_evidence entry missing candidate_id")
            continue
        if cid not in candidate_map:
            errors.append(f"unknown candidate_id in ranked_evidence: {cid}")
            continue

        # candidate_id must be unique within ranked
        if cid in ranked_ids:
            errors.append(f"duplicate candidate_id in ranked_evidence: {cid}")
            continue
        ranked_ids.add(cid)
        all_ids.add(cid)

        # relevance_score: 0-100
        rel_score = entry.get("relevance_score")
        if not isinstance(rel_score, (int, float)) or isinstance(rel_score, bool):
            errors.append(f"ranked_evidence [{cid}]: relevance_score must be a number")
            continue
        rel = float(rel_score)
        if rel < 0 or rel > 100:
            errors.append(f"ranked_evidence [{cid}]: relevance_score out of range {rel}")
            continue

        # quality_score: 0-100
        qual_score = entry.get("quality_score")
        if not isinstance(qual_score, (int, float)) or isinstance(qual_score, bool):
            errors.append(f"ranked_evidence [{cid}]: quality_score must be a number")
            continue
        qual = float(qual_score)
        if qual < 0 or qual > 100:
            errors.append(f"ranked_evidence [{cid}]: quality_score out of range {qual}")
            continue

        # stance: must be support/contradict/neutral
        stance = str(entry.get("stance", "")).strip().lower()
        if stance not in ("support", "contradict", "neutral"):
            errors.append(f"ranked_evidence [{cid}]: invalid stance {stance!r}")
            continue

        # reason: must be non-empty string
        reason = str(entry.get("reason", "")).strip()
        if not reason:
            errors.append(f"ranked_evidence [{cid}]: reason is empty")
            continue

        ranked.append({
            "cid": cid,
            "relevance_score": round(rel, 2),
            "quality_score": round(qual, 2),
            "stance": stance,
            "reason": reason[:1000],
        })

    # ── 3. validate rejected entries ─────────────────────────────────
    rejected: list[dict[str, Any]] = []

    for entry in rejected_raw:
        if not isinstance(entry, dict):
            errors.append("rejected_evidence contains non-dict entry")
            continue

        cid = str(entry.get("candidate_id", ""))

        if not cid:
            errors.append("rejected_evidence entry missing candidate_id")
            continue
        if cid not in candidate_map:
            errors.append(f"unknown candidate_id in rejected_evidence: {cid}")
            continue

        # must not appear in ranked
        if cid in all_ids:
            errors.append(f"candidate_id in both ranked and rejected: {cid}")
            continue
        all_ids.add(cid)

        reason = str(entry.get("reason", "")).strip()
        if not reason:
            errors.append(f"rejected_evidence [{cid}]: reason is empty")
            continue

        rejected.append({
            "cid": cid,
            "reason": reason[:1000],
        })

    # ── 4. if any errors, bail out ────────────────────────────────────
    if errors:
        return {"ranked": [], "rejected": [], "errors": errors}

    # ── 5. apply final rank_order (array index = final rank) ──────────
    ranked_candidates: list[dict[str, Any]] = []
    rejected_candidates: list[dict[str, Any]] = []

    for final_rank, decision in enumerate(ranked, start=1):
        candidate = dict(candidate_map[decision["cid"]])
        candidate["rank_order"] = final_rank
        candidate["relevance_score"] = decision["relevance_score"]
        candidate["quality_score"] = decision["quality_score"]
        candidate["stance"] = decision["stance"]
        candidate["arbitration_reason"] = decision["reason"]
        ranked_candidates.append(candidate)

    for decision in rejected:
        candidate = dict(candidate_map[decision["cid"]])
        candidate["rejection_reason"] = decision["reason"]
        rejected_candidates.append(candidate)

    return {
        "ranked": ranked_candidates,
        "rejected": rejected_candidates,
        "errors": [],
    }


def detect_news_credibility(
    db: Session,
    payload: DetectNewsRequest,
    current_user: Any | None = None,
) -> dict[str, Any]:
    title = clean_text(payload.title, max_length=255)
    content = clean_text(payload.content, max_length=12000)
    if not title or not content:
        raise DetectionServiceError("新闻标题和正文不能为空")

    keywords = extract_keywords(title=title, content=content)
    evidence_results = _search_top10_evidence(db=db, title=title, content=content)
    evidence_list = _format_evidence_list(evidence_results)

    # ── web search (conditional) ──
    web_triggered = False
    web_sources_count = 0
    settings = get_settings()
    web_search_enabled = getattr(settings, "web_search_enabled", True)
    if web_search_enabled and should_trigger_web_search(
        evidence_list,
        payload.enable_web_search,
    ):
        try:
            bocha_client = BochaClient(
                api_key=settings.bocha_api_key,
                timeout=settings.web_search_timeout_seconds,
            )
            web_items = search_evidence(
                client=bocha_client,
                title=title,
                keywords=keywords,
                count=settings.web_search_count,
                freshness=settings.web_search_freshness,
            )
            if web_items:
                evidence_list = merge_evidence(evidence_list, web_items)
                web_triggered = True
                web_sources_count = sum(
                    1 for e in evidence_list if e.get("source_type") == "web_search"
                )
        except BochaServiceError:
            logger.warning("Bocha web search failed, continuing with RAG-only evidence")

    # ── ensure every candidate has a candidate_id ──────────────────────
    _ensure_candidate_ids(evidence_list)

    # ── build neutral input order for LLM (source-neutral, reproducible) ──
    seed = f"{title}\n{content}"
    neutral_evidence = build_neutral_candidate_order(evidence_list, seed)
    prompt_evidence = neutral_evidence[:PROMPT_EVIDENCE_LIMIT]

    prompt_template = get_default_prompt_content(db)

    llm_result = analyze_news_credibility(
        title=title,
        content=content,
        evidence_list=prompt_evidence,
        prompt_template=prompt_template,
    )

    # ── evidence arbitration ─────────────────────────────────────────
    ranking_result: dict[str, Any] | None = None
    arbitration_status = "unavailable"

    if not _is_llm_failure(llm_result):
        arbitration = llm_result.get("evidence_arbitration")
        if arbitration is None:
            ranking_result = {
                "ranked": [],
                "rejected": [],
                "errors": ["missing evidence_arbitration"],
            }
        else:
            ranking_result = validate_and_apply_llm_ranking(evidence_list, arbitration)

        if ranking_result["errors"]:
            # ── retry once with fix prompt ──
            logger.warning(
                "LLM arbitration validation failed: %s. Retrying once.",
                "; ".join(ranking_result["errors"]),
            )
            retry_template = prompt_template + "\n\n" + ARBITRATION_RETRY_PROMPT_ADDENDUM
            retry_result = analyze_news_credibility(
                title=title,
                content=content,
                evidence_list=prompt_evidence,
                prompt_template=retry_template,
            )
            retry_arbitration = retry_result.get("evidence_arbitration")
            if retry_arbitration is not None:
                ranking_result = validate_and_apply_llm_ranking(
                    evidence_list, retry_arbitration
                )
                if not ranking_result["errors"]:
                    arbitration_status = "ok"
                    # The retry's scores and evidence quality were produced
                    # from the same arbitration decision, so keep them together.
                    llm_result = retry_result
                else:
                    logger.error(
                        "LLM arbitration retry also failed: %s",
                        "; ".join(ranking_result["errors"]),
                    )
            else:
                logger.error("LLM arbitration retry: no evidence_arbitration in response")
        else:
            arbitration_status = "ok"

    is_llm_degraded = _is_llm_failure(llm_result)
    if is_llm_degraded:
        llm_result = _build_degraded_llm_result(llm_result)

    # ── determine effective evidence ──────────────────────────────────
    if ranking_result is not None and not ranking_result["errors"]:
        effective_evidence = ranking_result["ranked"]
        excluded_evidence = ranking_result["rejected"]
    else:
        # Unarbitrated candidates must not affect scoring.
        effective_evidence = []
        excluded_evidence = []

    knowledge_has_relevant_match = any(
        evidence.get("source_type") == "knowledge_base"
        for evidence in effective_evidence
    )
    web_has_relevant_match = any(
        evidence.get("source_type") == "web_search"
        for evidence in effective_evidence
    )

    rule_result = calculate_rule_score(
        title=title,
        content=content,
        source_name=payload.source_name,
        evidence_list=effective_evidence,
    )

    evidence_score = calculate_evidence_score(effective_evidence)
    llm_score = _normalize_score(llm_result.get("llm_score"))
    rule_score = _normalize_score(rule_result.get("rule_score"))

    # ── evidence quality (LLM-evaluated) ──
    raw_evidence_quality = llm_result.get("evidence_quality") or {}
    evidence_quality = (
        raw_evidence_quality if arbitration_status == "ok" else None
    )
    eq_score = _normalize_score(raw_evidence_quality.get("score"))

    if is_llm_degraded:
        # Without an LLM arbitration decision, retrieval candidates are not
        # trusted as scoring evidence.  Fall back to the deterministic rules.
        final_score = rule_score
    elif not effective_evidence:
        final_score = round(llm_score * 0.6 + rule_score * 0.4, 2)
    else:
        final_score = round(
            llm_score * 0.5 + eq_score * 0.3 + rule_score * 0.2,
            2,
        )
    risk_level = get_risk_level_from_score(final_score)
    judgement_result = build_judgement_result(risk_level)
    reason = _build_reason(llm_result, effective_evidence)
    risk_points = _merge_risk_points(
        llm_result.get("risk_points"),
        rule_result.get("hit_rules"),
    )
    all_keywords = _merge_keywords(keywords, llm_result.get("keywords"))
    suggestion = clean_text(
        llm_result.get("suggestion") or "建议结合权威来源进行人工复核。",
        max_length=1000,
    )
    similar_news = _build_similar_news_from_llm(
        candidates=evidence_list,
        effective_evidence=effective_evidence,
        llm_similar_news=llm_result.get("similar_news"),
    )
    analysis_payload = {
        "publish_time": payload.publish_time,
        "source_name": payload.source_name,
        "source_url": payload.source_url,
        "candidate_evidence_list": evidence_list,
        "excluded_evidence": excluded_evidence,
        "similar_news": similar_news,
        "evidence_quality": evidence_quality,
        "arbitration_status": arbitration_status,
        "knowledge_has_relevant_match": knowledge_has_relevant_match,
        "web_has_relevant_match": web_has_relevant_match,
    }

    detection_record = save_detection_record(
        db,
        DetectionCreate(
            user_id=getattr(current_user, "id", None),
            input_title=title,
            input_content=content,
            category=payload.category,
            keywords=",".join(all_keywords),
            final_score=final_score,
            evidence_score=evidence_score,
            llm_score=llm_score,
            rule_score=rule_score,
            risk_level=risk_level,
            judgement_result=judgement_result,
            reason=reason,
            risk_points=risk_points,
            suggestion=suggestion,
            is_high_risk=should_mark_high_risk(final_score, risk_level),
            report_url=None,
            analysis_payload=analysis_payload,
            evidence_matches=[
                {
                    "knowledge_id": evidence.get("knowledge_id"),
                    "title": evidence.get("title") or "相似证据",
                    "summary": evidence.get("summary"),
                    "source_name": evidence.get("source_name"),
                    "similarity_score": evidence.get("similarity_score") or 0,
                    "rank_order": evidence.get("rank_order") or index,
                }
                for index, evidence in enumerate(effective_evidence, start=1)
            ],
        ),
    )

    return {
        "detection_id": int(detection_record.id),
        "created_at": getattr(detection_record, "created_at", None),
        "publish_time": payload.publish_time,
        "source_name": payload.source_name,
        "source_url": payload.source_url,
        "final_score": final_score,
        "evidence_score": evidence_score,
        "llm_score": llm_score,
        "rule_score": rule_score,
        "risk_level": risk_level,
        "judgement_result": judgement_result,
        "reason": reason,
        "risk_points": risk_points,
        "keywords": all_keywords,
        "candidate_evidence_list": evidence_list,
        "evidence_list": effective_evidence,
        "excluded_evidence": excluded_evidence,
        "similar_news": similar_news,
        "suggestion": suggestion,
        "agent_steps": build_agent_steps(web_triggered, is_llm_degraded),
        "disclaimer": DISCLAIMER,
        "web_search_triggered": web_triggered,
        "web_search_sources": web_sources_count,
        "evidence_quality": evidence_quality,
        "arbitration_status": arbitration_status,
        "knowledge_has_relevant_match": knowledge_has_relevant_match,
        "web_has_relevant_match": web_has_relevant_match,
    }


def extract_keywords(title: str, content: str, max_count: int = 8) -> list[str]:
    text = f"{title}\n{content}"
    keywords: list[str] = []

    for word in KEYWORD_HINTS:
        if word in text and word not in keywords:
            keywords.append(word)

    for token in re.findall(r"[A-Za-z0-9_]{2,}|[\u4e00-\u9fff]{2,6}", text):
        if token not in keywords:
            keywords.append(token)
        if len(keywords) >= max_count:
            break

    return keywords[:max_count]


def calculate_evidence_score(evidence_list: list[dict[str, Any]]) -> float:
    scores: list[float] = []
    for evidence in evidence_list[:PROMPT_EVIDENCE_LIMIT]:
        score = evidence.get("similarity_score")
        if score is None:
            continue
        scores.append(_similarity_to_percent(score))

    if not scores:
        return 0.0
    return round(sum(scores) / len(scores), 2)


def build_final_risk_level(final_score: float) -> str:
    return get_risk_level_from_score(final_score)


def calculate_degraded_final_score(evidence_score: float, rule_score: float) -> float:
    """Degraded-mode score when LLM is unavailable.

    evidence_score_rag takes over the 0.3 evidence_quality weight and
    rule_score keeps its 0.2, normalised to 1.0:  0.3 + 0.2 = 0.5.
    """
    return round(evidence_score * 0.6 + rule_score * 0.4, 2)


def build_judgement_result(risk_level: str) -> str:
    mapping = {
        RISK_LEVEL_TRUSTED: "该新闻整体可信度较高",
        RISK_LEVEL_SUSPICIOUS: "该新闻存在一定疑点，建议进一步核查",
        RISK_LEVEL_RUMOR: "该新闻疑似存在谣言风险",
        RISK_LEVEL_HIGH: "该新闻存在较高谣言风险",
    }
    return mapping.get(risk_level, "该新闻需要进一步核查")


def _search_top10_evidence(
    db: Session,
    title: str,
    content: str,
) -> list[dict[str, Any]]:
    query_text = build_rag_search_text(title=title, content=content)
    try:
        return search_similar_knowledge(
            db,
            query_text=query_text,
            top_k=RAG_TOP_K,
        )
    except KnowledgeVectorSyncError as exc:
        raise KnowledgeRetrievalFailedError("知识库证据检索失败") from exc


def _format_evidence_list(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    evidence_list: list[dict[str, Any]] = []
    for index, result in enumerate(results, start=1):
        metadata = result.get("metadata") or {}
        evidence_list.append(
            {
                "knowledge_id": metadata.get("knowledge_id"),
                "title": clean_text(metadata.get("title"), max_length=255),
                "summary": clean_text(metadata.get("summary"), max_length=1000),
                "category": clean_text(metadata.get("category"), max_length=50),
                "truth_label": clean_text(metadata.get("truth_label"), max_length=30),
                "source_name": clean_text(metadata.get("source_name"), max_length=100),
                "risk_level": clean_text(metadata.get("risk_level"), max_length=30),
                "similarity_score": result.get("similarity_score"),
                "rank_order": index,
                "source_type": "knowledge_base",
                "source_label": "📚 知识库",
            }
        )
    return evidence_list


def _is_llm_failure(llm_result: dict[str, Any]) -> bool:
    risk_level = clean_text(llm_result.get("risk_level"), max_length=50)
    if risk_level == LLM_FAILURE_RISK_LEVEL:
        return True

    error_text = clean_text(llm_result.get("error"), max_length=100)
    if error_text == LLM_FAILURE_ERROR:
        return True

    has_zero_score = _normalize_score(llm_result.get("llm_score")) == 0
    reason = clean_text(llm_result.get("reason"), max_length=1000)
    if has_zero_score and LLM_FAILURE_ERROR in reason:
        return True

    risk_points = llm_result.get("risk_points")
    if isinstance(risk_points, list):
        return has_zero_score and any(
            LLM_FAILURE_ERROR in clean_text(risk_point, max_length=200)
            for risk_point in risk_points
        )
    return has_zero_score and LLM_FAILURE_ERROR in clean_text(risk_points, max_length=1000)


def _build_degraded_llm_result(llm_result: dict[str, Any]) -> dict[str, Any]:
    reason = clean_text(llm_result.get("reason"), max_length=1600)
    suggestion = clean_text(llm_result.get("suggestion"), max_length=800)
    risk_points = llm_result.get("risk_points")
    if not isinstance(risk_points, list):
        risk_points = [risk_points] if risk_points else []

    degraded = {
        **llm_result,
        "llm_score": 0,
        "risk_level": RISK_LEVEL_SUSPICIOUS,
        "reason": clean_text(
            f"{LLM_DEGRADED_NOTICE}{reason}" if reason else LLM_DEGRADED_NOTICE,
            max_length=2000,
        ),
        "risk_points": [
            item
            for item in [LLM_DEGRADED_NOTICE, *risk_points]
            if clean_text(item, max_length=200)
        ],
        "keywords": llm_result.get("keywords") if isinstance(llm_result.get("keywords"), list) else [],
        "suggestion": clean_text(
            f"{LLM_DEGRADED_NOTICE}{suggestion}" if suggestion else (
                f"{LLM_DEGRADED_NOTICE}建议结合检索证据、规则命中情况和权威来源进行人工复核。"
            ),
            max_length=1000,
        ),
        "error": llm_result.get("error") or LLM_FAILURE_ERROR,
    }
    # No LLM evaluation → evidence_quality is not available.
    degraded["evidence_quality"] = None
    return degraded


def _normalize_score(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        score = 0.0
    return round(max(0.0, min(100.0, score)), 2)


def _similarity_to_percent(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    if score <= 1:
        score *= 100
    return round(max(0.0, min(100.0, score)), 2)


def _build_reason(llm_result: dict[str, Any], evidence_list: list[dict[str, Any]]) -> str:
    reason = clean_text(llm_result.get("reason"), max_length=2000)
    if not evidence_list:
        evidence_note = "知识库未检索到相关证据，当前分析存在证据不足。"
        if reason:
            return f"{reason} {evidence_note}"
        return evidence_note
    return reason or "模型未提供详细判断理由。"


def _merge_risk_points(
    llm_risk_points: Any,
    hit_rules: Any,
) -> list[str]:
    risk_points: list[str] = []
    if isinstance(llm_risk_points, list):
        for item in llm_risk_points:
            text = clean_text(item, max_length=200)
            if text and text not in risk_points:
                risk_points.append(text)

    if isinstance(hit_rules, list):
        for rule in hit_rules:
            if not isinstance(rule, dict):
                continue
            text = clean_text(rule.get("rule_name"), max_length=100)
            if text and text not in risk_points:
                risk_points.append(text)
    return risk_points


def _merge_keywords(
    extracted_keywords: list[str],
    llm_keywords: Any,
) -> list[str]:
    keywords: list[str] = []
    for item in extracted_keywords:
        text = clean_text(item, max_length=50)
        if text and text not in keywords:
            keywords.append(text)

    if isinstance(llm_keywords, list):
        for item in llm_keywords:
            text = clean_text(item, max_length=50)
            if text and text not in keywords:
                keywords.append(text)
    return keywords[:12]


def _ensure_candidate_ids(evidence_list: list[dict[str, Any]]) -> None:
    """Mutate *evidence_list* in-place to give every item a ``candidate_id``.

    RAG items use ``kb:{knowledge_id}`` (or ``kb:rag:{idx}`` fallback).
    Web items already have candidate_id from merge_evidence.
    Items that already have a candidate_id are left unchanged.
    """
    candidate_ids: set[str] = {str(e["candidate_id"]) for e in evidence_list if e.get("candidate_id")}
    for idx, item in enumerate(evidence_list, start=1):
        if item.get("candidate_id"):
            continue
        kid = item.get("knowledge_id")
        base = f"kb:{int(kid)}" if isinstance(kid, int) and not isinstance(kid, bool) and kid > 0 else f"kb:rag:{idx}"
        cid = base
        suffix = 2
        while cid in candidate_ids:
            cid = f"{base}:{suffix}"
            suffix += 1
        candidate_ids.add(cid)
        item["candidate_id"] = cid


def _build_similar_news_from_llm(
    candidates: list[dict[str, Any]],
    effective_evidence: list[dict[str, Any]],
    llm_similar_news: Any,
) -> list[dict[str, Any]]:
    """Build similar news only from validated LLM candidate references."""
    if not isinstance(llm_similar_news, list):
        return []

    candidate_map = {
        str(candidate.get("candidate_id")): candidate
        for candidate in candidates
        if candidate.get("candidate_id")
    }
    effective_map = {
        str(candidate.get("candidate_id")): candidate
        for candidate in effective_evidence
        if candidate.get("candidate_id")
    }
    allowed_risk_levels = {
        RISK_LEVEL_TRUSTED,
        RISK_LEVEL_SUSPICIOUS,
        RISK_LEVEL_RUMOR,
        RISK_LEVEL_HIGH,
    }
    similar_news: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for item in llm_similar_news:
        if not isinstance(item, dict):
            continue
        candidate_id = clean_text(item.get("candidate_id"), max_length=100)
        if (
            not candidate_id
            or candidate_id in seen_ids
            or candidate_id not in candidate_map
            or candidate_id not in effective_map
        ):
            continue

        risk_level = clean_text(item.get("risk_level"), max_length=30)
        relevance_reason = clean_text(
            item.get("relevance_reason") or item.get("reason"),
            max_length=1000,
        )
        if risk_level not in allowed_risk_levels or not relevance_reason:
            continue

        evidence = effective_map[candidate_id]
        similar_news.append(
            {
                "title": evidence.get("title") or "",
                "source_name": evidence.get("source_name"),
                "source_url": evidence.get("source_url"),
                "publish_time": evidence.get("publish_time"),
                "source_type": evidence.get("source_type"),
                "risk_level": risk_level,
                "similarity_score": evidence.get("similarity_score"),
                "candidate_id": candidate_id,
                "rank_order": len(similar_news) + 1,
                "relevance_score": evidence.get("relevance_score"),
                "quality_score": evidence.get("quality_score"),
                "stance": evidence.get("stance"),
                "relevance_reason": relevance_reason,
                "arbitration_reason": evidence.get("arbitration_reason"),
            }
        )
        seen_ids.add(candidate_id)

    return similar_news
