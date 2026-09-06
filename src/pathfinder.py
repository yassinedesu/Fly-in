from __future__ import annotations

from collections import deque
from graph import FlowEdge, Graph, TimeExpandedGraph, TimeNode


class Pathfinder:
    """Finds multi-drone conflict-free routes on a time-expanded graph."""

    def __init__(self, graph: Graph) -> None:
        self.graph = graph

    def run_spfa(self, teg: TimeExpandedGraph) -> list[FlowEdge] | None:
        """Finds augmenting path with negative weights via SPFA."""
        dist: dict[TimeNode, float] = {teg.source: 0.0}
        parent_edge: dict[TimeNode, FlowEdge | None] = {teg.source: None}
        in_queue: set[TimeNode] = {teg.source}
        queue: deque[TimeNode] = deque([teg.source])

        while queue:
            curr = queue.popleft()
            in_queue.remove(curr)
            curr_dist = dist[curr]

            for edge in teg.adj.get(curr, []):
                if edge.capacity > 0:
                    neighbor = edge.v
                    candidate_cost = curr_dist + edge.cost
                    if (
                        neighbor not in dist
                        or candidate_cost < dist[neighbor]
                    ):
                        dist[neighbor] = candidate_cost
                        parent_edge[neighbor] = edge
                        if neighbor not in in_queue:
                            queue.append(neighbor)
                            in_queue.add(neighbor)

        if teg.sink not in parent_edge:
            return None

        path_edges: list[FlowEdge] = []
        curr_node = teg.sink
        while curr_node != teg.source:
            p_edge = parent_edge[curr_node]
            assert p_edge is not None
            path_edges.append(p_edge)
            curr_node = p_edge.u

        path_edges.reverse()
        return path_edges

    def route_fleet(self) -> dict[str, list[str]]:
        """Solves Min-Cost Max-Flow across TEG for all drones."""
        if not self.graph.start_hub or not self.graph.end_hub:
            return {}

        base_horizon = max(
            25, len(self.graph.hubs) * 2 + self.graph.drone_count * 2
        )
        teg = TimeExpandedGraph(self.graph, horizon=base_horizon)

        drones_routed = 0
        while drones_routed < self.graph.drone_count:
            augmenting_path = self.run_spfa(teg)
            while augmenting_path is None:
                teg.extend_to_horizon(teg.horizon + 15)
                augmenting_path = self.run_spfa(teg)
                if teg.horizon > 300:
                    break

            if augmenting_path is None:
                break

            for edge in augmenting_path:
                edge.capacity -= 1
                if edge.undo_link is not None:
                    edge.undo_link.capacity += 1

            drones_routed += 1

        if drones_routed < self.graph.drone_count:
            return {}

        return self._extract_drone_schedules(teg)

    def _extract_drone_schedules(
        self, teg: TimeExpandedGraph
    ) -> dict[str, list[str]]:
        """Decomposes residual flow network into individual drone paths."""
        assert self.graph.start_hub is not None
        assert self.graph.end_hub is not None
        start_name = self.graph.start_hub.name
        end_name = self.graph.end_hub.name

        flow_usage: dict[FlowEdge, int] = {}
        for edges in teg.adj.values():
            for edge in edges:
                if edge.flow > 0:
                    flow_usage[edge] = edge.flow

        drone_paths: dict[str, list[str]] = {}
        for i in range(self.graph.drone_count):
            drone_id = f"D{i + 1}"
            path: list[str] = [start_name]
            curr_hub = start_name
            turn = 0

            while curr_hub != end_name and turn <= teg.horizon:
                out_node = TimeNode(curr_hub, turn, True)
                next_hub = curr_hub
                advanced = False
                candidate_edges = teg.adj.get(out_node, [])
                sorted_edges = sorted(
                    candidate_edges,
                    key=lambda e: 1 if e.v.hub_name == curr_hub else 0,
                )
                for edge in sorted_edges:
                    if (
                        flow_usage.get(edge, 0) > 0
                        and edge.v.turn == turn + 1
                    ):
                        flow_usage[edge] -= 1
                        next_hub = edge.v.hub_name
                        advanced = True
                        break

                if not advanced:
                    break

                curr_hub = next_hub
                turn += 1
                path.append(curr_hub)

            drone_paths[drone_id] = path

        return drone_paths

    def find_shortest_path(self) -> list[str] | None:
        """Backward-compatibility helper returning a single path."""
        schedules = self.route_fleet()
        if not schedules:
            return None
        return schedules.get("D1")
