import json
import unittest
from pathlib import Path

from app.schemas.detection import AgentTraceOut


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TRACE_EXAMPLE_PATH = REPOSITORY_ROOT / "docs" / "agent_trace_v1_example.json"
SCENARIO_PATH = (
    REPOSITORY_ROOT
    / "evaluation"
    / "datasets"
    / "agent_trace_v1_scenarios.json"
)


class AgentTraceBaselineAssetTests(unittest.TestCase):
    def test_trace_example_matches_the_v1_api_contract(self) -> None:
        trace = AgentTraceOut.model_validate(
            json.loads(TRACE_EXAMPLE_PATH.read_text(encoding="utf-8"))
        )

        self.assertEqual(trace.version, "1.0")
        self.assertEqual(trace.agent_name, "evidence-investigation-agent")
        self.assertEqual(len(trace.stages), 6)
        self.assertIsNotNone(trace.graph_execution)
        self.assertEqual(
            trace.graph_execution.graph_name,
            "evidence-investigation-agent",
        )
        self.assertEqual(
            trace.graph_execution.transitions[3].route,
            "skip",
        )
        self.assertIn(
            "persist_result",
            trace.graph_execution.visited_nodes,
        )
        self.assertEqual(
            [stage.id for stage in trace.stages],
            [
                "extract_claims",
                "retrieve_local_evidence",
                "route_web_search",
                "load_output_contract",
                "analyze_and_arbitrate",
                "score_risk",
            ],
        )

    def test_scenario_catalog_covers_twenty_unique_agent_paths(self) -> None:
        catalog = json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))
        scenarios = catalog["scenarios"]

        self.assertEqual(catalog["schema_version"], "1.0")
        self.assertEqual(len(scenarios), 20)
        self.assertEqual(len({item["id"] for item in scenarios}), 20)
        self.assertTrue(
            {"retrieval", "routing", "arbitration", "scoring", "compatibility"}
            <= {item["category"] for item in scenarios}
        )
        self.assertTrue(
            all(
                item["expected"]["trace_status"]
                in {"completed", "degraded", "absent"}
                and item["expected"]["web_stage_status"]
                in {"completed", "skipped", "degraded", "absent"}
                and item["expected"]["arbitration_stage_status"]
                in {"completed", "skipped", "degraded", "absent"}
                for item in scenarios
            )
        )
        legacy_without_trace = next(
            item for item in scenarios if item["id"] == "ATV1-019"
        )
        self.assertEqual(legacy_without_trace["expected"]["trace_status"], "absent")


if __name__ == "__main__":
    unittest.main()
