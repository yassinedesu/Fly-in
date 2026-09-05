"""Simulation engine managing drone movements and zone capacity rules."""

from __future__ import annotations
from graph import Graph


class Simulator:
    """Executes and records turn-by-turn fleet movements."""

    def __init__(
        self,
        graph: Graph,
        drone_routes: dict[str, list[str]],
        capacity_info: bool = False,
    ) -> None:
        self.graph = graph
        self.drone_routes = drone_routes
        self.capacity_info = capacity_info
        self.max_turns = (
            max(len(route) - 1 for route in drone_routes.values())
            if drone_routes
            else 0
        )
        self.history: list[dict[str, str]] = []

    def run_simulation(self) -> list[dict[str, str]]:
        """Runs the multi-drone simulation and outputs turn movements."""
        assert self.graph.start_hub is not None
        assert self.graph.end_hub is not None
        start_name = self.graph.start_hub.name
        end_name = self.graph.end_hub.name

        current_state = {
            drone_id: start_name for drone_id in self.drone_routes
        }
        self.history.append(current_state.copy())

        for t in range(1, self.max_turns + 1):
            moves_this_turn: list[str] = []
            turn_state: dict[str, str] = {}

            for drone_id, route in self.drone_routes.items():
                curr_loc = route[t] if t < len(route) else end_name
                prev_loc = current_state[drone_id]
                turn_state[drone_id] = curr_loc

                if curr_loc != prev_loc and prev_loc != end_name:
                    moves_this_turn.append(f"{drone_id}-{curr_loc}")

            current_state = turn_state
            self.history.append(current_state.copy())

            if moves_this_turn:
                print(" ".join(moves_this_turn))

            if self.capacity_info:
                occupancy: dict[str, int] = {}
                for hub_name in current_state.values():
                    if hub_name not in (start_name, end_name):
                        occ = occupancy.get(hub_name, 0) + 1
                        occupancy[hub_name] = occ

                for hub_name, hub in self.graph.hubs.items():
                    if not hub.is_start and not hub.is_end:
                        occ = occupancy.get(hub_name, 0)
                        print(
                            f"  > Zone {hub_name}: "
                            f"{occ}/{hub.max_drones} drones"
                        )

        return self.history

    def run_single_path_pipeline(self) -> list[dict[str, str]]:
        """Backward-compatibility wrapper for single path execution."""
        return self.run_simulation()
