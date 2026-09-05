"""Entry point for the Fly-in drone routing simulation."""

import sys
import argparse
import arcade
from parsing import Parser, ParsingError
from pathfinder import Pathfinder
from stimulation import Simulator
from visualization import FlyInVisualizer


def main() -> None:
    """Parses CLI arguments, calculates paths, and runs the simulation."""
    cli_parser = argparse.ArgumentParser(description="Fly-in Drone Routing")
    cli_parser.add_argument("map_file", type=str, help="Path to the map file")
    cli_parser.add_argument(
        "--capacity-info",
        action="store_true",
        help="Display capacity info per turn",
    )
    cli_parser.add_argument(
        "--visualize",
        action="store_true",
        help="Launch the Arcade visualizer",
    )
    args = cli_parser.parse_args()

    file_parser = Parser()

    try:
        graph = file_parser.parse_file(args.map_file)

        finder = Pathfinder(graph)
        drone_routes = finder.route_fleet()

        if not drone_routes:
            print("Error: No valid path found from start to end.")
            sys.exit(1)

        sim = Simulator(graph, drone_routes, capacity_info=args.capacity_info)
        simulation_history = sim.run_simulation()

        if args.visualize:
            FlyInVisualizer(
                graph,
                simulation_data=simulation_history,
                map_name=args.map_file,
            )
            arcade.run()

    except ParsingError as e:
        print(e)
        sys.exit(1)


if __name__ == "__main__":
    main()
