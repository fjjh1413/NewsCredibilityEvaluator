import hashlib
import logging
import math
import re
import time
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.assessment import ASSESSMENT_COMPLETED, UNKNOWN_RISK_LEVEL, assessment_outcome
from app.core.constants import (
    RISK_LEVEL_HIGH,
    RISK_LEVEL_RUMOR,
    RISK_LEVEL_SUSPICIOUS,
    RISK_LEVEL_TRUSTED,
)
from app.core.tracing import add_span_attributes, trace_span
from app.crud.detection_crud import save_detection_record
from app.schemas.detection import DetectionCreate, DetectNewsRequest
from app.services.knowledge_service import (
    KnowledgeVectorSyncError,
    build_rag_search_text,
    search_similar_knowledge,
)
from app.services.rag.contextual_compression import add_supporting_spans_to_results
from app.services.rag.fusion import fuse_ranked_parent_results
from app.services.rag.query_planner import build_claim_aware_queries
from app.services.evidence_arbitration_quality import (
    apply_arbitration_quality_controls,
    extract_core_claims,
)
from app.services.llm_service import (
    ANALYSIS_CONTRACT_VERSION,
    LLM_FAILURE_ERROR,
    analyze_evidence_arbitration,
    analyze_news_credibility,
)
from app.services.agent_trace import build_agent_trace
from app.services.agent_state_graph import END, GraphExecutionJournal
from app.services.detection_agent_graph import (
    DETECTION_NODE_IDS,
    DetectionAgentState,
    build_detection_agent_graph,
)
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


def _record_stage_latency(
    stage_latency_ms: dict[str, float],
    stage_name: str,
    started_at: float,
) -> None:
    stage_latency_ms[stage_name] = round((time.perf_counter() - started_at) * 1000, 2)


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
LLM_DEGRADED_NOTICE = "LLM 分析暂不可用，本次无法判断；规则分仅供诊断，不构成可信度结论。"

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
    if not isinstance(arbitration, dict):
        return {"ranked": [], "rejected": [], "errors": ["evidence_arbitration is not an object"]}
    ranked_raw = arbitration.get("ranked_evidence")
    rejected_raw = arbitration.get("rejected_evidence")

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
        if not math.isfinite(rel) or rel < 0 or rel > 100:
            errors.append(f"ranked_evidence [{cid}]: relevance_score out of range {rel}")
            continue

        # quality_score: 0-100
        qual_score = entry.get("quality_score")
        if not isinstance(qual_score, (int, float)) or isinstance(qual_score, bool):
            errors.append(f"ranked_evidence [{cid}]: quality_score must be a number")
            continue
        qual = float(qual_score)
        if not math.isfinite(qual) or qual < 0 or qual > 100:
            errors.append(f"ranked_evidence [{cid}]: quality_score out of range {qual}")
            continue

        # stance: must be support/contradict/neutral
        stance = str(entry.get("stance", "")).strip().lower()
        if stance not in ("support", "contradict", "neutral"):
            errors.append(f"ranked_evidence [{cid}]: invalid stance {stance!r}")
            continue

        # reason: must be non-empty string
        raw_reason = entry.get("reason")
        reason = raw_reason.strip() if isinstance(raw_reason, str) else ""
        if not reason:
            errors.append(f"ranked_evidence [{cid}]: reason is empty")
            continue

        claim_ids = _normalize_arbitration_claim_ids(entry.get("claim_ids"))

        ranked.append({
            "cid": cid,
            "relevance_score": round(rel, 2),
            "quality_score": round(qual, 2),
            "stance": stance,
            "claim_ids": claim_ids,
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

        raw_reason = entry.get("reason")
        reason = raw_reason.strip() if isinstance(raw_reason, str) else ""
        if not reason:
            errors.append(f"rejected_evidence [{cid}]: reason is empty")
            continue

        rejected.append({
            "cid": cid,
            "reason": reason[:1000],
        })

    missing_ids = set(candidate_map) - all_ids
    if missing_ids:
        errors.append(
            "candidate_id missing from arbitration: "
            + ", ".join(sorted(missing_ids))
        )

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
        candidate["claim_ids"] = decision["claim_ids"]
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


def _node_prepare_input(state: DetectionAgentState) -> None:
    state.title = clean_text(state.payload.title, max_length=255)
    state.content = clean_text(state.payload.content, max_length=12000)
    if not state.title or not state.content:
        raise DetectionServiceError("新闻标题和正文不能为空")


def _node_extract_claims(state: DetectionAgentState) -> None:
    started_at = time.perf_counter()
    with trace_span(
        "detection.extract_keywords",
        {"news.category": state.payload.category or ""},
    ) as span:
        state.keywords = extract_keywords(title=state.title, content=state.content)
        state.core_claims = extract_core_claims(state.title, state.content)
        add_span_attributes(
            span,
            {
                "keyword.count": len(state.keywords),
                "claim.count": len(state.core_claims),
            },
        )
    _record_stage_latency(state.stage_latency_ms, "extract_keywords", started_at)


def _node_retrieve_local_evidence(state: DetectionAgentState) -> None:
    started_at = time.perf_counter()
    with trace_span("detection.rag_search", {"rag.top_k": RAG_TOP_K}) as span:
        evidence_results = _search_top10_evidence(
            db=state.db,
            title=state.title,
            content=state.content,
            claims=state.core_claims,
        )
        state.evidence_list = _format_evidence_list(evidence_results)
        state.rag_query_count = max(
            [
                int(evidence.get("retrieval_query_count") or 0)
                for evidence in state.evidence_list
            ]
            or [1]
        )
        add_span_attributes(
            span,
            {
                "rag.match_count": len(state.evidence_list),
                "rag.query_count": state.rag_query_count,
            },
        )
    _record_stage_latency(state.stage_latency_ms, "rag_search", started_at)


def _node_route_web_search(state: DetectionAgentState) -> None:
    state.settings = get_settings()
    state.web_search_enabled = getattr(state.settings, "web_search_enabled", True)
    state.should_search_web = (
        state.web_search_enabled
        and should_trigger_web_search(
            state.evidence_list,
            state.payload.enable_web_search,
        )
    )
    if not state.should_search_web:
        started_at = time.perf_counter()
        with trace_span(
            "detection.web_search",
            {
                "web_search.enabled": state.web_search_enabled,
                "web_search.requested": bool(state.payload.enable_web_search),
                "web_search.triggered": False,
            },
        ):
            pass
        _record_stage_latency(state.stage_latency_ms, "web_search", started_at)


def _node_search_web_evidence(state: DetectionAgentState) -> None:
    started_at = time.perf_counter()
    with trace_span(
        "detection.web_search",
        {
            "web_search.enabled": state.web_search_enabled,
            "web_search.requested": bool(state.payload.enable_web_search),
            "web_search.triggered": True,
        },
    ) as span:
        state.web_search_attempted = True
        try:
            bocha_client = BochaClient(
                api_key=state.settings.bocha_api_key,
                timeout=state.settings.web_search_timeout_seconds,
            )
            web_items = search_evidence(
                client=bocha_client,
                title=state.title,
                keywords=state.keywords,
                count=state.settings.web_search_count,
                freshness=state.settings.web_search_freshness,
            )
            add_span_attributes(span, {"web_search.result_count": len(web_items)})
            if web_items:
                state.evidence_list = merge_evidence(state.evidence_list, web_items)
                state.web_triggered = True
                state.web_sources_count = sum(
                    1
                    for evidence in state.evidence_list
                    if evidence.get("source_type") == "web_search"
                )
        except BochaServiceError:
            add_span_attributes(span, {"web_search.failed": True})
            logger.warning("Bocha web search failed, continuing with RAG-only evidence")
    _record_stage_latency(state.stage_latency_ms, "web_search", started_at)


def _node_prepare_model_input(state: DetectionAgentState) -> None:
    _ensure_candidate_ids(state.evidence_list)
    seed = f"{state.title}\n{state.content}"
    neutral_evidence = build_neutral_candidate_order(state.evidence_list, seed)
    state.prompt_evidence = neutral_evidence[:PROMPT_EVIDENCE_LIMIT]

    started_at = time.perf_counter()
    with trace_span("detection.prompt_template") as span:
        state.prompt_template = get_default_prompt_content(state.db)
        add_span_attributes(
            span,
            {"prompt_template.loaded": bool(state.prompt_template)},
        )
    _record_stage_latency(state.stage_latency_ms, "prompt_template", started_at)


def _node_analyze_with_model(state: DetectionAgentState) -> None:
    started_at = time.perf_counter()
    with trace_span(
        "detection.llm_analysis",
        {"evidence.prompt_count": len(state.prompt_evidence)},
    ) as span:
        state.llm_result = analyze_news_credibility(
            title=state.title,
            content=state.content,
            evidence_list=state.prompt_evidence,
            prompt_template=state.prompt_template,
            claims=state.core_claims,
        )
        add_span_attributes(
            span,
            {"llm.degraded": _is_llm_failure(state.llm_result)},
        )
    _record_stage_latency(state.stage_latency_ms, "llm_analysis", started_at)


def _node_arbitrate_evidence(state: DetectionAgentState) -> None:
    state.should_retry_arbitration = False
    if _is_llm_failure(state.llm_result):
        state.arbitration_status = "invalid_response" if state.llm_result.get("analysis_status") == "invalid_response" else "provider_error"
        state.arbitration_error = state.llm_result.get("analysis_error") or "模型服务调用失败，未执行证据仲裁"
        return
    if not state.evidence_list:
        state.ranking_result = {"ranked": [], "rejected": [], "errors": []}
        state.arbitration_status = "no_evidence"
        state.quality_status = "no_evidence"
        return

    state.arbitration_attempts = 1
    arbitration = state.llm_result.get("evidence_arbitration")
    if arbitration is None:
        state.ranking_result = {
            "ranked": [],
            "rejected": [],
            "errors": ["missing evidence_arbitration"],
        }
    else:
        state.ranking_result = validate_and_apply_llm_ranking(
            state.evidence_list,
            arbitration,
        )

    quality_errors = _validate_evidence_quality(
        state.llm_result.get("evidence_quality")
    )
    first_errors = [*state.ranking_result["errors"], *quality_errors]
    if first_errors:
        logger.warning(
            "LLM evidence contract validation failed: %s. "
            "Retrying focused arbitration once.",
            "; ".join(first_errors),
        )
        state.should_retry_arbitration = True
        return

    state.arbitration_status = "ok"
    state.quality_status = "ok"


def _node_retry_arbitration(state: DetectionAgentState) -> None:
    state.arbitration_attempts = 2
    started_at = time.perf_counter()
    with trace_span(
        "detection.evidence_arbitration_retry",
        {"evidence.prompt_count": len(state.prompt_evidence)},
    ):
        retry_result = analyze_evidence_arbitration(
            title=state.title,
            content=state.content,
            evidence_list=state.prompt_evidence,
            claims=state.core_claims,
        )
    _record_stage_latency(
        state.stage_latency_ms,
        "evidence_arbitration_retry",
        started_at,
    )

    retry_arbitration = retry_result.get("evidence_arbitration")
    retry_ranking = (
        validate_and_apply_llm_ranking(state.evidence_list, retry_arbitration)
        if isinstance(retry_arbitration, dict)
        else {
            "ranked": [],
            "rejected": [],
            "errors": ["missing evidence_arbitration"],
        }
    )
    retry_quality = retry_result.get("evidence_quality")
    retry_quality_errors = _validate_evidence_quality(retry_quality)

    if not retry_ranking["errors"] and not retry_quality_errors:
        state.ranking_result = retry_ranking
        state.llm_result = {
            **state.llm_result,
            "evidence_arbitration": retry_arbitration,
            "evidence_quality": retry_quality,
            "similar_news": retry_result.get("similar_news") or [],
        }
        state.arbitration_status = "ok"
        state.quality_status = "ok"
        return

    retry_errors = [*retry_ranking["errors"], *retry_quality_errors]
    provider_error = clean_text(retry_result.get("error"), max_length=500)
    if provider_error:
        logger.error("Focused arbitration provider error: %s", provider_error)
        retry_errors.append("focused arbitration provider request failed")
    state.arbitration_status = "retry_exhausted"
    state.arbitration_error = "; ".join(retry_errors)[:1000]
    state.ranking_result = retry_ranking
    logger.error(
        "Focused evidence arbitration retry failed: %s",
        state.arbitration_error,
    )


def _node_score_risk(state: DetectionAgentState) -> None:
    if state.ranking_result is not None and not state.ranking_result["errors"]:
        quality_control = apply_arbitration_quality_controls(
            ranked=state.ranking_result["ranked"],
            rejected=state.ranking_result["rejected"],
            claims=state.core_claims,
            source_url=state.payload.source_url,
        )
        state.ranking_result = {
            **state.ranking_result,
            "ranked": quality_control["ranked"],
            "rejected": quality_control["rejected"],
            "quality": quality_control["quality"],
        }
        state.arbitration_quality_summary = quality_control["quality"]

    state.is_llm_degraded = _is_llm_failure(state.llm_result)
    if state.is_llm_degraded:
        state.llm_result = _build_degraded_llm_result(state.llm_result)

    if state.ranking_result is not None and not state.ranking_result["errors"]:
        state.effective_evidence = state.ranking_result["ranked"]
        state.excluded_evidence = state.ranking_result["rejected"]
    else:
        # Unarbitrated candidates must not affect scoring.
        state.effective_evidence = []
        state.excluded_evidence = []

    state.knowledge_has_relevant_match = any(
        evidence.get("source_type") == "knowledge_base"
        for evidence in state.effective_evidence
    )
    state.web_has_relevant_match = any(
        evidence.get("source_type") == "web_search"
        for evidence in state.effective_evidence
    )

    started_at = time.perf_counter()
    with trace_span(
        "detection.rule_score",
        {"evidence.effective_count": len(state.effective_evidence)},
    ) as span:
        rule_result = calculate_rule_score(
            title=state.title,
            content=state.content,
            source_name=state.payload.source_name,
            evidence_list=state.effective_evidence,
        )
        add_span_attributes(
            span,
            {"rule_score": _normalize_score(rule_result.get("rule_score"))},
        )
    _record_stage_latency(state.stage_latency_ms, "rule_score", started_at)

    state.evidence_score = calculate_evidence_score(state.effective_evidence)
    state.llm_score = _normalize_score(state.llm_result.get("llm_score"))
    state.rule_score = _normalize_score(rule_result.get("rule_score"))
    raw_evidence_quality = state.llm_result.get("evidence_quality") or {}
    if not isinstance(raw_evidence_quality, dict):
        raw_evidence_quality = {}
    state.evidence_quality = (
        raw_evidence_quality if state.quality_status == "ok" else None
    )
    if (
        isinstance(state.evidence_quality, dict)
        and state.arbitration_quality_summary
    ):
        state.evidence_quality = {
            **state.evidence_quality,
            "backend_arbitration_quality": state.arbitration_quality_summary,
        }
    evidence_quality_score = (
        _normalize_score(raw_evidence_quality.get("score"))
        if state.quality_status == "ok"
        else 0.0
    )

    state.assessment_status, state.assessment_reason = assessment_outcome(
        provider_failed=state.is_llm_degraded,
        arbitration_status=state.arbitration_status,
        quality_status=state.quality_status,
        evidence_count=sum(
            evidence.get("stance") in {"support", "contradict"}
            and float(evidence.get("relevance_score") or 0) > 0
            and float(evidence.get("quality_score") or 0) > 0
            for evidence in state.effective_evidence
        ) if state.quality_status == "ok" and _normalize_score(raw_evidence_quality.get("coverage")) > 0 else 0,
    )
    if state.assessment_status == ASSESSMENT_COMPLETED:
        state.final_score = round(
            state.llm_score * 0.5
            + evidence_quality_score * 0.3
            + state.rule_score * 0.2,
            2,
        )

        state.risk_level = get_risk_level_from_score(state.final_score)
        state.judgement_result = build_judgement_result(state.risk_level)
        state.reason = _build_reason(state.llm_result, state.effective_evidence)
    else:
        state.final_score = None
        state.risk_level = UNKNOWN_RISK_LEVEL
        state.judgement_result = state.assessment_reason
        state.reason = state.assessment_reason
    state.risk_points = _merge_risk_points(
        state.llm_result.get("risk_points"),
        rule_result.get("hit_rules"),
    )
    state.all_keywords = _merge_keywords(
        state.keywords,
        state.llm_result.get("keywords"),
    )
    state.suggestion = clean_text(
        state.llm_result.get("suggestion") or "建议结合权威来源进行人工复核。",
        max_length=1000,
    )
    if state.assessment_status != ASSESSMENT_COMPLETED:
        state.suggestion = "请补充可追溯的原始来源，或在服务恢复后重新检测；不要将本次诊断分数作为真假结论。"
    state.similar_news = _build_similar_news_from_llm(
        candidates=state.evidence_list,
        effective_evidence=state.effective_evidence,
        llm_similar_news=state.llm_result.get("similar_news"),
    )
    state.retrieval_index_version = (
        "v2"
        if any(
            evidence.get("index_version") == "v2"
            for evidence in state.evidence_list
        )
        else "v1"
    )
    state.candidate_chunk_count = sum(
        len(evidence.get("chunks") or []) for evidence in state.evidence_list
    )
    state.candidate_parent_count = len(
        {
            evidence.get("knowledge_id")
            for evidence in state.evidence_list
            if evidence.get("knowledge_id") is not None
        }
    )
    state.rag_query_count = max(
        [
            int(evidence.get("retrieval_query_count") or 0)
            for evidence in state.evidence_list
        ]
        or [1]
    )
    state.rag_query_strategy = next(
        (
            evidence.get("retrieval_query_strategy")
            for evidence in state.evidence_list
            if evidence.get("retrieval_query_strategy")
        ),
        "single_query",
    )
    state.rag_supporting_span_count = sum(
        len(chunk.get("supporting_spans") or [])
        for evidence in state.evidence_list
        for chunk in evidence.get("chunks") or []
    )


def _build_graph_execution_payload(state: DetectionAgentState) -> dict[str, Any]:
    journal = state.runtime.get("graph_journal")
    if not isinstance(journal, GraphExecutionJournal):
        raise RuntimeError("detection graph execution journal is missing")
    snapshot = journal.snapshot()
    transitions = list(snapshot["transitions"])
    transitions.append(
        {"source": "persist_result", "target": END, "route": None}
    )
    node_runs = list(snapshot["node_runs"])
    node_runs.append(
        {
            "node_id": "persist_result",
            "status": "completed",
            "latency_ms": None,
            "error_type": None,
        }
    )
    return {
        "version": "1.0",
        "graph_name": "evidence-investigation-agent",
        "visited_nodes": snapshot["visited_nodes"],
        "transitions": transitions,
        "node_runs": node_runs,
    }


def _node_persist_result(state: DetectionAgentState) -> None:
    graph_execution = _build_graph_execution_payload(state)
    agent_trace = build_agent_trace(
        stage_latency_ms=state.stage_latency_ms,
        keyword_count=len(state.all_keywords),
        claim_count=len(state.core_claims),
        candidate_count=len(state.evidence_list),
        effective_evidence_count=len(state.effective_evidence),
        excluded_evidence_count=len(state.excluded_evidence),
        rag_query_count=state.rag_query_count,
        web_search_requested=bool(state.payload.enable_web_search),
        web_search_enabled=state.web_search_enabled,
        web_search_attempted=state.web_search_attempted,
        web_search_triggered=state.web_triggered,
        web_search_sources=state.web_sources_count,
        arbitration_status=state.arbitration_status,
        arbitration_attempts=state.arbitration_attempts,
        is_llm_degraded=state.is_llm_degraded,
        risk_level=state.risk_level,
        final_score=state.final_score,
        assessment_status=state.assessment_status,
        graph_execution=graph_execution,
    )
    analysis_payload = {
        "assessment_status": state.assessment_status,
        "assessment_reason": state.assessment_reason,
        "publish_time": state.payload.publish_time,
        "source_name": state.payload.source_name,
        "source_url": state.payload.source_url,
        "web_search_enabled": state.payload.enable_web_search,
        "retrieval_version": getattr(state.settings, "rag_index_version", "v1"),
        "index_version": state.retrieval_index_version,
        "candidate_chunk_count": state.candidate_chunk_count,
        "candidate_parent_count": state.candidate_parent_count,
        "rag_query_count": state.rag_query_count,
        "rag_query_strategy": state.rag_query_strategy,
        "rag_supporting_span_count": state.rag_supporting_span_count,
        "stage_latency_ms": dict(state.stage_latency_ms),
        "agent_trace": agent_trace,
        "core_claims": state.core_claims,
        "candidate_evidence_list": state.evidence_list,
        "excluded_evidence": state.excluded_evidence,
        "similar_news": state.similar_news,
        "evidence_quality": state.evidence_quality,
        "arbitration_quality": state.arbitration_quality_summary,
        "arbitration_status": state.arbitration_status,
        "quality_status": state.quality_status,
        "arbitration_error": state.arbitration_error,
        "arbitration_attempts": state.arbitration_attempts,
        "analysis_contract_version": ANALYSIS_CONTRACT_VERSION,
        "knowledge_has_relevant_match": state.knowledge_has_relevant_match,
        "web_has_relevant_match": state.web_has_relevant_match,
    }

    started_at = time.perf_counter()
    detection_record = _save_detection_record_with_tracing(
        state.db,
        DetectionCreate(
            user_id=getattr(state.current_user, "id", None),
            input_title=state.title,
            input_content=state.content,
            category=state.payload.category,
            keywords=",".join(state.all_keywords),
            final_score=state.final_score,
            assessment_status=state.assessment_status,
            evidence_score=state.evidence_score,
            llm_score=state.llm_score,
            rule_score=state.rule_score,
            risk_level=state.risk_level,
            judgement_result=state.judgement_result,
            reason=state.reason,
            risk_points=state.risk_points,
            suggestion=state.suggestion,
            is_high_risk=should_mark_high_risk(
                state.final_score,
                state.risk_level,
            ),
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
                for index, evidence in enumerate(
                    state.effective_evidence,
                    start=1,
                )
            ],
        ),
        effective_evidence_count=len(state.effective_evidence),
    )
    _record_stage_latency(state.stage_latency_ms, "db_save", started_at)

    state.result = {
        "assessment_status": state.assessment_status,
        "assessment_reason": state.assessment_reason,
        "detection_id": int(detection_record.id),
        "created_at": getattr(detection_record, "created_at", None),
        "publish_time": state.payload.publish_time,
        "source_name": state.payload.source_name,
        "source_url": state.payload.source_url,
        "final_score": state.final_score,
        "evidence_score": state.evidence_score,
        "llm_score": state.llm_score,
        "rule_score": state.rule_score,
        "risk_level": state.risk_level,
        "judgement_result": state.judgement_result,
        "reason": state.reason,
        "risk_points": state.risk_points,
        "keywords": state.all_keywords,
        "candidate_evidence_list": state.evidence_list,
        "evidence_list": state.effective_evidence,
        "excluded_evidence": state.excluded_evidence,
        "similar_news": state.similar_news,
        "suggestion": state.suggestion,
        "agent_steps": build_agent_steps(
            state.web_triggered,
            state.is_llm_degraded,
        ),
        "agent_trace": agent_trace,
        "disclaimer": DISCLAIMER,
        "web_search_triggered": state.web_triggered,
        "web_search_sources": state.web_sources_count,
        "retrieval_version": getattr(state.settings, "rag_index_version", "v1"),
        "index_version": state.retrieval_index_version,
        "candidate_chunk_count": state.candidate_chunk_count,
        "candidate_parent_count": state.candidate_parent_count,
        "rag_query_count": state.rag_query_count,
        "rag_query_strategy": state.rag_query_strategy,
        "rag_supporting_span_count": state.rag_supporting_span_count,
        "stage_latency_ms": state.stage_latency_ms,
        "core_claims": state.core_claims,
        "evidence_quality": state.evidence_quality,
        "arbitration_quality": state.arbitration_quality_summary,
        "arbitration_status": state.arbitration_status,
        "quality_status": state.quality_status,
        "arbitration_error": state.arbitration_error,
        "arbitration_attempts": state.arbitration_attempts,
        "analysis_contract_version": ANALYSIS_CONTRACT_VERSION,
        "knowledge_has_relevant_match": state.knowledge_has_relevant_match,
        "web_has_relevant_match": state.web_has_relevant_match,
    }


_DETECTION_AGENT_GRAPH = build_detection_agent_graph(
    {
        "prepare_input": _node_prepare_input,
        "extract_claims": _node_extract_claims,
        "retrieve_local_evidence": _node_retrieve_local_evidence,
        "route_web_search": _node_route_web_search,
        "search_web_evidence": _node_search_web_evidence,
        "prepare_model_input": _node_prepare_model_input,
        "analyze_with_model": _node_analyze_with_model,
        "arbitrate_evidence": _node_arbitrate_evidence,
        "retry_arbitration": _node_retry_arbitration,
        "score_risk": _node_score_risk,
        "persist_result": _node_persist_result,
    }
)


def detect_news_credibility(
    db: Session,
    payload: DetectNewsRequest,
    current_user: Any | None = None,
) -> dict[str, Any]:
    state = DetectionAgentState(
        db=db,
        payload=payload,
        current_user=current_user,
    )
    journal = GraphExecutionJournal()
    state.runtime["graph_journal"] = journal
    _DETECTION_AGENT_GRAPH.invoke(
        state,
        max_steps=len(DETECTION_NODE_IDS),
        on_node_start=journal.on_node_start,
        on_transition=journal.on_transition,
        on_node_run=journal.on_node_run,
    )
    if state.result is None:
        raise RuntimeError("detection agent graph completed without a result")
    return state.result


def _save_detection_record_with_tracing(
    db: Session,
    payload: DetectionCreate,
    *,
    effective_evidence_count: int,
) -> Any:
    with trace_span(
        "detection.db_save",
        {"evidence.effective_count": effective_evidence_count},
    ) as span:
        record = save_detection_record(db, payload)
        add_span_attributes(span, {"detection.id": int(record.id)})
        return record


def _validate_evidence_quality(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["missing or invalid evidence_quality"]

    errors: list[str] = list(value.get("validation_errors") or [])
    for field_name in ("coverage", "consistency", "score"):
        field_value = value.get(field_name)
        if (
            not isinstance(field_value, (int, float))
            or isinstance(field_value, bool)
            or not 0 <= float(field_value) <= 100
        ):
            errors.append(f"evidence_quality.{field_name} must be a number from 0 to 100")
    if not clean_text(value.get("assessment"), max_length=1000):
        errors.append("evidence_quality.assessment is empty")
    return errors


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
    claims: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    settings = get_settings()
    query_text = build_rag_search_text(title=title, content=content)
    query_texts = [query_text] if query_text else []
    if getattr(settings, "rag_claim_aware_enabled", True):
        query_texts = build_claim_aware_queries(
            title=title,
            content=content,
            claims=claims,
            max_queries=getattr(settings, "rag_claim_query_count", 4),
        )
    if not query_texts:
        return []

    try:
        if len(query_texts) == 1:
            results = search_similar_knowledge(
                db,
                query_text=query_texts[0],
                top_k=RAG_TOP_K,
            )
        else:
            ranked_result_sets = [
                search_similar_knowledge(db, query_text=query, top_k=RAG_TOP_K)
                for query in query_texts
            ]
            results = fuse_ranked_parent_results(
                ranked_result_sets,
                top_k=RAG_TOP_K,
                rank_constant=getattr(settings, "rag_rrf_rank_constant", 60),
                query_texts=query_texts,
            )
    except KnowledgeVectorSyncError as exc:
        raise KnowledgeRetrievalFailedError("知识库证据检索失败") from exc


    if getattr(settings, "rag_supporting_spans_enabled", True):
        results = add_supporting_spans_to_results(
            results,
            query_texts=query_texts,
            max_spans_per_result=getattr(settings, "rag_supporting_span_count", 2),
        )

    strategy = "claim_aware_multi_query" if len(query_texts) > 1 else "single_query"
    for result in results:
        result["retrieval_query_count"] = len(query_texts)
        result["retrieval_query_strategy"] = strategy
        result.setdefault(
            "retrieval_queries",
            [clean_text(query, max_length=300) for query in query_texts],
        )
    return results


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
                "source_url": metadata.get("source_url"),
                "publish_time": metadata.get("publish_time"),
                "risk_level": clean_text(metadata.get("risk_level"), max_length=30),
                "similarity_score": result.get("similarity_score"),
                "raw_cosine_score": result.get("raw_cosine_score"),
                "fusion_score": result.get("fusion_score"),
                "parent_revision": metadata.get("parent_revision"),
                "index_version": (
                    result.get("index_version")
                    or metadata.get("index_version")
                    or "v1"
                ),
                "chunks": result.get("chunks") or [],
                "supporting_spans": result.get("supporting_spans") or [],
                "score_components": result.get("score_components") or {},
                "query_match_count": result.get("query_match_count"),
                "query_hits": result.get("query_hits") or [],
                "retrieval_queries": result.get("retrieval_queries") or [],
                "retrieval_query_count": result.get("retrieval_query_count"),
                "retrieval_query_strategy": result.get("retrieval_query_strategy"),
                "multi_query_rrf_score": result.get("multi_query_rrf_score"),
                "rerank_original_rank": result.get("rerank_original_rank"),
                "rule_rerank_score": result.get("rule_rerank_score"),
                "model_rerank_score": result.get("model_rerank_score"),
                "model_rerank_reason": result.get("model_rerank_reason"),
                "rerank_score": result.get("rerank_score"),
                "rerank_stage": result.get("rerank_stage"),
                "diversity_adjusted_rerank_score": result.get("diversity_adjusted_rerank_score"),
                "rerank_order": result.get("rerank_order"),
                "rank_order": index,
                "source_type": "knowledge_base",
                "source_label": "📚 知识库",
            }
        )
    return evidence_list


def _is_llm_failure(llm_result: dict[str, Any]) -> bool:
    if llm_result.get("analysis_status") == "invalid_response":
        return True
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


def _normalize_arbitration_claim_ids(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_items = re.split(r"[,，\s]+", value)
    elif isinstance(value, list):
        raw_items = value
    else:
        return []

    claim_ids: list[str] = []
    for item in raw_items:
        claim_id = clean_text(item, max_length=20)
        if claim_id and claim_id not in claim_ids:
            claim_ids.append(claim_id)
    return claim_ids[:10]


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
