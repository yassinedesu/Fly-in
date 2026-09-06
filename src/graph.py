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


@dataclass
class SharedCapacity:
    """Shared capacity state across paired bidirectional connection edges."""

    capacity: int
    initial_capacity: int = 0

    def __post_init__(self) -> None:
        if self.initial_capacity == 0:
            self.initial_capacity = self.capacity


@dataclass(eq=False)
class FlowEdge:
    """Residual edge tracking capacity, costs, and paired reverse links."""

    u: TimeNode
    v: TimeNode
    _capacity: int
    cost: int
    initial_capacity: int = 0
    undo_link: FlowEdge | None = field(default=None, repr=False)
    shared_cap: SharedCapacity | None = field(default=None, repr=False)
    flow: int = 0

    def __post_init__(self) -> None:
        if self.initial_capacity == 0 and self._capacity > 0:
            self.initial_capacity = self._capacity

    @property
    def capacity(self) -> int:
        if self.shared_cap is not None:
            return self.shared_cap.capacity
        return self._capacity

    @capacity.setter
    def capacity(self, value: int) -> None:
        if self.shared_cap is not None:
            diff = self.shared_cap.capacity - value
            self.shared_cap.capacity = value
            self.flow += diff
        else:
            diff = self._capacity - value
            self._capacity = value
            self.flow += diff

    @property
    def residual_capacity(self) -> int:
        return self.capacity


def add_residual_edge_pair(
    adj: dict[TimeNode, list[FlowEdge]],
    u: TimeNode,
    v: TimeNode,
    capacity: int,
    cost: int,
    shared_cap: SharedCapacity | None = None,
) -> tuple[FlowEdge, FlowEdge]:
    """Appends forward and reverse edges via paired object references."""
    forward_edge = FlowEdge(
        u=u,
        v=v,
        _capacity=capacity,
        cost=cost,
        initial_capacity=capacity,
        shared_cap=shared_cap,
    )
    reverse_edge = FlowEdge(
        u=v,
        v=u,
        _capacity=0,
        cost=-cost,
        initial_capacity=0,
        shared_cap=None,
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
            # 1. Zone Splitting: Internal capacity bottleneck (IN -> OUT)
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

                if hub.is_end:
                    turn_cost = t * 1000
                    add_residual_edge_pair(
                        self.adj,
                        out_node,
                        self.sink,
                        self.physical_graph.drone_count,
                        turn_cost,
                    )

        # 2. Transit Splitting: Intermediate nodes for restricted transitions
            if t > 0:
                for u_name, conns in self.physical_graph.adj.items():
                    u_hub = self.physical_graph.hubs[u_name]
                    if u_hub.zone == ZoneType.BLOCKED:
                        continue
                    for conn in conns:
                        v_hub = self.physical_graph.hubs[conn.v]
                        if v_hub.zone == ZoneType.RESTRICTED:
                            t_in = TimeNode(f"{u_name}-{conn.v}", t, False)
                            t_out = TimeNode(f"{u_name}-{conn.v}", t, True)
                            add_residual_edge_pair(
                                self.adj,
                                t_in,
                                t_out,
                                conn.max_link_capacity,
                                0,
                            )

            # 3. Time transitions from turn (t - 1) to turn t
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

                # Complete 2-turn restricted transit: transit(t-1) -> dest(t)
                for u_name, conns in self.physical_graph.adj.items():
                    u_hub = self.physical_graph.hubs[u_name]
                    if u_hub.zone == ZoneType.BLOCKED:
                        continue
                    for conn in conns:
                        v_hub = self.physical_graph.hubs[conn.v]
                        if v_hub.zone == ZoneType.RESTRICTED:
                            p_trans_out = TimeNode(
                                f"{u_name}-{conn.v}", t - 1, True
                            )
                            c_dest_in = TimeNode(conn.v, t, False)
                            add_residual_edge_pair(
                                self.adj,
                                p_trans_out,
                                c_dest_in,
                                conn.max_link_capacity,
                                0,
                            )

                # Connection entry links across turns (t-1 -> t)
                seen_pairs: set[frozenset[str]] = set()
                for u_name, conns in self.physical_graph.adj.items():
                    u_hub = self.physical_graph.hubs[u_name]
                    if u_hub.zone == ZoneType.BLOCKED:
                        continue
                    for conn in conns:
                        v_hub = self.physical_graph.hubs[conn.v]
                        if v_hub.zone == ZoneType.BLOCKED:
                            continue

                        pair = frozenset({u_name, conn.v})
                        if pair in seen_pairs:
                            continue
                        seen_pairs.add(pair)

                        shared_cap = SharedCapacity(conn.max_link_capacity)

                        # u -> v transition
                        if not u_hub.is_end:
                            prev_out_u = TimeNode(u_name, t - 1, True)
                            if v_hub.zone == ZoneType.RESTRICTED:
                                target_in = TimeNode(
                                    f"{u_name}-{conn.v}", t, False
                                )
                                cost = self.get_zone_traversal_cost(
                                    ZoneType.RESTRICTED
                                )
                            else:
                                target_in = TimeNode(conn.v, t, False)
                                cost = self.get_zone_traversal_cost(v_hub.zone)
                            add_residual_edge_pair(
                                self.adj,
                                prev_out_u,
                                target_in,
                                conn.max_link_capacity,
                                cost,
                                shared_cap=shared_cap,
                            )

                        # v -> u transition
                        if not v_hub.is_end:
                            prev_out_v = TimeNode(conn.v, t - 1, True)
                            if u_hub.zone == ZoneType.RESTRICTED:
                                target_in = TimeNode(
                                    f"{conn.v}-{u_name}", t, False
                                )
                                cost = self.get_zone_traversal_cost(
                                    ZoneType.RESTRICTED
                                )
                            else:
                                target_in = TimeNode(u_name, t, False)
                                cost = self.get_zone_traversal_cost(u_hub.zone)
                            add_residual_edge_pair(
                                self.adj,
                                prev_out_v,
                                target_in,
                                conn.max_link_capacity,
                                cost,
                                shared_cap=shared_cap,
                            )

        self.built_turns = new_horizon
