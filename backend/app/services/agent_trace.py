from __future__ import annotations

from typing import Any


TRACE_VERSION = "1.0"
AGENT_NAME = "evidence-investigation-agent"


def _latency(stage_latency_ms: dict[str, float], *stage_names: str) -> float | None:
    values = [
        float(stage_latency_ms[name])
        for name in stage_names
        if name in stage_latency_ms
    ]
    return round(sum(values), 2) if values else None


def _stage(
    *,
    stage_id: str,
    title: str,
    kind: str,
    status: str,
    decision: str,
    summary: str,
    latency_ms: float | None,
    metrics: dict[str, Any],
    tool: str | None = None,
) -> dict[str, Any]:
    return {
        "id": stage_id,
        "title": title,
        "kind": kind,
        "tool": tool,
        "status": status,
        "latency_ms": latency_ms,
        "decision": decision,
        "summary": summary,
        "metrics": metrics,
    }


def _web_search_decision(
    *,
    requested: bool,
    enabled: bool,
    attempted: bool,
    triggered: bool,
) -> tuple[str, str, str]:
    if triggered:
        return (
            "completed",
            "本地证据不足，按策略调用联网搜索补充时效性证据。",
            "已调用联网搜索并合并候选证据。",
        )
    if attempted:
        return (
            "degraded",
            "本地证据不足，已调用联网搜索，但没有可合并的结果。",
            "联网搜索未返回可用来源，工作流继续使用本地证据。",
        )
    if not requested:
        return (
            "skipped",
            "用户未请求联网补证，保持本地知识库检索路径。",
            "未调用联网搜索。",
        )
    if not enabled:
        return (
            "skipped",
            "系统级联网搜索开关已关闭。",
            "未调用联网搜索。",
        )
    return (
        "skipped",
        "本地证据已满足补证阈值，无需增加外部调用成本。",
        "未调用联网搜索。",
    )


def _arbitration_state(
    *,
    arbitration_status: str,
    is_llm_degraded: bool,
) -> tuple[str, str]:
    if is_llm_degraded or arbitration_status in {"provider_error", "retry_exhausted"}:
        return "degraded", "模型或证据仲裁未完整成功，结果已按安全策略降级。"
    if arbitration_status == "no_evidence":
        return "skipped", "未召回候选证据，跳过证据仲裁并保留无证据状态。"
    if arbitration_status == "ok":
        return "completed", "模型已完成结构化分析，后端已校验证据仲裁契约。"
    return "degraded", "证据仲裁状态不可用，未让未仲裁候选影响证据评分。"


def build_agent_trace(
    *,
    stage_latency_ms: dict[str, float],
    keyword_count: int,
    claim_count: int,
    candidate_count: int,
    effective_evidence_count: int,
    excluded_evidence_count: int,
    rag_query_count: int,
    web_search_requested: bool,
    web_search_enabled: bool,
    web_search_attempted: bool,
    web_search_triggered: bool,
    web_search_sources: int,
    arbitration_status: str,
    arbitration_attempts: int,
    is_llm_degraded: bool,
    risk_level: str,
    final_score: float | None,
    assessment_status: str = "completed",
    graph_execution: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a privacy-safe trace of the observable agent workflow.

    The trace intentionally stores decisions, counts and timings rather than raw
    prompts, article content, tool arguments or hidden model reasoning.
    """
    web_status, web_decision, web_summary = _web_search_decision(
        requested=web_search_requested,
        enabled=web_search_enabled,
        attempted=web_search_attempted,
        triggered=web_search_triggered,
    )
    arbitration_stage_status, arbitration_decision = _arbitration_state(
        arbitration_status=arbitration_status,
        is_llm_degraded=is_llm_degraded,
    )
    retry_count = max(0, arbitration_attempts - 1)

    stages = [
        _stage(
            stage_id="extract_claims",
            title="提取关键词与核心主张",
            kind="reasoning",
            status="completed",
            decision="先把长文本压缩为可检索、可逐项核验的主张。",
            summary=f"提取 {keyword_count} 个关键词和 {claim_count} 条核心主张。",
            latency_ms=_latency(stage_latency_ms, "extract_keywords"),
            metrics={"keyword_count": keyword_count, "claim_count": claim_count},
        ),
        _stage(
            stage_id="retrieve_local_evidence",
            title="检索本地证据",
            kind="tool",
            tool="chroma_hybrid_search",
            status="completed",
            decision="始终先搜索本地知识库，建立低成本、可复用的证据基线。",
            summary=f"使用 {rag_query_count} 个查询召回 {candidate_count} 条候选证据。",
            latency_ms=_latency(stage_latency_ms, "rag_search"),
            metrics={
                "candidate_count": candidate_count,
                "query_count": rag_query_count,
            },
        ),
        _stage(
            stage_id="route_web_search",
            title="路由联网补证",
            kind="decision",
            tool="bocha_web_search",
            status=web_status,
            decision=web_decision,
            summary=(
                f"联网证据来源 {web_search_sources} 条。"
                if web_search_triggered
                else web_summary
            ),
            latency_ms=_latency(stage_latency_ms, "web_search"),
            metrics={
                "requested": web_search_requested,
                "enabled": web_search_enabled,
                "attempted": web_search_attempted,
                "source_count": web_search_sources,
            },
        ),
        _stage(
            stage_id="load_output_contract",
            title="加载输出契约",
            kind="guardrail",
            status="completed",
            decision="在模型调用前固定结构化输出和证据引用边界。",
            summary="已加载可信度分析模板与输出契约。",
            latency_ms=_latency(stage_latency_ms, "prompt_template"),
            metrics={},
        ),
        _stage(
            stage_id="analyze_and_arbitrate",
            title="分析并仲裁证据",
            kind="model",
            tool="deepseek_structured_analysis",
            status=arbitration_stage_status,
            decision=arbitration_decision,
            summary=(
                f"采纳 {effective_evidence_count} 条，排除 {excluded_evidence_count} 条；"
                f"共尝试 {arbitration_attempts} 次。"
            ),
            latency_ms=_latency(
                stage_latency_ms,
                "llm_analysis",
                "evidence_arbitration_retry",
            ),
            metrics={
                "attempts": arbitration_attempts,
                "retry_count": retry_count,
                "accepted_evidence_count": effective_evidence_count,
                "excluded_evidence_count": excluded_evidence_count,
            },
        ),
        _stage(
            stage_id="score_risk",
            title="计算风险评分",
            kind="guardrail",
            status="completed" if final_score is not None else "skipped",
            decision="仅在模型与证据校验完整成功时生成综合评分；其他情况保留无法判断状态。",
            summary=(f"最终分数 {round(float(final_score), 2)}，风险等级为{risk_level}。"
                     if final_score is not None else "本次无法判断，不生成综合可信度分数。"),
            latency_ms=_latency(stage_latency_ms, "rule_score"),
            metrics={"final_score": round(float(final_score), 2) if final_score is not None else None,
                     "assessment_status": assessment_status},
        ),
    ]
    trace_status = (
        "degraded"
        if (
            is_llm_degraded
            or arbitration_stage_status == "degraded"
            or web_status == "degraded"
            or assessment_status != "completed"
        )
        else "completed"
    )
    trace = {
        "version": TRACE_VERSION,
        "agent_name": AGENT_NAME,
        "status": trace_status,
        "total_latency_ms": round(
            sum(
                stage["latency_ms"]
                for stage in stages
                if stage["latency_ms"] is not None
            ),
            2,
        ),
        "stages": stages,
    }
    if graph_execution is not None:
        trace["graph_execution"] = graph_execution
    return trace
