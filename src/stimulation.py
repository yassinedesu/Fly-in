from graph import Graph

class Simulator:
    def __init__(self, graph: Graph, path: list[str], capacity_info: bool = False):
        self.graph = graph
        self.path = path
        self.capacity_info = capacity_info
        self.turns = 0
        
        # Initialize all drones at the start hub
        self.drones = {f"D{i+1}": self.graph.start_hub.name for i in range(self.graph.drone_count)}
        self.delivered = set()
        self.history = [self.drones.copy()]

    def run_single_path_pipeline(self) -> list[dict[str, str]]:
        end_zone = self.graph.end_hub.name
        
        while len(self.delivered) < self.graph.drone_count:
            self.turns += 1
            moves_this_turn = []
            
            # Sort drones closest to the end first to satisfy the conveyor rule
            active_drones = [d for d in self.drones.items() if d[0] not in self.delivered]
            sorted_drones = sorted(active_drones, key=lambda item: self.path.index(item[1]), reverse=True)
            
            # Track current zone occupancy to enforce max_drones
            occupancy = {
                node: sum(1 for loc in self.drones.values() if loc == node and loc not in (end_zone, self.graph.start_hub.name)) 
                for node in self.path
            }
            
            for drone_id, current_loc in sorted_drones:
                current_idx = self.path.index(current_loc)
                next_loc = self.path[current_idx + 1]
                next_hub = self.graph.hubs[next_loc]
                
                # Check capacity (end hub has infinite capacity)
                has_capacity = next_hub.is_end or (occupancy.get(next_loc, 0) < next_hub.max_drones)
                
                if has_capacity:
                    if not next_hub.is_end and not current_loc == self.graph.start_hub.name:
                        occupancy[current_loc] -= 1
                    if not next_hub.is_end:
                        occupancy[next_loc] += 1
                        
                    self.drones[drone_id] = next_loc
                    moves_this_turn.append(f"{drone_id}-{next_loc}")
                    
                    if next_hub.is_end:
                        self.delivered.add(drone_id)
                        
            if moves_this_turn:
                print(" ".join(moves_this_turn))
                
                # Live-coding requirement from the correction sheet
                if self.capacity_info:
                    for node in self.path:
                        hub = self.graph.hubs[node]
                        if not hub.is_start and not hub.is_end:
                            print(f"  > Zone {node}: {occupancy.get(node, 0)}/{hub.max_drones} drones")
                            
            self.history.append(self.drones.copy())
            
        return self.history