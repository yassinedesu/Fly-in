# Fly-in — Full Breakdown + 7-Day Build Plan

*A guidance document (no code, no repo structure). Goal: understand the subject completely, learn exactly what you need in Python, and follow a day-by-day plan you can finish in ≤7 days at 8h/day.*

---

## PART 1 — What this project actually is

### The one-sentence version
You are given a **graph of zones** and a number of **drones** that all start in one zone (`start`) and must all reach another zone (`end`). Your job: move **all** drones from start to end in the **fewest total simulation turns**, while never breaking the capacity and movement rules.

### This is the "lem-in" problem in disguise
This is a well-known algorithmic exercise (ants moving through rooms) with a drone reskin, **plus two extra layers** that make it harder:

1. **Capacities.** Every zone can hold at most `max_drones` drones at once (default **1**), and every connection can carry at most `max_link_capacity` drones per turn (default **1**). Start and end are unlimited.
2. **Weights.** Moving *into* a `restricted` zone costs **2 turns** instead of 1. `priority` zones cost 1 but should be *preferred*. `blocked` zones can never be entered or crossed.

Because most zones default to capacity 1, you **cannot** just send every drone down the single shortest path — they'd queue up and it would be slow (or deadlock). The entire challenge is **parallelism under constraints**.

### The core insight (read this twice)
The number of turns to move N drones is **not** the length of the shortest path. Roughly:

> **turns ≈ max over the paths you use of ( path_cost + drones_on_that_path − 1 )**

So a *slightly longer second path* can **lower** the total by taking load off the first path. You trade path length for throughput. Finding the right *set* of paths and the right *split* of drones across them is the optimization.

**Tiny concrete example** (easy map 1: `start → w1 → w2 → goal`, 2 drones, all capacity 1):
- Turn 1: D1→w1
- Turn 2: D1→w2, D2→w1  ← D2 can enter w1 because D1 just vacated it (the "conveyor" rule)
- Turn 3: D1→goal, D2→w2
- Turn 4: D2→goal

That's **4 turns** = path_length(3) + (drones−1)(1). Target for that map is ≤6, so you have room — but on capacity-limited maps you'll *need* multiple paths.

### Why the provided maps are shaped the way they are
I read all of them. They're teaching you specific lessons:
- **easy/linear, fork, capacity** → basic movement, splitting across two paths, and respecting `max_drones`/`max_link_capacity`.
- **medium/dead_end_trap** → your pathfinder must not walk drones into dead ends.
- **medium/circular_loop** → your pathfinder must not loop forever (cycle handling / visited sets).
- **medium/priority_puzzle** → weights matter; the "fast" priority path should win over the "slow" restricted path. This is where **Dijkstra** (weighted) beats plain BFS (unweighted).
- **hard/capacity_hell** → single-capacity gates + waiting areas. You *must* use multiple parallel routes and pipeline drones through them, or you'll blow the turn target. This is the map that proves you need real flow + scheduling, not one path.
- **hard/maze_nightmare, ultimate_challenge** → everything at once, many decoy paths.
- **challenger/impossible_dream (25 drones)** → optional, bonus only.

---

## PART 2 — The subject, precisely (every rule that will bite you)

### Input format rules you must parse and validate
- First line: `nb_drones: <positive integer>`. Must handle **any** number of drones.
- Exactly **one** `start_hub:` and **one** `end_hub:`. Zones are `hub: <name> <x> <y> [metadata]`.
- Zone **names**: any characters **except dashes and spaces**, and must be **unique**. Coordinates are always integers.
- Metadata is optional, in `[...]`, tags in **any order**: `zone=<type>`, `color=<value>`, `max_drones=<n>`.
- Zone types: `normal` (default), `blocked`, `restricted`, `priority`. **Any other type is a parse error.**
- Connections: `connection: <name1>-<name2> [max_link_capacity=<n>]`, **bidirectional**. Both zones must already be defined. `a-b` and `b-a` are **duplicates** and must be rejected.
- Capacities (`max_drones`, `max_link_capacity`) must be **positive integers**.
- `max_drones` on start/end is **ignored** (not an error).
- Lines starting with `#` are comments. Blank lines exist in the real maps — handle them.
- Any other parse error must **stop the program** with a clear message naming the **line and the cause**.

> The provided maps put metadata after the coordinates and sometimes give connections a `[max_link_capacity=...]`. Metadata is always inside brackets, so a safe move is: split the line's bracket part off first, then parse the rest.

### Movement & turn mechanics (the simulation heart)
- Turns are discrete. Each turn, each drone may: move to one adjacent zone, continue a multi-turn move, or stay.
- **Cost is based on the destination zone type**: normal 1, priority 1, restricted **2**, blocked = never.
- **Restricted = 2-turn move.** The drone spends one turn "on the connection" (in transit) and **must** arrive the next turn — it **cannot** wait on the connection for space to open up. Plan capacity *before* launching a drone toward a restricted zone.
- **The conveyor rule:** drones leaving a zone free its capacity *the same turn*, so a chain of drones can all step forward together — as long as, after everyone leaving has left, the destination still has room.
- A drone may **never** enter a zone that would exceed its `max_drones`, and no more than `max_link_capacity` drones may cross the same connection in the same turn.

### Output format (must be exact — peers/graders check this)
- One line per turn.
- Each moving drone printed space-separated as `D<id>-<destination>`.
- While a drone is mid-flight toward a restricted zone, print `D<id>-<connection>` (the connection it's transiting), then `D<id>-<zone>` when it arrives.
- Drones that don't move that turn are **omitted**. Delivered drones are no longer printed.
- Simulation ends when **all** drones are at end.

### Hard project constraints (these are graded too)
- **Python 3.10+**, **fully object-oriented**, **fully type-safe**.
- Must pass **flake8** and **mypy** (the exact mypy flags are in the Makefile section of the subject; also try `--strict`).
- **No graph libraries** (no networkx, graphlib, etc.). You implement the graph and the algorithms yourself.
- Type hints everywhere, docstrings (PEP 257), graceful exception handling, context managers for files.
- A **Makefile** with `install / run / debug / clean / lint` (and optional `lint-strict`).
- A **README.md** with a specific italic first line, plus Description / Instructions / Resources sections, an explanation of your algorithm, how AI was used, and documentation of your visualization.
- **Visual representation** is mandatory: at minimum, colored terminal output showing drone movements and zone states.
- Peer review **can ask you to modify the code live** and to **explain any part**. Build it yourself and understand every line — this is non-negotiable for passing.

---

## PART 3 — The algorithm, and where Dijkstra actually fits

Think of the solver as **three stages**. Dijkstra lives in stage 1.

### Stage 1 — Path discovery (Dijkstra is the primitive here)
- **Dijkstra** finds the lowest-*cost* path from start to end, where an edge's weight = the destination zone's cost (1 or 2), blocked zones excluded, and priority zones preferred on ties. Plain BFS would ignore the restricted=2 weighting, which is exactly what the priority_puzzle map punishes — so weighted Dijkstra is the correct primitive.
- But you need **several** paths, not one. The classic technique: find a path, then search again on a **residual graph** (the max-flow idea) so the next path complements the first instead of duplicating it. Repeat until no more useful paths exist.
- To respect **zone capacity** (`max_drones`) inside this, use the **node-splitting trick**: split each zone into an "in" node and an "out" node joined by an edge whose capacity = the zone's `max_drones`. Now zone capacity becomes an ordinary edge capacity, and standard flow logic handles it.

**Two honest tiers of ambition:**
- **Tier A (enough to pass, very achievable in the week):** find several **disjoint-ish paths** with residual-graph search (Edmonds-Karp style, but using Dijkstra instead of BFS so weights count). Node-disjointness naturally respects capacity-1 zones. This meets the benchmarks on nearly all maps.
- **Tier B (for "perfect"/bonus):** full **capacity-aware min-cost flow** (successive shortest paths with Dijkstra) that also exploits zones with capacity >1. More optimal, more work. Only chase this if Tier A is solid and you have time.

### Stage 2 — Drone distribution (a greedy assignment, not an algorithm you look up)
Given the paths from stage 1 and their costs, assign drones to paths to **minimize the makespan**:
- Repeatedly hand the next drone to whichever path gives the **smallest resulting finish time** (`path_cost + drones_already_assigned`).
- Only **add another path** to the mix if doing so **lowers** the overall max. A longer path is worth using only when it relieves a crowded shorter one.

### Stage 3 — Simulation / scheduling (correctness-heavy, this is where bugs live)
A turn engine that, each turn:
- Advances drones one step along their assigned path when the destination has room and the connection isn't over capacity.
- Enforces the **conveyor rule** (vacating frees space this turn), zone caps, and edge caps.
- Handles the **2-turn restricted transit** (occupy connection this turn, must land next turn).
- Lets a drone **wait** when blocked (never crash, never deadlock).
- Emits the exact output line and stops when all delivered.

> If you get stage 3 slightly wrong, your turn counts and output format break even when your paths are perfect. Budget real time for it and test it hard.

---

## PART 4 — What you must know in Python (learn/refresh this first)

You don't need everything at once. Here's the map of concepts → why you need them.

**Object orientation (required by the subject):**
- Classes, `__init__`, methods, composition; `@dataclass` for clean data-holding types (zones, drones, edges); `@property` where handy.
- `enum.Enum` for zone types (normal/blocked/restricted/priority) instead of raw strings.
- Optionally `abc.ABC` if you want to plug in more than one pathfinding strategy behind a common interface.

**Typing (required, mypy must pass):**
- Modern 3.10 hints: built-in generics (`list[str]`, `dict[str, Zone]`), `X | None` instead of `Optional`.
- `typing` extras when needed: `TypeAlias`, `Iterable`, `Iterator`, `Callable`.
- Understand what makes mypy complain: missing return types, `None` where a value is expected, untyped defs (the mandatory flags include `--disallow-untyped-defs`).

**Parsing & I/O:**
- File reading with a **context manager** (`with open(...) as f:`).
- `str.strip()`, `str.split()`, `str.startswith("#")`, splitting off the `[...]` metadata.
- `re` (regular expressions) for validating/extracting metadata tags cleanly.
- **Custom exception classes** + raising them with a message that includes the line number and cause.

**Data structures & the algorithm toolkit:**
- `dict` and `set` (adjacency lists, visited sets, name→zone lookups).
- `collections.deque` — the queue for BFS (and Edmonds-Karp).
- `heapq` — the priority queue that makes **Dijkstra** work. Learn the "push (cost, node), pop smallest, skip stale entries" pattern.
- The concepts: **graph as adjacency list**, **BFS**, **Dijkstra**, **residual graph / augmenting paths (max-flow / Edmonds-Karp)**, **node-splitting for node capacities**, and (Tier B) **successive-shortest-paths min-cost flow**. Understand them well enough to explain on a whiteboard.

**Tooling:**
- `venv` (isolation), `git` (submit at repo root), `make` (the required targets).
- `flake8` and `mypy` with the subject's flags; run them constantly, not at the end.
- `pytest` or `unittest` for your own tests (not graded, but they'll save you).
- Terminal color: ANSI escape codes are enough (a lib like `colorama`/`rich` is fine too — those aren't "graph logic", so they don't violate the no-library rule). A graphical UI (`tkinter`/`pygame`) is optional extra credit, not required.

---

## PART 5 — The 7-Day Plan (8h/day ≈ 56 hours)

Each day ends with a **concrete deliverable** so you always have something working. The order is deliberate: you build the pipeline end-to-end early on the easy case, then deepen it.

### Day 1 — Understand + environment + Python foundations
- **Morning:** Re-read the subject. Hand-solve `easy/01`, `easy/02`, and `medium/03` on paper — write the turn-by-turn moves yourself. You cannot code what you can't do by hand.
- **Afternoon:** Set up `venv`, `git`, a `.gitignore`, and a Makefile skeleton with all targets (even if `run` just prints for now). Get `make lint` (flake8 + mypy) passing on a trivial typed function.
- **Learn/refresh:** OOP + dataclasses + enums, 3.10 type hints, custom exceptions, `with open`, `heapq` and `deque` basics.
- ✅ **Deliverable:** clean linting environment; you can hand-trace the optimal solution of 3 maps.

### Day 2 — Parser + graph model
- Decide your entities conceptually (a zone, a connection/edge, the whole graph, a drone) — model them as typed classes.
- Write the parser with **full validation**: every rule in Part 2. Make error messages name the line and cause.
- Test against **all 10 provided maps** (they must all parse), then write ~5 deliberately broken maps (bad type, duplicate connection, missing start, negative capacity, dash in a name) and confirm each fails cleanly.
- ✅ **Deliverable:** every valid map loads into your graph model; every malformed map is rejected gracefully.

### Day 3 — Dijkstra + single-path pipeline
- Implement **weighted Dijkstra** with `heapq`: edge weight = destination zone cost, exclude blocked, prefer priority on ties, and be cycle-safe (handles `circular_loop`).
- Wire a **minimal simulator** that moves all drones down that one path with the conveyor rule, and prints the output format.
- ✅ **Deliverable:** easy/01 and easy/02 solved end-to-end and printed correctly (even if not yet optimal on multi-path maps). Learn Edmonds-Karp / residual-graph concept this evening.

### Day 4 — Multiple paths + drone distribution
- Upgrade path discovery to find a **set** of complementary paths via residual-graph search (Tier A: Dijkstra-based, disjoint-ish). Add **node-splitting** so `max_drones` is respected.
- Implement the **greedy distribution** (assign each drone to the path minimizing its finish time; add a path only when it helps).
- ✅ **Deliverable:** for any map you can produce a valid set of paths + a per-drone route plan. Verify the plan's *predicted* turn count looks sane vs. the targets.

### Day 5 — Full simulation engine + output
- Build the real turn engine: per-turn zone caps, per-turn edge caps (`max_link_capacity`), conveyor rule, **restricted 2-turn transit** with the connection-name output, waiting when blocked, stop when all delivered.
- Validate **turn counts** against the targets on all **easy + medium** maps.
- ✅ **Deliverable:** easy + medium maps solved **within the target turns**, output format exact.

### Day 6 — Hard maps + capacity correctness + visualization
- Run the hard maps. Expect capacity/timing bugs (`capacity_hell` will expose them). Fix scheduling until you hit/approach targets.
- Add the mandatory **colored terminal visualization** (zone states + drone moves per turn).
- Harden: run `mypy --strict`, clear all flake8, add docstrings, make sure nothing crashes on weird input.
- ✅ **Deliverable:** hard maps within targets; visualization working; lint clean.

### Day 7 — README, tests, self-review, buffer
- Write the **README** exactly to spec (italic first line; Description / Instructions / Resources; algorithm explanation; **how AI was used**; visualization docs).
- Add your own **test maps** and a few unit tests.
- **Rehearse the peer review:** be ready to explain any function and to make a small live change (e.g., "add a new zone type", "change the output", "store an extra field"). Practice one such change.
- Use leftover time as buffer. **Only if everything above is solid**, attempt the challenger map or Tier-B min-cost flow.
- ✅ **Deliverable:** submittable project — everything at repo root, `make run` works, README complete.

### Day 8 — Pure buffer / submit
Spillover, final flake8/mypy pass, final read-through, submit.

---

## PART 6 — Traps that cost people days (pin these to your wall)
- **Duplicate connections:** `a-b` == `b-a`. Reject on parse.
- **Cost is the destination's type**, not the source's. Restricted-*destination* moves cost 2.
- **Restricted transit can't wait on the wire** — only launch when the destination will have room next turn.
- **Conveyor rule:** check capacity *after* accounting for drones leaving this same turn, or you'll wrongly block valid moves.
- **start/end ignore `max_drones`** — don't cap them.
- **`blocked` = never entered or crossed** — exclude from the graph search entirely.
- **priority is a soft preference**, cost still 1 — implement as a tie-breaker, not a cost change that distorts distances.
- **Output:** omit non-movers; stop printing delivered drones; one line per turn; exact `D<id>-<dest>` format.
- **Don't recompute paths every turn** if you don't need to — cache the plan; the subject explicitly asks you about caching vs. recomputing.
- **You must explain everything.** If you lean on AI, make sure you can defend every line, or you fail the review (the subject's own AI chapter warns about exactly this).

---

## PART 7 — If you fall behind (priority triage)
Ship in this order; each stage is independently defensible at review:
1. **Parser + validation** (correctness gate — without it nothing runs).
2. **Dijkstra + single-path simulator** with correct output (passes easy maps).
3. **Multi-path + distribution** (passes medium + most hard).
4. **Capacity-aware scheduling polish** (hits hard targets).
5. **Visualization + README + tests** (grading requirements — don't skip; a working solver with no README/visual still loses points).
6. **Tier-B min-cost flow / challenger** (bonus only).

A clean, fully-understood Tier-A solution that meets targets and has a solid README beats a half-finished Tier-B one every time.
