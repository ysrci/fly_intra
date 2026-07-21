# Line-by-Line Explanation of `pathfinder.py`

> This document explains every single line of `pathfinder.py` in simple, clear English —
> as if talking to the corrector during a peer-evaluation.

---

## 0 — What This File Does (Big Picture)

The parser gave us a `Graph` — zones and connections. Now we need to **find routes**
for every drone from the start zone to the end zone.

`pathfinder.py` does three things:

1. **Find the best single path** using a modified Dijkstra algorithm that also
   prefers "priority" zones (tie-breaking).
2. **Find multiple alternative paths** using a penalty-based technique
   (penalize nodes of previous paths to force new routes).
3. **Assign each drone to one of those paths** using a greedy simulation-based
   approach: for each drone, try every candidate path, run a full simulation,
   and pick the path that produces the fewest total turns.

---

## 1 — Imports (Lines 1–6)

```python
from __future__ import annotations        # Line 1
import heapq                               # Line 2
from dataclasses import dataclass          # Line 3
from typing import Dict, List, Optional, Tuple  # Line 4
from models import Graph                   # Line 5
from simulator import Simulation           # Line 6
```

| Line | What it does |
|------|-------------|
| 1 | Enables modern type-hint syntax (same as in the parser). |
| 2 | `heapq` — Python's built-in **min-heap** (priority queue). We use it for Dijkstra's algorithm. A min-heap always gives us the element with the smallest value first. |
| 3 | `dataclass` — A decorator that auto-generates `__init__`, `__repr__`, etc. for simple data-holding classes. |
| 4 | Type-hint imports for `mypy` compliance. |
| 5 | `Graph` — The graph object built by the parser. Contains zones, connections, and adjacency lists. |
| 6 | `Simulation` — The simulation engine. The pathfinder runs **trial simulations** to evaluate which path assignment gives the fewest turns. |

---

## 2 — `PathResult` Dataclass (Lines 9–14)

```python
@dataclass(frozen=True)
class PathResult:
    """Store one path."""
    path: List[str]
    cost: int
    property_count: int
```

| Field | Type | Meaning |
|-------|------|---------|
| `path` | `List[str]` | Ordered list of zone names from start to end. Example: `["hub", "roof1", "roof2", "goal"]`. |
| `cost` | `int` | Total movement cost of this path. `normal`/`priority` zones cost 1, `restricted` zones cost 2. |
| `property_count` | `int` | How many **priority zones** this path passes through. Higher is better — priority zones should be preferred. |

`frozen=True` makes objects **immutable** (you cannot change their fields after creation).
This is good practice for results that should never be modified.

---

## 3 — `AllocationResult` Dataclass (Lines 17–21)

```python
@dataclass(frozen=True)
class AllocationResult:
    """Store drone paths."""
    assignments: List[List[str]]
    nb_turns: int
```

| Field | Type | Meaning |
|-------|------|---------|
| `assignments` | `List[List[str]]` | One path per drone. `assignments[0]` is the path for drone 1, `assignments[1]` for drone 2, etc. |
| `nb_turns` | `int` | The estimated total number of simulation turns needed to deliver all drones using these assignments. |

---

## 4 — `MultiPathFinder` Class (Line 24)

```python
class MultiPathFinder:
    """Find the best paths."""
```

This is the main class. It contains all the pathfinding logic.

### 4.1 — `__init__` (Lines 26–28)

```python
def __init__(self, graph: Graph) -> None:
    """Save the graph."""
    self.graph = graph
```

Simply stores a reference to the parsed graph. All methods will use `self.graph`
to access zones, connections, and adjacency lists.

---

## 5 — `best_single_path` — Modified Dijkstra (Lines 30–93)

This is the **core algorithm**. It finds the shortest path from `start` to `end`,
with two special features:
- It respects **zone movement costs** (restricted = 2, others = 1).
- It uses **priority zone count as a tie-breaker** (more priority zones = better).

### 5.1 — Method Signature (Lines 30–33)

```python
def best_single_path(self,
                     start: str, end: str,
                     penalty: Optional[Dict[str, int]] = None
                     ) -> Optional[PathResult]:
    """Find the best path."""
```

| Parameter | Meaning |
|-----------|---------|
| `start` | Name of the start zone. |
| `end` | Name of the end zone. |
| `penalty` | **Optional** dictionary of extra costs per zone. Used by `extra_path()` to push the algorithm away from already-found paths, forcing it to discover new alternative routes. |

Returns `None` if no path exists.

### 5.2 — Initialization (Lines 35–42)

```python
dist: Dict[str, int] = {z: 10**9 for z in self.graph.zones}
prio_score: Dict[str, int] = {z: -10**9 for z in self.graph.zones}
prev: Dict[str, Optional[str]] = {z: None for z in self.graph.zones}

dist[start] = 0
prio_score[start] = 0

heap: List[Tuple[int, int, str]] = [(0, 0, start)]
```

| Variable | Purpose | Initial value |
|----------|---------|---------------|
| `dist` | Shortest known distance (cost) to reach each zone. | `10**9` (infinity) for all zones, except `start` = 0. |
| `prio_score` | Number of priority zones on the best path to reach each zone. | `-10**9` for all, except `start` = 0. |
| `prev` | Previous zone on the best path (for reconstructing the path later). | `None` for all. |
| `heap` | The min-heap (priority queue). Each entry is `(cost, neg_priority, zone_name)`. | Starts with just the start zone at cost 0. |

**Why negative priority in the heap?**
Python's `heapq` is a **min-heap** — it pops the smallest value first. We want
to **maximize** priority zones. By storing `-priority`, the min-heap effectively
gives us the entry with the **highest** priority count when costs are equal.

### 5.3 — Main Loop (Lines 44–79)

```python
while heap:
    cost, neg_priority, zone = heapq.heappop(heap)
    priority = -neg_priority
```

Pop the zone with the **lowest cost** (and highest priority count as tie-breaker)
from the heap.

#### Skip Outdated Entries (Lines 48–51)

```python
    if cost > dist[zone]:
        continue
    if cost == dist[zone] and priority < prio_score[zone]:
        continue
```

- If we already found a **cheaper** way to reach this zone, skip this old entry.
- If the cost is the same but we already found a path with **more priority zones**,
  also skip. These are "stale" heap entries that are no longer the best.

#### Early Exit (Lines 52–53)

```python
    if zone == end:
        break
```

If we just popped the **end zone**, we are done! Dijkstra guarantees that the first
time we pop a zone, we have found the shortest path to it.

#### Explore Neighbors (Lines 55–79)

```python
    for v_zone, _ in self.graph.neighbors(zone):
        name = v_zone.name
```

Loop over all zones connected to the current zone. `v_zone` is the neighbor `Zone`
object, `_` is the `Connection` object (not used here).

```python
        if self.graph.zones[name].zone_type == "blocked":
            continue
```

**Skip blocked zones.** The subject says blocked zones are inaccessible — drones
must never enter them.

```python
        step = self._move_cost(name)
        extra = 0 if penalty is None else penalty.get(name, 0)
```

- `step` — The movement cost to enter this zone: `2` for restricted, `1` for
  normal/priority.
- `extra` — If a penalty dictionary was passed, add the penalty for this zone.
  This is how `extra_path()` discourages reusing the same zones.

```python
        nd = cost + step + extra
        np = priority + (
            1
            if self.graph.zones[name].zone_type == "priority"
            else 0)
```

- `nd` — **New distance**: cost to reach this neighbor through the current zone.
- `np` — **New priority count**: how many priority zones we have visited on this path.
  If this neighbor is a priority zone, add 1.

```python
        better = False
        if nd < dist[name]:
            better = True
        elif nd == dist[name] and np > prio_score[name]:
            better = True
```

A new path to this neighbor is **better** if:
1. It has a **lower cost** than the best we know, **OR**
2. Same cost but passes through **more priority zones** (tie-breaking).

```python
        if better:
            dist[name] = nd
            prio_score[name] = np
            prev[name] = zone
            heapq.heappush(heap, (nd, -np, name))
```

If better, update the tables and push this neighbor into the heap.
Note: `prev[name] = zone` records that to reach `name`, we came from `zone`.

### 5.4 — Check Reachability and Reconstruct (Lines 81–93)

```python
if dist[end] >= 10**9:
    return None
```

If the end zone still has "infinity" distance, **no path exists** → return `None`.

```python
path = self._reconstruct(prev, start, end)
if not path:
    return None
```

Build the path by following `prev` pointers backwards from `end` to `start`
(explained in section 9 below).

```python
if penalty is None:
    real_cost = dist[end]
else:
    real_cost = self._path_real_cost(path)
```

- If no penalties were used, the distance from the table is the real cost.
- If penalties were used, the `dist[end]` includes penalty costs, so we
  recalculate the **actual** movement cost without penalties using `_path_real_cost()`.

```python
return PathResult(path, real_cost, prio_score[end])
```

Return the result: the path, its real cost, and how many priority zones it uses.

---

## 6 — `extra_path` — Finding Multiple Alternative Paths (Lines 95–119)

```python
def extra_path(self, start: str, end: str, k: int = 6) -> List[PathResult]:
    """Find many paths."""
```

This method finds **up to `k` different paths** from start to end.

### 6.1 — Get the First Path (Lines 97–102)

```python
    base = self.best_single_path(start, end)
    if base is None:
        return []
    candidates: List[PathResult] = [base]
    seen = {tuple(base.path)}
    penalize_nodes: Dict[str, int] = {}
```

- Find the best path with no penalties.
- If no path exists, return empty list.
- `candidates` — List of found paths, starting with the base path.
- `seen` — Set of paths already found (as tuples, since lists are not hashable).
- `penalize_nodes` — Accumulating penalty dictionary.

### 6.2 — Iterative Penalty Loop (Lines 104–119)

```python
    for _ in range(k - 1):
        for p in candidates[-1].path[1:-1]:
            penalize_nodes[p] = penalize_nodes.get(p, 0) + 1

        alt = self.best_single_path(start, end, penalize_nodes)
        if alt is None:
            break
        key = tuple(alt.path)
        if key in seen:
            break
        seen.add(key)
        candidates.append(alt)
        candidates.sort(
            key=lambda p: (p.cost, -p.property_count, len(p.path))
        )
    return candidates
```

**How the penalty technique works:**

1. Take the **last found path** and add `+1` penalty to every **intermediate** zone
   (skip start and end — `path[1:-1]`).
2. Run Dijkstra again **with these penalties**. The penalties make previously-used
   zones more expensive, so the algorithm is forced to find a **different route**.
3. If the new path is `None` (no more routes) or is a **duplicate** of one we already
   have → stop.
4. Add the new path to candidates and **sort** them by:
   - Primary: **lowest cost** first.
   - Secondary: **most priority zones** first (`-p.property_count` to reverse sort).
   - Tertiary: **shortest path** first.

This technique is a simplified version of **Yen's k-shortest paths algorithm**.

---

## 7 — `drone_waste` — Greedy Drone Assignment (Lines 121–143)

```python
def drone_waste(self,
                start: str, end: str, nb_drones: int,
                max_paths: int = 24) -> AllocationResult:
    """Choose paths for drones."""
```

This is the **final step**: assign a path to each drone such that the total number
of simulation turns is minimized.

### 7.1 — Get Candidate Paths (Lines 125–127)

```python
    paths = self.extra_path(start, end, k=max_paths)
    if not paths:
        return AllocationResult(assignments=[], nb_turns=0)
```

Find up to `max_paths` (default 24) alternative routes.
If no paths exist → return empty result.

### 7.2 — Greedy Assignment Loop (Lines 128–140)

```python
    assignments: List[List[str]] = []
    for _ in range(nb_drones):
        best_i = 0
        best_score = 10**9

        for i, p in enumerate(paths):
            test_assign = assignments + [p.path]
            sim = Simulation(self.graph, test_assign)
            turns = len(sim.run(max_turns=2000))
            if turns < best_score:
                best_score = turns
                best_i = i
        assignments.append(paths[best_i].path)
```

**How greedy assignment works:**

For each drone (one at a time):
1. Try **every candidate path**.
2. Create a temporary assignment list: all previously assigned drones + this drone
   on the candidate path.
3. Run a **full simulation** with this assignment.
4. Count how many turns the simulation took.
5. Pick the path that gives the **fewest total turns**.
6. Add that path to the permanent assignments.

This is a **greedy** algorithm — it makes the locally optimal choice for each drone
without reconsidering previous assignments. It is not guaranteed to find the global
optimum, but it works well in practice.

### 7.3 — Final Simulation and Return (Lines 141–143)

```python
    final_sim = Simulation(self.graph, assignments)
    estimated_turns = len(final_sim.run(max_turns=2000))
    return AllocationResult(assignments, estimated_turns)
```

After all drones are assigned, run one final simulation to get the accurate turn count.
Return the `AllocationResult` with all assignments and the total turns.

---

## 8 — `_path_real_cost` — Sum Path Cost Without Penalties (Lines 145–150)

```python
def _path_real_cost(self, path: List[str]) -> int:
    """Get the path cost."""
    cost = 0
    for name in path[1:]:
        cost += self._move_cost(name)
    return cost
```

Walk the path from the **second zone** to the end (skip the start — you are already
there). For each zone, add its movement cost. Returns the **true** cost of the path,
without any penalty bonuses.

---

## 9 — `_move_cost` — Zone Movement Cost (Lines 152–156)

```python
def _move_cost(self, zone: str) -> int:
    """Return move cost."""
    if self.graph.zones[zone].zone_type == "restricted":
        return 2
    return 1
```

Simple rule from the subject:
- `restricted` → costs **2 turns** to enter.
- Everything else (`normal`, `priority`) → costs **1 turn**.
- (`blocked` zones are never reached — they are filtered in Dijkstra).

---

## 10 — `_reconstruct` — Build Path from `prev` Table (Lines 158–170)

```python
def _reconstruct(self,
                 prev: Dict[str, Optional[str]], start: str,
                 end: str) -> List[str]:
    """Build the path."""
    path: List[str] = []
    cur: Optional[str] = end
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    path.reverse()
    if not path or path[0] != start:
        return []
    return path
```

| Line(s) | What it does |
|---------|-------------|
| 162–163 | Start from `end`, create an empty path list. |
| 164–166 | Follow the `prev` pointers backwards: `end → prev[end] → prev[prev[end]] → ... → start`. At each step, add the zone to the path. Stop when `prev` is `None` (meaning we reached the start). |
| 167 | The path was built backwards (end → start), so **reverse** it to get start → end. |
| 168–169 | Safety check: if the path is empty or does not start at the correct start zone, return an empty list (no valid path). |
| 170 | Return the reconstructed path. |

---

## Summary

The pathfinder has three layers:

```
                     drone_waste (greedy drone assignment)
                           │
                     ┌─────┴──────┐
                     │ extra_path │  (find k alternative paths)
                     └─────┬──────┘
                           │
                  ┌────────┴────────┐
                  │ best_single_path│  (modified Dijkstra)
                  └────────┬────────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
         _move_cost   _reconstruct  _path_real_cost
```

1. **`best_single_path`** — Dijkstra with priority-zone tie-breaking.
2. **`extra_path`** — Runs Dijkstra repeatedly with increasing penalties to find
   diverse alternative routes.
3. **`drone_waste`** — For each drone, tries all candidate paths via simulation and
   picks the one that minimizes total turns (greedy approach).

The result is a list of path assignments — one per drone — ready for the simulator.
