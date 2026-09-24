import unittest

from app.services.agent_trace import build_agent_trace


class AgentTraceTests(unittest.TestCase):
    def test_builds_auditable_trace_for_completed_run(self) -> None:
        trace = build_agent_trace(
            stage_latency_ms={
                "extract_keywords": 2.5,
                "rag_search": 18.0,
                "web_search": 0.4,
                "prompt_template": 1.0,
                "llm_analysis": 120.0,
                "rule_score": 3.0,
                "db_save": 5.0,
            },
            keyword_count=4,
            claim_count=2,
            candidate_count=8,
            effective_evidence_count=3,
            excluded_evidence_count=5,
            rag_query_count=2,
            web_search_requested=True,
            web_search_enabled=True,
            web_search_attempted=False,
            web_search_triggered=False,
            web_search_sources=0,
            arbitration_status="ok",
            arbitration_attempts=1,
            is_llm_degraded=False,
            risk_level="存疑信息",
            final_score=68.5,
        )

        self.assertEqual(trace["version"], "1.0")
        self.assertEqual(trace["status"], "completed")
        self.assertEqual(trace["total_latency_ms"], 144.9)
        self.assertEqual(
            [stage["id"] for stage in trace["stages"]],
            [
                "extract_claims",
                "retrieve_local_evidence",
                "route_web_search",
                "load_output_contract",
                "analyze_and_arbitrate",
                "score_risk",
            ],
        )

        web_stage = trace["stages"][2]
        self.assertEqual(web_stage["status"], "skipped")
        self.assertIn("本地证据已满足", web_stage["decision"])
        self.assertEqual(web_stage["tool"], "bocha_web_search")

        arbitration_stage = trace["stages"][4]
        self.assertEqual(arbitration_stage["status"], "completed")
        self.assertEqual(arbitration_stage["metrics"]["attempts"], 1)
        self.assertEqual(arbitration_stage["metrics"]["accepted_evidence_count"], 3)

    def test_marks_retry_exhaustion_as_degraded_without_exposing_raw_inputs(self) -> None:
        trace = build_agent_trace(
            stage_latency_ms={"llm_analysis": 100.0, "evidence_arbitration_retry": 80.0},
            keyword_count=1,
            claim_count=1,
            candidate_count=3,
            effective_evidence_count=0,
            excluded_evidence_count=0,
            rag_query_count=1,
            web_search_requested=False,
            web_search_enabled=True,
            web_search_attempted=False,
            web_search_triggered=False,
            web_search_sources=0,
            arbitration_status="retry_exhausted",
            arbitration_attempts=2,
            is_llm_degraded=False,
            risk_level="高风险信息",
            final_score=32.0,
        )

        self.assertEqual(trace["status"], "degraded")
        arbitration_stage = next(
            stage for stage in trace["stages"] if stage["id"] == "analyze_and_arbitrate"
        )
        self.assertEqual(arbitration_stage["status"], "degraded")
        self.assertEqual(arbitration_stage["metrics"]["attempts"], 2)
        self.assertEqual(arbitration_stage["metrics"]["retry_count"], 1)
        self.assertNotIn("prompt", str(trace).lower())
        self.assertNotIn("content", str(trace).lower())

    def test_ignores_unrepresented_persistence_latency(self) -> None:
        trace = build_agent_trace(
            stage_latency_ms={"extract_keywords": 2.0, "db_save": 9.0},
            keyword_count=1,
            claim_count=1,
            candidate_count=0,
            effective_evidence_count=0,
            excluded_evidence_count=0,
            rag_query_count=1,
            web_search_requested=False,
            web_search_enabled=True,
            web_search_attempted=False,
            web_search_triggered=False,
            web_search_sources=0,
            arbitration_status="no_evidence",
            arbitration_attempts=0,
            is_llm_degraded=False,
            risk_level="存疑信息",
            final_score=50.0,
        )

        self.assertEqual(trace["total_latency_ms"], 2.0)
        self.assertNotIn("persist_result", [stage["id"] for stage in trace["stages"]])

    def test_distinguishes_failed_web_tool_from_policy_skip(self) -> None:
        trace = build_agent_trace(
            stage_latency_ms={"web_search": 8000.0},
            keyword_count=1,
            claim_count=1,
            candidate_count=0,
            effective_evidence_count=0,
            excluded_evidence_count=0,
            rag_query_count=1,
            web_search_requested=True,
            web_search_enabled=True,
            web_search_attempted=True,
            web_search_triggered=False,
            web_search_sources=0,
            arbitration_status="ok",
            arbitration_attempts=1,
            is_llm_degraded=False,
            risk_level="存疑信息",
            final_score=55.0,
        )

        web_stage = next(
            stage for stage in trace["stages"] if stage["id"] == "route_web_search"
        )
        self.assertEqual(trace["status"], "degraded")
        self.assertEqual(web_stage["status"], "degraded")
        self.assertIn("未返回可用来源", web_stage["summary"])


if __name__ == "__main__":
    unittest.main()
