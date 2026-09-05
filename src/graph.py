from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum


class ZoneType(Enum):
    NORMAL = "normal"
    BLOCKED = "blocked"
    RESTRICTED = "restricted"
    PRIORITY = "priority"


@dataclass
class Connection:
    u: str
    v: str
    max_link_capacity: int = 1


@dataclass
class Hub:
    name: str
    x: int
    y: int
    zone: ZoneType = ZoneType.NORMAL
    color: str | None = None
    max_drones: int = 1
    is_start: bool = False
    is_end: bool = False


@dataclass(frozen=True)
class TimeNode:
    """Immutable node tracking hub, time step, and vertex partition."""

    hub_name: str
    turn: int
    is_out_node: bool


@dataclass(eq=False)
class FlowEdge:
    """Residual edge tracking capacity, costs, and paired reverse links."""

    u: TimeNode
    v: TimeNode
    capacity: int
    cost: int
    initial_capacity: int = 0
    undo_link: FlowEdge | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.initial_capacity == 0 and self.capacity > 0:
            self.initial_capacity = self.capacity

    @property
    def residual_capacity(self) -> int:
        return self.capacity


def add_residual_edge_pair(
    adj: dict[TimeNode, list[FlowEdge]],
    u: TimeNode,
    v: TimeNode,
    capacity: int,
    cost: int,
) -> tuple[FlowEdge, FlowEdge]:
    """Appends forward and reverse edges via paired object references."""
    forward_edge = FlowEdge(
        u=u, v=v, capacity=capacity, cost=cost, initial_capacity=capacity
    )
    reverse_edge = FlowEdge(
        u=v, v=u, capacity=0, cost=-cost, initial_capacity=0
    )

    forward_edge.undo_link = reverse_edge
    reverse_edge.undo_link = forward_edge

    adj.setdefault(u, []).append(forward_edge)
    adj.setdefault(v, []).append(reverse_edge)
    return forward_edge, reverse_edge


@dataclass
class Graph:
    drone_count: int = 0
    hubs: dict[str, Hub] = field(default_factory=dict)
    adj: dict[str, list[Connection]] = field(default_factory=dict)
    start_hub: Hub | None = None
    end_hub: Hub | None = None


class TimeExpandedGraph:
    """Builds an unrolled network with vertex splitting and capacities."""

    def __init__(self, physical_graph: Graph, horizon: int) -> None:
        self.physical_graph = physical_graph
        self.horizon = horizon
        self.adj: dict[TimeNode, list[FlowEdge]] = {}
        self.source = TimeNode("__source__", -1, False)
        self.sink = TimeNode("__sink__", 999999, True)
        self.built_turns = -1
        self.extend_to_horizon(self.horizon)

    def get_zone_traversal_cost(self, zone: ZoneType) -> int:
        if zone == ZoneType.PRIORITY:
            return 8
        if zone == ZoneType.RESTRICTED:
            return 20
        return 10

    def extend_to_horizon(self, new_horizon: int) -> None:
        if new_horizon <= self.built_turns:
            return

        start_turn = 0 if self.built_turns < 0 else self.built_turns + 1
        self.horizon = new_horizon

        # Connect global source to start hub at turn 0
        if self.built_turns < 0 and self.physical_graph.start_hub:
            start_in = TimeNode(self.physical_graph.start_hub.name, 0, False)
            add_residual_edge_pair(
                self.adj,
                self.source,
                start_in,
                self.physical_graph.drone_count,
                0,
            )

        for t in range(start_turn, self.horizon + 1):
            # 1. Zone Splitting: Internal bottleneck edges (IN -> OUT)
            for hub in self.physical_graph.hubs.values():
                if hub.zone == ZoneType.BLOCKED:
                    continue

                in_node = TimeNode(hub.name, t, False)
                out_node = TimeNode(hub.name, t, True)

                cap = (
                    self.physical_graph.drone_count
                    if (hub.is_start or hub.is_end)
                    else hub.max_drones
                )
                add_residual_edge_pair(self.adj, in_node, out_node, cap, 0)

                # Connect terminal hub directly to global sink
                if hub.is_end:
                    turn_cost = t * 1000
                    add_residual_edge_pair(
                        self.adj,
                        out_node,
                        self.sink,
                        self.physical_graph.drone_count,
                        turn_cost,
                    )

            # 2. Time transitions from turn (t - 1) to turn t
            if t > 0:
                # Wait edges across turns (t-1 -> t)
                for hub in self.physical_graph.hubs.values():
                    if hub.zone == ZoneType.BLOCKED or hub.is_end:
                        continue

                    prev_out = TimeNode(hub.name, t - 1, True)
                    curr_in = TimeNode(hub.name, t, False)
                    wait_cap = (
                        self.physical_graph.drone_count
                        if hub.is_start
                        else hub.max_drones
                    )
                    wait_cost = 10 if hub.is_start else 12
                    add_residual_edge_pair(
                        self.adj, prev_out, curr_in, wait_cap, wait_cost
                    )

                # Connection links across turns (t-1 -> t)
                for u_name, edges in self.physical_graph.adj.items():
                    u_hub = self.physical_graph.hubs[u_name]
                    if u_hub.zone == ZoneType.BLOCKED or u_hub.is_end:
                        continue

                    prev_out = TimeNode(u_name, t - 1, True)

                    for conn in edges:
                        v_hub = self.physical_graph.hubs[conn.v]
                        if v_hub.zone == ZoneType.BLOCKED:
                            continue

                        curr_in = TimeNode(conn.v, t, False)
                        cost = self.get_zone_traversal_cost(v_hub.zone)
                        add_residual_edge_pair(
                            self.adj,
                            prev_out,
                            curr_in,
                            conn.max_link_capacity,
                            cost,
                        )

        self.built_turns = new_horizon