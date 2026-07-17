# End-to-End Walkthrough: `03_priority_puzzle.txt`

> This document traces a **real example** through every file in the project,
> from the raw map file to the final animated output.
> Written in simple English for the corrector.

---

## The Map File

We use `maps/medium/03_priority_puzzle.txt`:

```
# Medium Level 3: Priority zones create optimal path challenges
nb_drones: 5

start_hub: start 0 0 [color=green]
hub: slow_path1 1 -1 [zone=restricted color=red]
hub: slow_path2 2 -1 [color=red]
hub: fast_junction 1 0 [zone=priority color=blue max_drones=2]
hub: fast_path 2 0 [zone=priority color=blue]
hub: merge_point 3 0 [color=yellow max_drones=3]
end_hub: goal 4 0 [color=green]

connection: start-slow_path1
connection: start-fast_junction
connection: slow_path1-slow_path2
connection: slow_path2-merge_point
connection: fast_junction-fast_path
connection: fast_path-merge_point
connection: merge_point-goal [max_link_capacity=2]
```

### What the map looks like (text diagram)

```
                           FAST ROUTE (priority, 1-turn per step)
                   ┌──────────────────┐    ┌──────────────┐
                   │  fast_junction    │───▶│  fast_path   │──┐
                   │  (priority, cap=2)│    │  (priority)  │  │
                   └──────────────────┘    └──────────────┘  │
                         ▲                                    │
 ┌────────┐              │                              ┌─────▼─────┐    ┌────────┐
 │ start  │──────────────┘                              │merge_point│═══▶│  goal  │
 │(0,0)   │──────────────┐                              │ (cap=3)   │    │(4,0)   │
 └────────┘              │                              └─────▲─────┘    └────────┘
                         ▼                                    │
                   ┌──────────────────┐    ┌──────────────┐  │
                   │  slow_path1      │───▶│  slow_path2  │──┘
                   │  (restricted, 2T)│    │  (normal)    │
                   └──────────────────┘    └──────────────┘
                           SLOW ROUTE (restricted = 2 turns for first hop)

   ═══▶  means max_link_capacity=2 (two drones can cross at the same time)
```

There are **2 routes** from `start` to `goal`:
- **Fast route:** start → fast_junction → fast_path → merge_point → goal (cost = 4 turns, all priority/normal zones)
- **Slow route:** start → slow_path1 → slow_path2 → merge_point → goal (cost = 5 turns, because slow_path1 is restricted = 2 turns)

Key constraints:
- `fast_junction` can hold **2 drones** at once.
- `merge_point` can hold **3 drones**.
- The `merge_point → goal` connection has **capacity 2** (two drones can cross it per turn).
- `slow_path1` is **restricted** — entering it costs 2 turns (1 turn on the connection, 1 turn to arrive).

---

## Step 1 — `main.py`: The Entry Point

When you run `python3 main.py maps/medium/03_priority_puzzle.txt`, here is what happens:

```python
mapfile = sys.argv[1]                          # = "maps/medium/03_priority_puzzle.txt"
parse_map = MapParser()                        # Create a parser
nb, start, end, graph = parse_map.parse_file(mapfile)  # Parse the map
```

After this line, we have:
- `nb = 5` (five drones)
- `start = "start"`
- `end = "goal"`
- `graph` = a `Graph` object with 7 zones and 7 connections

Then:

```python
finder = MultiPathFinder(graph)                # Create the path finder
alloc = finder.drone_waste(start, end, nb)     # Allocate paths for 5 drones
sim = Simulation(graph, alloc.assignments)      # Create the simulation
turns = sim.run()                               # Run all turns
print(sim.format_turns(turns))                  # Print the output
```

Let's follow each step in detail.

---

## Step 2 — `models.py`: The Data Structures

Before we parse, let's understand what the parser will create.

### Zone dataclass

Each zone in our map becomes a `Zone` object:

| Zone name | x | y | zone_type | color | max_drones | is_start | is_end |
|-----------|---|---|-----------|-------|------------|----------|--------|
| `start` | 0 | 0 | normal | green | 1 | **True** | False |
| `slow_path1` | 1 | -1 | **restricted** | red | 1 | False | False |
| `slow_path2` | 2 | -1 | normal | red | 1 | False | False |
| `fast_junction` | 1 | 0 | **priority** | blue | **2** | False | False |
| `fast_path` | 2 | 0 | **priority** | blue | 1 | False | False |
| `merge_point` | 3 | 0 | normal | yellow | **3** | False | False |
| `goal` | 4 | 0 | normal | green | 1 | False | **True** |

### Connection dataclass

Each connection becomes a `Connection` object:

| node_a | node_b | max_link_capacity |
|--------|--------|-------------------|
| start | slow_path1 | 1 |
| start | fast_junction | 1 |
| slow_path1 | slow_path2 | 1 |
| slow_path2 | merge_point | 1 |
| fast_junction | fast_path | 1 |
| fast_path | merge_point | 1 |
| merge_point | goal | **2** |

### Graph class

The `Graph` object stores:
- `zones` dict — all 7 zones by name
- `links` dict — all 7 connections by frozenset key
- `adj` dict — the adjacency list (who is connected to who)
- `start = "start"`, `end = "goal"`, `nb_drones = 5`

The adjacency list for our map:

```
"start"         → [(slow_path1, conn1), (fast_junction, conn2)]
"slow_path1"    → [(start, conn1), (slow_path2, conn3)]
"slow_path2"    → [(slow_path1, conn3), (merge_point, conn4)]
"fast_junction" → [(start, conn2), (fast_path, conn5)]
"fast_path"     → [(fast_junction, conn5), (merge_point, conn6)]
"merge_point"   → [(slow_path2, conn4), (fast_path, conn6), (goal, conn7)]
"goal"          → [(merge_point, conn7)]
```

---

## Step 3 — `parser.py`: Reading the Map File

The parser reads `03_priority_puzzle.txt` line by line. Here is exactly what happens
for each meaningful line:

### Line 1: `# Medium Level 3: ...`
- The `#` makes this a comment. The parser strips everything after `#`, gets an empty string, and **skips it**.

### Line 2: `nb_drones: 5`
- Starts with `"nb_drones:"` → extract the number after `:`.
- `val = " 5"` → `int("5")` = **5**.
- `flight_map.nb_drones = 5`.

### Line 3: (empty)
- After stripping, empty → **skip**.

### Line 4: `start_hub: start 0 0 [color=green]`
- Starts with `"start_hub:"` → apply `ZONE_PAT` regex.
- Captures: `type_hub="start_hub"`, `name="start"`, `x="0"`, `y="0"`, `metadata="color=green"`.
- Coordinates `(0, 0)` — not seen before → OK, add to `list_coords`.
- `is_start = True` → set `flight_map.start = "start"`.
- Parse metadata: `{"color": "green"}`.
  - No `zone` key → default `type_zone = "normal"`.
  - No `max_drones` → default `max_drones = 1`.
  - `color = "green"` — valid color → OK.
- Create `Zone(name="start", x=0, y=0, zone_type="normal", color="green", max_drones=1, is_start=True, is_end=False)`.
- Call `flight_map.add_zone(zone)` → stores it in `zones["start"]` and creates `adj["start"] = []`.

### Line 5: `hub: slow_path1 1 -1 [zone=restricted color=red]`
- Starts with `"hub:"` → apply `ZONE_PAT` regex.
- Captures: `type_hub="hub"`, `name="slow_path1"`, `x="1"`, `y="-1"`, `metadata="zone=restricted color=red"`.
- Coordinates `(1, -1)` — unique → OK.
- `is_start = False`, `is_end = False`.
- Parse metadata: `{"zone": "restricted", "color": "red"}`.
  - `zone = "restricted"` — valid type → `type_zone = "restricted"`.
  - `color = "red"` — valid → OK.
- Create `Zone(name="slow_path1", x=1, y=-1, zone_type="restricted", color="red", max_drones=1)`.
- Add to graph.

### Lines 6–10: (same pattern)
Each hub line follows the same process. Notable outcomes:
- **Line 7** (`fast_junction`): `zone=priority`, `max_drones=2` → parsed and stored.
- **Line 9** (`merge_point`): `max_drones=3` → parsed and stored.
- **Line 10** (`goal`): `end_hub` → `flight_map.end = "goal"`.

### Line 12: `connection: start-slow_path1`
- Starts with `"connection:"` → apply `LINK_PAT` regex.
- Captures: `zone_a="start"`, `zone_b="slow_path1"`, `metaconn=None`.
- No metadata → default `max_cap = 1`.
- Both zones exist in `flight_map.zones` → OK.
- `conn_key = ("slow_path1", "start")` (alphabetical order) — not seen → OK, add.
- Create `Connection(node_a="start", node_b="slow_path1", max_link_capacity=1)`.
- Call `flight_map.add_link(conn)`:
  - Store in `links`.
  - `adj["start"]` gets `(slow_path1_zone, conn)`.
  - `adj["slow_path1"]` gets `(start_zone, conn)`.

### Lines 13–17: (same pattern)
Each connection is validated and added to the adjacency list.

### Line 18: `connection: merge_point-goal [max_link_capacity=2]`
- Metadata is present: `"max_link_capacity=2"`.
- Parse it → `{"max_link_capacity": "2"}` → `max_cap = 2`.
- Create `Connection(node_a="merge_point", node_b="goal", max_link_capacity=2)`.

### Final validation
After all lines:
- `flight_map.start` = `"start"` → OK (not None).
- `flight_map.end` = `"goal"` → OK (not None).

### Return value
```python
return (5, "start", "goal", flight_map)
#        ^     ^       ^        ^
#     drones  start   end    Graph object
```

---

## Step 4 — `pathfinder.py`: Finding the Best Routes

Back in `main.py`:
```python
finder = MultiPathFinder(graph)
alloc = finder.drone_waste(start="start", end="goal", nb_drones=5)
```

### 4.1 — `extra_path()`: Finding multiple paths

First, `drone_waste()` calls `extra_path()`, which calls `best_single_path()` repeatedly
to discover different routes.

#### First call: `best_single_path("start", "goal")` (no penalty)

This uses **Dijkstra's algorithm** with a priority queue (min-heap).

Initial state:
```
dist = {"start": 0, all others: 10⁹}
heap = [(0, 0, "start")]
```

**Pop (0, 0, "start"):**
- Neighbors: `slow_path1` (restricted, cost=2), `fast_junction` (priority, cost=1)
- `slow_path1`: dist = 0+2 = 2, priority_score = 0 → push (2, 0, "slow_path1")
- `fast_junction`: dist = 0+1 = 1, priority_score = 0+1 = 1 → push (1, -1, "fast_junction")

**Pop (1, -1, "fast_junction"):**
- Neighbors: `start` (already visited, dist=0 < 1), `fast_path` (priority, cost=1)
- `fast_path`: dist = 1+1 = 2, priority_score = 1+1 = 2 → push (2, -2, "fast_path")

**Pop (2, 0, "slow_path1"):**
- Neighbors: `start` (skip), `slow_path2` (normal, cost=1)
- `slow_path2`: dist = 2+1 = 3, priority_score = 0 → push (3, 0, "slow_path2")

**Pop (2, -2, "fast_path"):**
- Neighbors: `fast_junction` (skip), `merge_point` (normal, cost=1)
- `merge_point`: dist = 2+1 = 3, priority_score = 2 → push (3, -2, "merge_point")

**Pop (3, 0, "slow_path2"):**
- Neighbors: `slow_path1` (skip), `merge_point` (cost=1)
- `merge_point`: dist = 3+1 = 4, but we already have dist=3 → **skip** (not better)

**Pop (3, -2, "merge_point"):**
- Neighbors: `goal` (normal, cost=1)
- `goal`: dist = 3+1 = 4 → push (4, -2, "goal")

**Pop (4, -2, "goal"):**
- `zone == end` → **stop!**

Reconstruct path by following `prev` pointers:
```
goal ← merge_point ← fast_path ← fast_junction ← start
```

**Result: Path 1 = `["start", "fast_junction", "fast_path", "merge_point", "goal"]`**
- Cost = 4, priority_count = 2 (two priority zones)

#### Second call: `best_single_path("start", "goal", penalty)`

After finding path 1, the internal nodes (`fast_junction`, `fast_path`, `merge_point`)
get a penalty of +1 each. This pushes the algorithm to find an alternative route.

With the penalty, the slow route becomes competitive:
- Slow: start → slow_path1(cost 2) → slow_path2(cost 1) → merge_point(cost 1 + penalty 1) → goal(cost 1) = **6**
- Fast (penalized): start → fast_junction(cost 1 + penalty 1) → fast_path(cost 1 + penalty 1) → merge_point(cost 1 + penalty 1) → goal(cost 1) = **7**

**Result: Path 2 = `["start", "slow_path1", "slow_path2", "merge_point", "goal"]`**
- Real cost (without penalty) = 5

The two paths are sorted by `(cost, -priority_count, length)`:
1. Fast route: cost=4, priority=2
2. Slow route: cost=5, priority=0

### 4.2 — `drone_waste()`: Assigning drones to paths

Now `drone_waste()` assigns each of the 5 drones **one at a time**, choosing the path
that gives the fewest total turns when simulated.

The algorithm works greedily:

| Drone# | Try path 1 (fast) | Try path 2 (slow) | Best | Assignment |
|--------|-------------------|-------------------|------|------------|
| D1 | Simulate [fast] → turns? | Simulate [slow] → turns? | fast wins (shorter) | D1 → fast route |
| D2 | Simulate [fast,fast] → turns? | Simulate [fast,slow] → turns? | slow wins (avoids congestion) | D2 → slow route |
| D3 | ... | ... | fast route | D3 → fast route |
| D4 | ... | ... | fast route | D4 → fast route |
| D5 | ... | ... | slow route | D5 → slow route |

For each candidate assignment, a **full simulation** is run to count the turns.
This is the brute-force optimization — try both paths and keep the one with fewer turns.

**Final assignments:**
```
D1 → ["start", "fast_junction", "fast_path", "merge_point", "goal"]    (fast)
D2 → ["start", "slow_path1", "slow_path2", "merge_point", "goal"]     (slow)
D3 → ["start", "fast_junction", "fast_path", "merge_point", "goal"]    (fast)
D4 → ["start", "fast_junction", "fast_path", "merge_point", "goal"]    (fast)
D5 → ["start", "slow_path1", "slow_path2", "merge_point", "goal"]     (slow)
```

Result: `AllocationResult(assignments=[...5 paths...], nb_turns=6)`

---

## Step 5 — `simulator.py`: Running the Simulation

Back in `main.py`:
```python
sim = Simulation(graph, alloc.assignments)
turns = sim.run()
```

### Initialization

The `Simulation.__init__` creates:
- 5 `Drone` objects, each with their path and `path_index = 0` (at `start`).
- An occupancy map: `{"start": 5, all others: 0}` — all 5 drones start at `start`.

### Turn-by-turn execution

Each call to `sim.step()` processes drones in order (D1, D2, D3, D4, D5) and
checks if they can move.

---

#### Turn 1

Occupancy at start: `start=5`

| Drone | Current | Next | Can move? | Action |
|-------|---------|------|-----------|--------|
| D1 | start | fast_junction | fast_junction has cap=2, occ=0 → **yes** | Move. occ: start=4, fast_junction=1 |
| D2 | start | slow_path1 | slow_path1 is **restricted** → 2-turn move. occ=0, cap=1 → **yes** | Start transit. occ: start=3, slow_path1=1 |
| D3 | start | fast_junction | cap=2, occ=1 → **yes** (room for 1 more) | Would move, but... |

> **Wait** — D2's restricted zone move is special. The drone enters transit: it
> occupies `slow_path1` immediately (reserving the spot), but won't "arrive" until next turn.
> On the connection, the output is `D2-start-slow_path1`.

Actually, let me trace the real output. The simulation produced:

```
Turn 1: D1-fast_junction D2-start-slow_path1
```

So only D1 and D2 moved in turn 1. D3, D4, D5 stayed at `start` because the
destinations were full:
- `fast_junction` cap=2 but only 1 drone moved there (D1). However, with link capacity
  of 1 on `start-fast_junction`, only 1 drone can cross per turn.
- `slow_path1` cap=1, already taken by D2.

**Occupancy after turn 1:** start=3, fast_junction=1, slow_path1=1

---

#### Turn 2

D2 was in transit (restricted zone) → arrives at `slow_path1`.

```
Turn 2: D2-slow_path1 D1-fast_path D2-slow_path2 D3-fast_junction
```

Wait — D2 appears twice? Let's trace carefully:

1. **Transit arrivals** (processed first):
   - D2 was in transit to `slow_path1` → arrives. Output: `D2-slow_path1`. path_index advances.

2. **Normal moves** (processed after):
   - D1 at `fast_junction` → moves to `fast_path`. Output: `D1-fast_path`.
   - D2 just arrived at `slow_path1` → BUT its path_index already advanced, so next is `slow_path2`. The zone `slow_path2` has cap=1, occ=0 → Move! Output: `D2-slow_path2`.

   Actually, D2 arrived from transit this turn, so its `in_transit` was cleared and it can move again? Let me re-check...

   Looking at the code: `_resolve_transit_arrivals` sets `drone.in_transit = False` and advances `path_index`. Then in the main loop, the drone is no longer `in_transit` and not `finished`, so it can attempt another move. So yes — **D2 arrives at slow_path1 AND moves to slow_path2 in the same turn**.

   - D3 at `start` → `fast_junction` now free (D1 left). cap=2, occ=0 → Move! Output: `D3-fast_junction`.
   - D4 at `start` → `fast_junction` now has occ=1, but link `start-fast_junction` already used by D3 (cap=1) → **blocked**.
   - D5 at `start` → `slow_path1` now free (D2 left). But restricted → transit. Output would be `D5-start-slow_path1`. But the actual output doesn't show D5 here... so D5 waited.

**Occupancy after turn 2:** start=2, fast_junction=1 (D3), fast_path=1 (D1), slow_path2=1 (D2)

---

#### Turn 3

```
Turn 3: D1-merge_point D2-merge_point D3-fast_path D4-fast_junction D5-start-slow_path1
```

| Drone | Action |
|-------|--------|
| D1 | fast_path → merge_point (cap=3, occ=0) → move |
| D2 | slow_path2 → merge_point (cap=3, occ=1 after D1) → move |
| D3 | fast_junction → fast_path (occ=0 after D1 left) → move |
| D4 | start → fast_junction (occ=0 after D3 left) → move |
| D5 | start → slow_path1 (restricted, occ=0) → start transit |

**Occupancy after turn 3:** start=0, fast_junction=1 (D4), fast_path=1 (D3), merge_point=2 (D1,D2), slow_path1=1 (D5 in transit)

---

#### Turn 4

```
Turn 4: D5-slow_path1 D1-goal D2-goal D3-merge_point D4-fast_path D5-slow_path2
```

| Drone | Action |
|-------|--------|
| D5 | Transit arrival → arrives at slow_path1 |
| D1 | merge_point → goal: link cap=2, used=0 → move. **FINISHED!** |
| D2 | merge_point → goal: link cap=2, used=1 → move. **FINISHED!** |
| D3 | fast_path → merge_point → move |
| D4 | fast_junction → fast_path → move |
| D5 | slow_path1 → slow_path2 → move (same turn as arrival, like D2 did) |

**Occupancy after turn 4:** fast_path=1 (D4), merge_point=1 (D3), slow_path2=1 (D5), goal=2 (D1,D2 finished)

---

#### Turn 5

```
Turn 5: D3-goal D4-merge_point D5-merge_point
```

| Drone | Action |
|-------|--------|
| D3 | merge_point → goal. **FINISHED!** |
| D4 | fast_path → merge_point → move |
| D5 | slow_path2 → merge_point (cap=3, occ=1) → move |

**Occupancy after turn 5:** merge_point=2 (D4,D5), goal=3

---

#### Turn 6

```
Turn 6: D4-goal D5-goal
```

| Drone | Action |
|-------|--------|
| D4 | merge_point → goal: link cap=2, used=0 → move. **FINISHED!** |
| D5 | merge_point → goal: link cap=2, used=1 → move. **FINISHED!** |

All 5 drones have reached `goal`. **Simulation complete in 6 turns.**

---

## Step 6 — `main.py`: Printing the Output

```python
print(f"\n\nNumber of turns: {alloc.nb_turns}\n\n")
print(sim.format_turns(turns))
```

The `format_turns` method joins each turn's moves with spaces, and joins turns
with newlines:

```
D1-fast_junction D2-start-slow_path1
D2-slow_path1 D1-fast_path D2-slow_path2 D3-fast_junction
D1-merge_point D2-merge_point D3-fast_path D4-fast_junction D5-start-slow_path1
D5-slow_path1 D1-goal D2-goal D3-merge_point D4-fast_path D5-slow_path2
D3-goal D4-merge_point D5-merge_point
D4-goal D5-goal
```

Output format explained:
- `D1-fast_junction` → Drone 1 moved to fast_junction (normal move)
- `D2-start-slow_path1` → Drone 2 is flying between start and slow_path1 (restricted zone, in transit)
- `D2-slow_path1` → Drone 2 arrived at slow_path1 (transit complete)

---

## Step 7 — `visualizer.py`: Drawing Everything

When you run `python3 visualizer.py maps/medium/03_priority_puzzle.txt`, the
visualizer does everything `main.py` does **plus** draws it on screen.

### 7.1 — Building screen positions (`_build_positions`)

World coordinates from the map:

| Zone | World (x, y) |
|------|-------------|
| start | (0, 0) |
| slow_path1 | (1, -1) |
| slow_path2 | (2, -1) |
| fast_junction | (1, 0) |
| fast_path | (2, 0) |
| merge_point | (3, 0) |
| goal | (4, 0) |

The method scales these to fill the 1200×780 window (with 80px margins):
- x range: 0 to 4 → scaled to 80 to 1120 pixels
- y range: -1 to 0 → scaled to 80 to 700 pixels
- Then centered on screen

### 7.2 — Highlighting path edges

From the 5 drone assignments, these edges are on at least one path:

```
(fast_junction, start)        → yellow
(fast_junction, fast_path)    → yellow
(fast_path, merge_point)      → yellow
(merge_point, goal)           → yellow
(slow_path1, start)           → yellow
(slow_path1, slow_path2)      → yellow
(merge_point, slow_path2)     → yellow
```

All 7 edges in this map are used → **all edges drawn in yellow**.

### 7.3 — Drawing zones

Each zone is drawn as a 22×22 colored square:
- `start` → green square
- `slow_path1` → red square
- `fast_junction` → blue square
- `merge_point` → yellow square
- `goal` → green square

No zone is `blocked`, so no white X is drawn.

### 7.4 — Animating drones

Every 0.70 seconds, the visualizer calls `_begin_turn()` which calls `sim.step()`.
During the 0.55 seconds of animation:

1. Each moving drone's progress goes from 0.0 to 1.0 using **smoothstep** interpolation.
2. The drone image is drawn at the interpolated position between its source and destination zone.
3. The drone image is **rotated** to face the direction of movement.
4. When multiple drones are at the same zone, they spread in a **circle** (radius 12px) so they don't overlap.

### 7.5 — User controls

- **SPACE** → pause/resume the auto-advancing
- **RIGHT ARROW** → manually step one turn (useful when paused)
- **ESCAPE** → close the window

---

## Summary: The Complete Data Flow

```
┌──────────────────────────────────────────────────────────────┐
│                    03_priority_puzzle.txt                     │
│                     (raw text file)                           │
└──────────────┬───────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────┐
│  parser.py: MapParser.parse_file()                           │
│  • Read line by line                                         │
│  • Validate syntax with regex                                │
│  • Create Zone and Connection objects                        │
│  • Build Graph with adjacency list                           │
│  Output: (5, "start", "goal", Graph)                         │
└──────────────┬───────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────┐
│  pathfinder.py: MultiPathFinder                              │
│  • best_single_path() → Dijkstra finds fast route (cost=4)   │
│  • extra_path() → penalize, find slow route (cost=5)         │
│  • drone_waste() → assign 5 drones: 3 fast, 2 slow           │
│  Output: AllocationResult(5 paths, 6 turns)                  │
└──────────────┬───────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────┐
│  simulator.py: Simulation                                    │
│  • Track occupancy of every zone                             │
│  • Each step(): check capacity, move drones, handle transit  │
│  • Restricted zones → 2-turn movement with transit state     │
│  • Output per turn: "D1-zone D2-zone ..."                    │
│  Result: 6 turns, all 5 drones at goal                       │
└──────────────┬───────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────┐
│  main.py: Print to terminal                                  │
│                          OR                                   │
│  visualizer.py: Draw with Pygame                             │
│  • Scale zone coordinates to screen                          │
│  • Draw edges (yellow=used), nodes (colored squares)         │
│  • Animate drones with smoothstep interpolation              │
│  • Controls: SPACE, RIGHT, ESCAPE                            │
└──────────────────────────────────────────────────────────────┘
```

### Final Output (6 turns to route 5 drones)

```
Turn 1:  D1-fast_junction  D2-start-slow_path1
Turn 2:  D2-slow_path1  D1-fast_path  D2-slow_path2  D3-fast_junction
Turn 3:  D1-merge_point  D2-merge_point  D3-fast_path  D4-fast_junction  D5-start-slow_path1
Turn 4:  D5-slow_path1  D1-goal  D2-goal  D3-merge_point  D4-fast_path  D5-slow_path2
Turn 5:  D3-goal  D4-merge_point  D5-merge_point
Turn 6:  D4-goal  D5-goal
```

> The target for this medium map is ≤ 12 turns. We achieved **6 turns** — well
> within the benchmark.
