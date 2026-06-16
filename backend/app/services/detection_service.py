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
PROMPT_EVIDENCE_LIMIT = 5


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

    prompt_evidence = evidence_list[:PROMPT_EVIDENCE_LIMIT]
    prompt_template = get_default_prompt_content(db)

    llm_result = analyze_news_credibility(
        title=title,
        content=content,
        evidence_list=prompt_evidence,
        prompt_template=prompt_template,
    )
    is_llm_degraded = _is_llm_failure(llm_result)
    if is_llm_degraded:
        llm_result = _build_degraded_llm_result(llm_result)

    rule_result = calculate_rule_score(
        title=title,
        content=content,
        source_name=payload.source_name,
        evidence_list=prompt_evidence,
    )

    evidence_score = calculate_evidence_score(prompt_evidence)
    llm_score = _normalize_score(llm_result.get("llm_score"))
    rule_score = _normalize_score(rule_result.get("rule_score"))
    final_score = calculate_degraded_final_score(
        evidence_score,
        rule_score,
    ) if is_llm_degraded else round(
        evidence_score * 0.4 + llm_score * 0.4 + rule_score * 0.2,
        2,
    )
    risk_level = get_risk_level_from_score(final_score)
    judgement_result = build_judgement_result(risk_level)
    reason = _build_reason(llm_result, evidence_list)
    risk_points = _merge_risk_points(
        llm_result.get("risk_points"),
        rule_result.get("hit_rules"),
    )
    all_keywords = _merge_keywords(keywords, llm_result.get("keywords"))
    suggestion = clean_text(
        llm_result.get("suggestion") or "建议结合权威来源进行人工复核。",
        max_length=1000,
    )

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
            evidence_matches=[
                {
                    "knowledge_id": evidence.get("knowledge_id"),
                    "title": evidence.get("title") or "相似证据",
                    "summary": evidence.get("summary"),
                    "source_name": evidence.get("source_name"),
                    "similarity_score": evidence.get("similarity_score") or 0,
                    "rank_order": evidence.get("rank_order") or index,
                }
                for index, evidence in enumerate(evidence_list, start=1)
            ],
        ),
    )

    return {
        "detection_id": int(detection_record.id),
        "final_score": final_score,
        "evidence_score": evidence_score,
        "llm_score": llm_score,
        "rule_score": rule_score,
        "risk_level": risk_level,
        "judgement_result": judgement_result,
        "reason": reason,
        "risk_points": risk_points,
        "keywords": all_keywords,
        "evidence_list": evidence_list,
        "similar_news": _build_similar_news(evidence_list),
        "suggestion": suggestion,
        "agent_steps": build_agent_steps(web_triggered, is_llm_degraded),
        "disclaimer": DISCLAIMER,
        "web_search_triggered": web_triggered,
        "web_search_sources": web_sources_count,
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
    available_weight = 0.4 + 0.2
    score = (evidence_score * 0.4 + rule_score * 0.2) / available_weight
    return round(score, 2)


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

    return {
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


def _build_similar_news(evidence_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "title": evidence.get("title") or "",
            "risk_level": evidence.get("risk_level"),
            "similarity_score": evidence.get("similarity_score"),
        }
        for evidence in evidence_list
    ]
