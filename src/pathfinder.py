import heapq
from graph import Graph, ZoneType

class Pathfinder:
    def __init__(self, graph: Graph):
        self.graph = graph

    def get_zone_cost(self, zone: ZoneType) -> tuple[int, int]:
        """
        Returns (turn_cost, priority_bonus).
        Priority bonus is negative so heapq naturally sorts it first on cost ties.
        """
        if zone == ZoneType.RESTRICTED:
            return 2, 0
        if zone == ZoneType.PRIORITY:
            return 1, -1
        return 1, 0

    def find_shortest_path(self) -> list[str] | None:
        """
        Executes Dijkstra's algorithm to find the optimal single path from start to end.
        """
        if not self.graph.start_hub or not self.graph.end_hub:
            return None

        start = self.graph.start_hub.name
        goal = self.graph.end_hub.name

        # Queue stores tuples of: (total_cost, priority_score, current_node, path_history)
        queue: list[tuple[int, int, str, list[str]]] = [(0, 0, start, [start])]
        visited: set[str] = set()

        while queue:
            cost, prio_score, current, path = heapq.heappop(queue)

            if current == goal:
                return path

            if current in visited:
                continue
            
            visited.add(current)

            for edge in self.graph.adj.get(current, []):
                neighbor_name = edge.v
                neighbor_hub = self.graph.hubs[neighbor_name]

                if neighbor_hub.zone == ZoneType.BLOCKED:
                    continue

                if neighbor_name not in visited:
                    turn_cost, prio_bonus = self.get_zone_cost(neighbor_hub.zone)
                    new_cost = cost + turn_cost
                    new_prio = prio_score + prio_bonus
                    
                    heapq.heappush(
                        queue, 
                        (new_cost, new_prio, neighbor_name, path + [neighbor_name])
                    )
        return None