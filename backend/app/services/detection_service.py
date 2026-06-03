import re
from typing import Any

from sqlalchemy.orm import Session

from app.crud.detection_crud import save_detection_record
from app.schemas.detection import DetectionCreate, DetectNewsRequest
from app.services.knowledge_service import (
    KnowledgeVectorSyncError,
    build_rag_search_text,
    search_similar_knowledge,
)
from app.services.llm_service import analyze_news_credibility
from app.services.rule_score_service import calculate_rule_score
from app.utils.text_cleaner import clean_text


RAG_TOP_K = 10
PROMPT_EVIDENCE_LIMIT = 5

AGENT_STEPS = [
    "关键词提取完成",
    "知识库证据检索完成",
    "大模型可信度分析完成",
    "风险规则评分完成",
    "检测结果生成完成",
]

DISCLAIMER = (
    "本系统为新闻可信度辅助评估工具，检测结果仅供参考，"
    "不能替代人工事实核查、权威媒体报道或官方通报。"
)

LLM_FAILURE_RISK_LEVEL = "模型调用失败"

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


class LLMAnalysisFailedError(DetectionServiceError):
    pass


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
    prompt_evidence = evidence_list[:PROMPT_EVIDENCE_LIMIT]

    llm_result = analyze_news_credibility(
        title=title,
        content=content,
        evidence_list=prompt_evidence,
        prompt_template="",
    )
    if _is_llm_failure(llm_result):
        raise LLMAnalysisFailedError(clean_text(llm_result.get("reason"), max_length=1000))

    rule_result = calculate_rule_score(
        title=title,
        content=content,
        source_name=payload.source_name,
        evidence_list=prompt_evidence,
    )

    evidence_score = calculate_evidence_score(prompt_evidence)
    llm_score = _normalize_score(llm_result.get("llm_score"))
    rule_score = _normalize_score(rule_result.get("rule_score"))
    final_score = round(
        evidence_score * 0.4 + llm_score * 0.4 + rule_score * 0.2,
        2,
    )
    risk_level = build_final_risk_level(final_score)
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
            is_high_risk=final_score < 40,
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
        "agent_steps": AGENT_STEPS,
        "disclaimer": DISCLAIMER,
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
    if final_score >= 80:
        return "可信新闻"
    if final_score >= 60:
        return "存疑信息"
    if final_score >= 40:
        return "疑似谣言"
    return "高风险谣言"


def build_judgement_result(risk_level: str) -> str:
    mapping = {
        "可信新闻": "该新闻整体可信度较高",
        "存疑信息": "该新闻存在一定疑点，建议进一步核查",
        "疑似谣言": "该新闻疑似存在谣言风险",
        "高风险谣言": "该新闻存在较高谣言风险",
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
    return risk_level == LLM_FAILURE_RISK_LEVEL


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
