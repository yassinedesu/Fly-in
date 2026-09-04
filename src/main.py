import sys
import argparse
import arcade
from parsing import Parser, ParsingError
from pathfinder import Pathfinder
from stimulation import Simulator
from visualization import FlyInVisualizer

def main():
    cli_parser = argparse.ArgumentParser(description="Fly-in Drone Routing")
    cli_parser.add_argument("map_file", type=str, help="Path to the map file")
    cli_parser.add_argument("--capacity-info", action="store_true", help="Display capacity info per turn")
    cli_parser.add_argument("--visualize", action="store_true", help="Launch the Arcade visualizer")
    args = cli_parser.parse_args()

    file_parser = Parser()
    
    try:
        graph = file_parser.parse_file(args.map_file)
        
        # 1. Discover the path
        finder = Pathfinder(graph)
        optimal_path = finder.find_shortest_path()
        
        if optimal_path is None:
            print("Error: No valid path found from start to end.")
            sys.exit(1)
            
        # 2. Run the simulation engine
        sim = Simulator(graph, optimal_path, capacity_info=args.capacity_info)
        simulation_history = sim.run_single_path_pipeline()
        
        # 3. Pass actual historical data to the visualizer
        if args.visualize:
            window = FlyInVisualizer(graph, simulation_data=simulation_history)
            arcade.run()
            
    except ParsingError as e:
        print(e)
        sys.exit(1)

if __name__ == "__main__":
    main()