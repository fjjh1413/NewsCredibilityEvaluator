from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Generic, TypeVar


END = "__end__"

StateT = TypeVar("StateT")
Node = Callable[[StateT], None]
Router = Callable[[StateT], str]
NodeRunObserver = Callable[["NodeRun"], None]
NodeStartObserver = Callable[[str], None]
TransitionObserver = Callable[["Transition"], None]


@dataclass(frozen=True, slots=True)
class NodeRun:
    node_id: str
    status: str
    latency_ms: float
    error_type: str | None = None


@dataclass(frozen=True, slots=True)
class Transition:
    source: str
    target: str
    route: str | None = None


@dataclass(frozen=True, slots=True)
class GraphRunResult(Generic[StateT]):
    graph_name: str
    state: StateT
    visited_nodes: list[str]
    transitions: list[Transition]
    node_runs: list[NodeRun]


class GraphExecutionJournal:
    """Collect privacy-safe graph execution metadata for persistence and tracing."""

    def __init__(self) -> None:
        self._visited_nodes: list[str] = []
        self._transitions: list[Transition] = []
        self._node_runs: list[NodeRun] = []

    def on_node_start(self, node_id: str) -> None:
        self._visited_nodes.append(node_id)

    def on_transition(self, transition: Transition) -> None:
        self._transitions.append(transition)

    def on_node_run(self, node_run: NodeRun) -> None:
        self._node_runs.append(node_run)

    def snapshot(self) -> dict[str, object]:
        return {
            "visited_nodes": list(self._visited_nodes),
            "transitions": [
                {
                    "source": edge.source,
                    "target": edge.target,
                    "route": edge.route,
                }
                for edge in self._transitions
            ],
            "node_runs": [
                {
                    "node_id": run.node_id,
                    "status": run.status,
                    "latency_ms": run.latency_ms,
                    "error_type": run.error_type,
                }
                for run in self._node_runs
            ],
        }


@dataclass(frozen=True, slots=True)
class _ConditionalEdge(Generic[StateT]):
    router: Router[StateT]
    routes: Mapping[str, str]


class StateGraph(Generic[StateT]):
    """Small deterministic state graph for synchronous in-process workflows."""

    def __init__(self, name: str) -> None:
        if not name.strip():
            raise ValueError("graph name must not be empty")
        self._name = name
        self._nodes: dict[str, Node[StateT]] = {}
        self._edges: dict[str, str] = {}
        self._conditional_edges: dict[str, _ConditionalEdge[StateT]] = {}
        self._entry_point: str | None = None

    def add_node(self, node_id: str, node: Node[StateT]) -> None:
        self._validate_node_id(node_id)
        if node_id in self._nodes:
            raise ValueError(f"node {node_id!r} is already registered")
        self._nodes[node_id] = node

    def set_entry_point(self, node_id: str) -> None:
        self._entry_point = node_id

    def add_edge(self, source: str, target: str) -> None:
        self._ensure_no_outgoing_edge(source)
        self._edges[source] = target

    def add_conditional_edges(
        self,
        source: str,
        router: Router[StateT],
        routes: Mapping[str, str],
    ) -> None:
        if not routes:
            raise ValueError("conditional routes must not be empty")
        self._ensure_no_outgoing_edge(source)
        self._conditional_edges[source] = _ConditionalEdge(
            router=router,
            routes=dict(routes),
        )

    def compile(self) -> "CompiledStateGraph[StateT]":
        if self._entry_point is None:
            raise ValueError("graph entry point is not configured")
        self._validate_target(self._entry_point, context="entry point")
        for source, target in self._edges.items():
            self._validate_source(source)
            self._validate_target(target, context=f"edge from {source!r}")
        for source, edge in self._conditional_edges.items():
            self._validate_source(source)
            for route, target in edge.routes.items():
                if not route:
                    raise ValueError(f"conditional edge from {source!r} has empty route")
                self._validate_target(
                    target,
                    context=f"route {route!r} from {source!r}",
                )
        return CompiledStateGraph(
            name=self._name,
            nodes=dict(self._nodes),
            edges=dict(self._edges),
            conditional_edges=dict(self._conditional_edges),
            entry_point=self._entry_point,
        )

    def _ensure_no_outgoing_edge(self, source: str) -> None:
        if source in self._edges or source in self._conditional_edges:
            raise ValueError(f"node {source!r} already has an outgoing edge")

    def _validate_source(self, node_id: str) -> None:
        if node_id not in self._nodes:
            raise ValueError(f"edge source {node_id!r} is not a registered node")

    def _validate_target(self, node_id: str, *, context: str) -> None:
        if node_id != END and node_id not in self._nodes:
            raise ValueError(f"{context} targets unknown node {node_id!r}")

    @staticmethod
    def _validate_node_id(node_id: str) -> None:
        if not node_id or node_id == END:
            raise ValueError(f"invalid node id {node_id!r}")


class CompiledStateGraph(Generic[StateT]):
    def __init__(
        self,
        *,
        name: str,
        nodes: Mapping[str, Node[StateT]],
        edges: Mapping[str, str],
        conditional_edges: Mapping[str, _ConditionalEdge[StateT]],
        entry_point: str,
    ) -> None:
        self.name = name
        self._nodes = nodes
        self._edges = edges
        self._conditional_edges = conditional_edges
        self._entry_point = entry_point

    def invoke(
        self,
        state: StateT,
        *,
        max_steps: int = 100,
        on_node_run: NodeRunObserver | None = None,
        on_node_start: NodeStartObserver | None = None,
        on_transition: TransitionObserver | None = None,
    ) -> GraphRunResult[StateT]:
        if max_steps < 1:
            raise ValueError("max_steps must be at least 1")

        current = self._entry_point
        visited_nodes: list[str] = []
        transitions: list[Transition] = []
        node_runs: list[NodeRun] = []

        for _step in range(max_steps):
            visited_nodes.append(current)
            if on_node_start is not None:
                on_node_start(current)
            started_at = time.perf_counter()
            try:
                self._nodes[current](state)
            except Exception as exc:
                run = NodeRun(
                    node_id=current,
                    status="failed",
                    latency_ms=_elapsed_ms(started_at),
                    error_type=type(exc).__name__,
                )
                node_runs.append(run)
                if on_node_run is not None:
                    on_node_run(run)
                raise

            run = NodeRun(
                node_id=current,
                status="completed",
                latency_ms=_elapsed_ms(started_at),
            )
            node_runs.append(run)
            if on_node_run is not None:
                on_node_run(run)

            target, route = self._resolve_target(current, state)
            transition = Transition(source=current, target=target, route=route)
            transitions.append(transition)
            if on_transition is not None:
                on_transition(transition)
            if target == END:
                return GraphRunResult(
                    graph_name=self.name,
                    state=state,
                    visited_nodes=visited_nodes,
                    transitions=transitions,
                    node_runs=node_runs,
                )
            current = target

        raise RuntimeError(f"graph {self.name!r} exceeded max_steps={max_steps}")

    def describe(self) -> dict[str, object]:
        edges = [
            {"source": source, "target": target, "route": None}
            for source, target in self._edges.items()
        ]
        edges.extend(
            {
                "source": source,
                "target": target,
                "route": route,
            }
            for source, conditional in self._conditional_edges.items()
            for route, target in conditional.routes.items()
        )
        return {
            "name": self.name,
            "entry_point": self._entry_point,
            "nodes": list(self._nodes),
            "edges": edges,
        }

    def _resolve_target(self, source: str, state: StateT) -> tuple[str, str | None]:
        conditional = self._conditional_edges.get(source)
        if conditional is not None:
            route = conditional.router(state)
            if route not in conditional.routes:
                raise RuntimeError(
                    f"conditional edge from {source!r} returned unknown route {route!r}"
                )
            return conditional.routes[route], route
        if source not in self._edges:
            raise RuntimeError(f"node {source!r} has no outgoing edge")
        return self._edges[source], None


def _elapsed_ms(started_at: float) -> float:
    return round((time.perf_counter() - started_at) * 1000, 2)
