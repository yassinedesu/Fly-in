*This project has been created as part of the 42 curriculum by yael-kha.*

# Fly-in

An autonomous multi-drone routing and scheduling engine that navigates fleets through capacity-constrained networks with heterogeneous airspace zones in minimal simulation turns.

## Description

Fly-in addresses the Multi-Agent Pathfinding (MAPF) problem across topological networks under strict physical and temporal constraints. The objective is to route a fleet of $N$ drones from a designated `start_hub` to an `end_hub` while eliminating path conflicts, deadlocks, and capacity violations.

The simulation operates in discrete turns and models multiple airspace conditions:

* **Normal Zones**: Standard transit requiring 1 turn.


* **Priority Zones**: Preferred routes requiring 1 turn with reduced routing cost weights.


* **Restricted Zones**: Sensitive air corridors requiring a 2-turn traversal where drones occupy transit links between turns.


* **Blocked Zones**: Inaccessible hubs that forbid entry.


* **Capacity Constraints**: Strict limits on simultaneous zone occupancy (`max_drones`) and bidirectional link traversals (`max_link_capacity`).



The engine features a custom Min-Cost Max-Flow solver built from scratch without external graph libraries, alongside an interactive, hardware-accelerated 2D visualizer.

---

## Instructions

### Prerequisites

* Python 3.10 or later


* A POSIX-compliant environment with `make` (Linux/macOS)

### Installation

Clone the repository and install the dependencies:

```bash
git clone <repository_url>
cd fly-in
make install

```

Or install via `pip`:

```bash
pip install -r requirements.txt

```

### Execution

Run the simulation on any valid map file:

```bash
# Using Makefile
make run MAP=maps/easy/01_linear_path.txt

# Directly via Python CLI
python3 main.py maps/easy/01_linear_path.txt

```

To launch the simulation with the interactive 2D GUI, append `--visualize`:

```bash
python3 main.py maps/easy/01_linear_path.txt --visualize

```

### Development & Verification

The project is fully typed and adheres to PEP 8 / Flake8 standards:

```bash
make lint         # Runs Flake8 and standard MyPy checks
make lint-strict  # Runs MyPy in strict mode and Flake8
make clean        # Removes bytecode and cache directories
make debug        # Runs execution under Python's pdb debugger

```

---

## Algorithm Choices & Implementation Strategy

Solving multi-drone routing while avoiding collisions and respecting concurrent edge/vertex capacities cannot be accomplished with static shortest-path algorithms like A* or Dijkstra. Fly-in models the problem as **Min-Cost Max-Flow (MCMF) over a Time-Expanded Graph (TEG)**.

```
                     Time Step t-1                     Time Step t
                 +-------------------+             +-------------------+
Wait Edge:       | Hub A (OUT, t-1)  | ----------> |  Hub A (IN, t)    |
                 +-------------------+   (Cap,Cost)+-------------------+
                                                             |
                                                       Vertex Splitting
                                                       (Node Capacity)
                                                             v
                 +-------------------+  Transit    +-------------------+
Link Edge:       | Hub A (OUT, t-1)  | ----------> |  Hub B (IN, t)    |
                 +-------------------+  (Link Cap) +-------------------+

```

### 1. Time-Expanded Network Construction

The physical network is unrolled across discrete time steps $t \in [0, H]$ up to a time horizon $H$. Every hub at turn $t$ is represented by discrete time nodes.

### 2. Vertex & Transit Splitting

* **Zone Capacities (`max_drones`)**: Each physical hub at time $t$ is split into an entry node (`TimeNode(hub, t, is_out=False)`) and an exit node (`TimeNode(hub, t, is_out=True)`). An internal directed edge links `IN -> OUT` with capacity equal to `max_drones` and cost `0`. Start and end hubs use infinite capacity (bounded by total fleet size).


* **Link Capacities (`max_link_capacity`)**: Physical connections between hubs $U$ and $V$ share a single capacity pool across opposite travel directions via a synchronized `SharedCapacity` reference.


* **2-Turn Restricted Corridors**: Entering a restricted hub requires two simulation steps. The graph creates intermediate transit nodes `TimeNode("U-V", t)` holding the drone in transit between $t-1$ and $t$, delivering it to the destination at turn $t+1$. Drones cannot pause or hold indefinitely on connection links.


* **Wait Edges**: Drones may remain stationary at a hub across turns via temporal wait links `TimeNode(hub, t-1, True) -> TimeNode(hub, t, False)`.



### 3. Min-Cost Augmentation via SPFA

A virtual source connects to `start_hub` at $t=0$, and exit nodes of `end_hub` across all turns connect to a global sink with costs scaled by turn index ($t \times 1000$).

* Augmenting paths are computed using the **Shortest Path Faster Algorithm (SPFA)** to accommodate negative residual edge weights caused by flow cancelation.


* Edge traversal costs prioritize movements: Priority zones have a lower traversal cost (`8`), Normal zones cost `10`, and Waiting costs `12` (disincentivizing idle delays).


* The objective function naturally minimizes arrival turn across all drones simultaneously.



### 4. Dynamic Horizon Scaling

If $N$ augmenting paths cannot be routed within the initial time horizon heuristic ($2 \times \vert{}V\vert{} + 2 \times N$), the graph automatically extends its unrolled time horizons in increments of 15 turns until all drones reach the sink.

### 5. Conflict-Free Flow Decomposition

Once total flow equals the fleet size, residual flow along forward edges is extracted into turn-by-turn coordinate schedules for each unique drone identifier ($D1, D2, \dots$).

---

## Visual Representation

The project includes an interactive graphical interface implemented with the Python `arcade` library (`visualization.py`):

* **Dual-Camera Coordinate Space**: An unprojected world camera renders simulation geometry, while a fixed GUI camera displays real-time metrics (current turn, delivered drones, controls).


* **Interpolated Motion**: Turn playback smoothly lerps drone positions between discrete coordinates using delta-time updates.


* **Hover Inspection & Tooltips**: Mouse-over collision detection checks distances to nodes and links, displaying dynamic metadata tooltips (zone type, custom colors, current occupancy vs. maximum capacity).


* **Custom Styling**: Renders custom map metadata colors, standard zone indicators (Normal: Gray, Restricted: Red, Priority: Green, Blocked: Dark Gray), and animated dynamic color tags (e.g., `RAINBOW`).



### Visualizer Keybindings

| Key / Action | Function |
| --- | --- |
| `SPACE` | Toggle Play / Pause

 |
| `RIGHT ARROW` | Step forward one turn

 |
| `LEFT ARROW` | Step backward one turn

 |
| `R` | Restart simulation from turn 0

 |
| `F` | Refocus and center camera view

 |
| `Left Mouse Drag` | Pan viewport across the map

 |
| `Mouse Scroll` | Zoom into / out of cursor position

 |
| `ESCAPE` | Close visualizer window

 |

---

## Example Input & Expected Output

### Input Map File (`simple_network.txt`)

```txt
# Fleet definition
nb_drones: 2

# Zones
start_hub: depot 0 0 [color=green]
end_hub: delivery_dock 6 0 [color=gold]
hub: corridor_a 2 2 [zone=priority max_drones=1]
hub: corridor_b 2 -2 [zone=normal max_drones=1]
hub: bottleneck 4 0 [zone=normal max_drones=1]

# Connections
connection: depot-corridor_a
connection: depot-corridor_b
connection: corridor_a-bottleneck
connection: corridor_b-bottleneck
connection: bottleneck-delivery_dock

```

### Command

```bash
python3 main.py simple_network.txt

```

### Standard Output

```text
D1-corridor_a D2-corridor_b
D1-bottleneck
D1-delivery_dock D2-bottleneck
D2-delivery_dock

```

Each line represents an executed simulation turn, listing all drones that moved in the format `D<ID>-<destination>`. Drones staying stationary during a turn are omitted from that line.

---

## Resources

### References

* **Network Flows: Theory, Algorithms, and Applications** (Ravindra K. Ahuja, Thomas L. Magnanti, James B. Orlin) – Foundational formulation of time-expanded networks and residual graph augmentation.
* **Shortest Path Faster Algorithm (SPFA)** – F. Yen (1970) / Jiang Dingwei (1994) – Efficient negative-cycle-tolerant single-source shortest path algorithm on sparse DAG-like flow networks.
* **Multi-Agent Pathfinding (MAPF) Research** – Time-space conflict avoidance models and vertex capacity splitting.

### AI Usage Disclosure

In compliance with the 42 curriculum guidelines, generative AI was utilized strictly as an advisory and conceptual learning partner for the following tasks:

* **Algorithm Information**: Researching theoretical formulations for Multi-Agent Pathfinding (MAPF), comparing Time-Expanded Graph models against discrete-time search algorithms, and evaluating Min-Cost Max-Flow feasibility under vertex and link capacity bounds.


* **Concept Explanations**: Clarifying the mechanics of residual graphs, vertex splitting (in/out node separation) for physical zone capacity modeling, and SPFA queue dynamics in the presence of negative edge weights from back-propagation.


* **Code Review & Edge Case Analysis**: Reviewing manually written code for logical edge cases, suggesting potential bottlenecks in graph construction, and verifying adherence to strict MyPy type safety and PEP 8 / Flake8 style standards.

