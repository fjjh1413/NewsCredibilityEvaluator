from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.schemas.detection import DetectNewsRequest
from app.services.agent_state_graph import END, CompiledStateGraph, StateGraph


DETECTION_NODE_IDS = (
    "prepare_input",
    "extract_claims",
    "retrieve_local_evidence",
    "route_web_search",
    "search_web_evidence",
    "prepare_model_input",
    "analyze_with_model",
    "arbitrate_evidence",
    "retry_arbitration",
    "score_risk",
    "persist_result",
)


@dataclass(slots=True)
class DetectionAgentState:
    db: Session
    payload: DetectNewsRequest
    current_user: Any | None = None
    title: str = ""
    content: str = ""
    stage_latency_ms: dict[str, float] = field(default_factory=dict)
    keywords: list[str] = field(default_factory=list)
    core_claims: list[dict[str, str]] = field(default_factory=list)
    evidence_list: list[dict[str, Any]] = field(default_factory=list)
    rag_query_count: int = 1
    settings: Any = None
    web_search_enabled: bool = True
    should_search_web: bool = False
    web_search_attempted: bool = False
    web_triggered: bool = False
    web_sources_count: int = 0
    prompt_evidence: list[dict[str, Any]] = field(default_factory=list)
    prompt_template: str = ""
    llm_result: dict[str, Any] = field(default_factory=dict)
    ranking_result: dict[str, Any] | None = None
    arbitration_status: str = "unavailable"
    quality_status: str = "unavailable"
    arbitration_attempts: int = 0
    arbitration_error: str | None = None
    arbitration_quality_summary: dict[str, Any] = field(default_factory=dict)
    should_retry_arbitration: bool = False
    effective_evidence: list[dict[str, Any]] = field(default_factory=list)
    excluded_evidence: list[dict[str, Any]] = field(default_factory=list)
    is_llm_degraded: bool = False
    knowledge_has_relevant_match: bool = False
    web_has_relevant_match: bool = False
    evidence_score: float = 0.0
    llm_score: float = 0.0
    rule_score: float = 0.0
    final_score: float | None = None
    assessment_status: str = "degraded"
    assessment_reason: str = ""
    risk_level: str = ""
    judgement_result: str = ""
    reason: str = ""
    risk_points: list[str] = field(default_factory=list)
    all_keywords: list[str] = field(default_factory=list)
    suggestion: str = ""
    similar_news: list[dict[str, Any]] = field(default_factory=list)
    evidence_quality: dict[str, Any] | None = None
    retrieval_index_version: str = "v1"
    candidate_chunk_count: int = 0
    candidate_parent_count: int = 0
    rag_query_strategy: str = "single_query"
    rag_supporting_span_count: int = 0
    result: dict[str, Any] | None = None
    runtime: dict[str, Any] = field(default_factory=dict)


def build_detection_agent_graph(
    nodes: Mapping[str, Callable[[DetectionAgentState], None]],
) -> CompiledStateGraph[DetectionAgentState]:
    missing = [node_id for node_id in DETECTION_NODE_IDS if node_id not in nodes]
    extra = [node_id for node_id in nodes if node_id not in DETECTION_NODE_IDS]
    if missing:
        raise ValueError(f"missing detection graph nodes: {', '.join(missing)}")
    if extra:
        raise ValueError(f"unknown detection graph nodes: {', '.join(extra)}")

    graph = StateGraph[DetectionAgentState]("evidence-investigation-agent")
    for node_id in DETECTION_NODE_IDS:
        graph.add_node(node_id, nodes[node_id])

    graph.set_entry_point("prepare_input")
    graph.add_edge("prepare_input", "extract_claims")
    graph.add_edge("extract_claims", "retrieve_local_evidence")
    graph.add_edge("retrieve_local_evidence", "route_web_search")
    graph.add_conditional_edges(
        "route_web_search",
        lambda state: "search" if state.should_search_web else "skip",
        {
            "search": "search_web_evidence",
            "skip": "prepare_model_input",
        },
    )
    graph.add_edge("search_web_evidence", "prepare_model_input")
    graph.add_edge("prepare_model_input", "analyze_with_model")
    graph.add_edge("analyze_with_model", "arbitrate_evidence")
    graph.add_conditional_edges(
        "arbitrate_evidence",
        lambda state: "retry" if state.should_retry_arbitration else "continue",
        {
            "retry": "retry_arbitration",
            "continue": "score_risk",
        },
    )
    graph.add_edge("retry_arbitration", "score_risk")
    graph.add_edge("score_risk", "persist_result")
    graph.add_edge("persist_result", END)
    return graph.compile()
