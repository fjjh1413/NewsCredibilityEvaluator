import unittest

from app.services.agent_state_graph import END, GraphExecutionJournal, StateGraph


class StateGraphTests(unittest.TestCase):
    def test_executes_nodes_and_records_real_transition_path(self) -> None:
        state = {"value": 0}
        graph = StateGraph[dict]("linear")
        graph.add_node("increment", lambda current: current.__setitem__("value", 1))
        graph.add_node("double", lambda current: current.__setitem__("value", 2))
        graph.set_entry_point("increment")
        graph.add_edge("increment", "double")
        graph.add_edge("double", END)

        result = graph.compile().invoke(state)

        self.assertIs(result.state, state)
        self.assertEqual(state["value"], 2)
        self.assertEqual(result.visited_nodes, ["increment", "double"])
        self.assertEqual(
            [(edge.source, edge.target, edge.route) for edge in result.transitions],
            [("increment", "double", None), ("double", END, None)],
        )
        self.assertTrue(all(run.status == "completed" for run in result.node_runs))
        self.assertTrue(all(run.latency_ms >= 0 for run in result.node_runs))

    def test_conditional_edge_executes_only_selected_branch(self) -> None:
        state = {"search": False, "events": []}
        graph = StateGraph[dict]("conditional")
        graph.add_node("route", lambda current: current["events"].append("route"))
        graph.add_node("search", lambda current: current["events"].append("search"))
        graph.add_node("finish", lambda current: current["events"].append("finish"))
        graph.set_entry_point("route")
        graph.add_conditional_edges(
            "route",
            lambda current: "search" if current["search"] else "skip",
            {"search": "search", "skip": "finish"},
        )
        graph.add_edge("search", "finish")
        graph.add_edge("finish", END)

        result = graph.compile().invoke(state)

        self.assertEqual(state["events"], ["route", "finish"])
        self.assertEqual(result.visited_nodes, ["route", "finish"])
        self.assertEqual(result.transitions[0].route, "skip")

    def test_unknown_conditional_route_is_rejected(self) -> None:
        graph = StateGraph[dict]("invalid-route")
        graph.add_node("route", lambda _state: None)
        graph.set_entry_point("route")
        graph.add_conditional_edges("route", lambda _state: "missing", {"ok": END})

        with self.assertRaisesRegex(RuntimeError, "unknown route 'missing'"):
            graph.compile().invoke({})

    def test_node_exception_is_not_wrapped(self) -> None:
        expected = ValueError("node failed")
        graph = StateGraph[dict]("failure")

        def fail(_state: dict) -> None:
            raise expected

        graph.add_node("fail", fail)
        graph.set_entry_point("fail")
        graph.add_edge("fail", END)

        with self.assertRaises(ValueError) as raised:
            graph.compile().invoke({})

        self.assertIs(raised.exception, expected)

    def test_max_steps_stops_accidental_cycle(self) -> None:
        graph = StateGraph[dict]("cycle")
        graph.add_node("loop", lambda _state: None)
        graph.set_entry_point("loop")
        graph.add_edge("loop", "loop")

        with self.assertRaisesRegex(RuntimeError, "exceeded max_steps=3"):
            graph.compile().invoke({}, max_steps=3)

    def test_execution_journal_captures_nodes_transitions_and_statuses(self) -> None:
        journal = GraphExecutionJournal()
        graph = StateGraph[dict]("journaled")
        graph.add_node("start", lambda state: state.update(route="finish"))
        graph.add_node("finish", lambda state: state.update(done=True))
        graph.set_entry_point("start")
        graph.add_conditional_edges(
            "start",
            lambda state: state["route"],
            {"finish": "finish"},
        )
        graph.add_edge("finish", END)

        graph.compile().invoke(
            {},
            on_node_start=journal.on_node_start,
            on_transition=journal.on_transition,
            on_node_run=journal.on_node_run,
        )

        snapshot = journal.snapshot()
        self.assertEqual(snapshot["visited_nodes"], ["start", "finish"])
        self.assertEqual(snapshot["transitions"][0]["route"], "finish")
        self.assertEqual(snapshot["transitions"][-1]["target"], END)
        self.assertEqual(
            [run["status"] for run in snapshot["node_runs"]],
            ["completed", "completed"],
        )


if __name__ == "__main__":
    unittest.main()
