import unittest

from app.services.agent_state_graph import END
from app.services.detection_agent_graph import (
    DETECTION_NODE_IDS,
    build_detection_agent_graph,
)


class DetectionAgentGraphDefinitionTests(unittest.TestCase):
    def test_graph_exposes_named_nodes_and_conditional_edges(self) -> None:
        nodes = {node_id: (lambda _state: None) for node_id in DETECTION_NODE_IDS}

        description = build_detection_agent_graph(nodes).describe()

        self.assertEqual(description["entry_point"], "prepare_input")
        self.assertEqual(description["nodes"], list(DETECTION_NODE_IDS))
        edge_tuples = {
            (edge["source"], edge["target"], edge["route"])
            for edge in description["edges"]
        }
        self.assertIn(
            ("route_web_search", "search_web_evidence", "search"),
            edge_tuples,
        )
        self.assertIn(
            ("route_web_search", "prepare_model_input", "skip"),
            edge_tuples,
        )
        self.assertIn(
            ("arbitrate_evidence", "retry_arbitration", "retry"),
            edge_tuples,
        )
        self.assertIn(
            ("arbitrate_evidence", "score_risk", "continue"),
            edge_tuples,
        )
        self.assertIn(("persist_result", END, None), edge_tuples)

    def test_graph_requires_every_declared_node(self) -> None:
        with self.assertRaisesRegex(ValueError, "missing detection graph nodes"):
            build_detection_agent_graph({})


if __name__ == "__main__":
    unittest.main()
