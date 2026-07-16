# Line-by-Line Explanation of `simulator.py`

> This document explains every single line of `simulator.py` in simple, clear English —
> as if talking to the corrector during a peer-evaluation.

---

## 0 — What This File Does (Big Picture)

The pathfinder gave each drone a **path** (a list of zone names from start to end).
Now the simulator must **execute** those paths turn by turn, respecting all the rules
from the subject:

- Zones have a **max capacity** (default 1 drone at a time).
- Connections have a **max link capacity** (default 1 drone at a time).
- **Restricted** zones take **2 turns** to enter (the drone spends 1 turn "in transit").
- **Blocked** zones cannot be entered.
- **Start** and **end** zones have **unlimited capacity**.
- Drones leaving a zone **free up space** on the same turn.

The simulator produces the output format required by the subject:
- `D<ID>-<zone>` for normal arrivals.
- `D<ID>-<src>-<dst>` for a drone in transit toward a restricted zone.

---

## 1 — Imports (Lines 1–4)

```python
from __future__ import annotations                    # Line 1
from dataclasses import dataclass                      # Line 2
from typing import Dict, List, Optional, Tuple         # Line 3
from models import Graph                               # Line 4
```

| Line | What it does |
|------|-------------|
| 1 | Enables modern type-hint syntax. |
| 2 | `dataclass` — Auto-generates `__init__` and other methods for data-holding classes. |
| 3 | Type-hint imports for `mypy` compliance. |
| 4 | `Graph` — The parsed graph with zones, connections, and adjacency lists. |

---

## 2 — `Drone` Dataclass (Lines 7–16)

```python
@dataclass
class Drone:
    """Run the drone simulation."""
    drone_id: int
    path: List[str]
    path_index: int = 0
    finished: bool = False
    in_transit: bool = False
    transit_src: Optional[str] = None
    transit_dst: Optional[str] = None
```

Each drone is a simple data object that tracks its state:

| Field | Type | Meaning |
|-------|------|---------|
| `drone_id` | `int` | Unique ID (1, 2, 3, ...). Used in output like `D1`, `D2`. |
| `path` | `List[str]` | The sequence of zone names this drone must follow, e.g. `["hub", "roof1", "goal"]`. |
| `path_index` | `int` | Current position in the path. Starts at `0` (the start zone). After moving to the next zone, incremented by 1. |
| `finished` | `bool` | `True` when the drone has reached the end zone. It will no longer move. |
| `in_transit` | `bool` | `True` when the drone is flying toward a **restricted** zone (takes 2 turns). During transit, the drone cannot do anything else. |
| `transit_src` | `Optional[str]` | The zone the drone left when it started transit. `None` when not in transit. |
| `transit_dst` | `Optional[str]` | The restricted zone the drone is flying toward. `None` when not in transit. |

---

## 3 — `Simulation` Class (Lines 19–23)

```python
class Simulation:
    """simulation supporting multi-path
    Output format:
        - D<ID>-<zone> for normal/priority/end arrivals
        - D<ID>-<src>-<dst> while flying toward a restricted zone"""
```

The main simulation engine. One `Simulation` object handles one complete run of
all drones from start to end.

### 3.1 — `__init__` (Lines 24–38)

```python
def __init__(self, graph: Graph, assignments: List[List[str]]) -> None:
    """Create a new simulation."""
    if not assignments:
        raise ValueError("Assignments list must not be empty")
    self.graph = graph
    self.drones: List[Drone] = []
    self.turn_count: int = 0
    self.start = assignments[0][0]
    self.end = assignments[0][-1]

    for idx, path in enumerate(assignments, start=1):
        self.drones.append(Drone(drone_id=idx, path=path))

    self.occupancy: Dict[str, int] = {z: 0 for z in self.graph.zones}
    self.occupancy[self.start] = len(self.drones)
```

| Line(s) | What it does |
|---------|-------------|
| 26–27 | If the assignments list is empty, raise an error. We need at least one drone. |
| 28 | Store the graph reference. |
| 29 | Create an empty list to hold all `Drone` objects. |
| 30 | Initialize the turn counter to 0. |
| 31 | The **start zone** is the first zone in the first drone's path. |
| 32 | The **end zone** is the last zone in the first drone's path. |
| 34–35 | Create one `Drone` object per assignment. IDs start from 1 (`enumerate(..., start=1)`). |
| 37 | Initialize an **occupancy tracker**: a dictionary where the key is the zone name and the value is how many drones are currently in that zone. All zones start at 0. |
| 38 | All drones start at the start zone, so set `occupancy[start]` to the total number of drones. |

---

## 4 — `step` Method — One Simulation Turn (Lines 40–81)

```python
def step(self) -> List[str]:
    """Run one simulation turn."""
    self.turn_count += 1
    moves: List[str] = []
    link_used: Dict[Tuple[str, str], int] = {}
```

| Line | What it does |
|------|-------------|
| 42 | Increment the turn counter. |
| 43 | Create an empty list to store all movement strings for this turn (e.g. `["D1-roof1", "D2-corridorA"]`). |
| 44 | Track how many drones have used each connection this turn. Key is a sorted tuple of zone names, value is usage count. |

### 4.1 — Resolve Transit Arrivals First (Line 45)

```python
    self._resolve_transit_arrivals(moves, link_used)
```

**Before moving any normal drones**, first handle drones that started flying toward
a restricted zone **last turn**. They MUST arrive this turn (the subject says they
cannot wait on a connection). This is explained in section 6.

### 4.2 — Process Each Drone (Lines 46–81)

```python
    for drone in self.drones:
        if drone.finished or drone.in_transit:
            continue
```

Loop over all drones. Skip drones that:
- Are already **finished** (reached the end zone).
- Are **in transit** (already handled by `_resolve_transit_arrivals`).

```python
        if drone.path_index >= len(drone.path) - 1:
            drone.finished = True
            continue
```

If the drone's `path_index` has reached the last element of its path, it is at the
end zone → mark as **finished** and skip.

```python
        src = drone.path[drone.path_index]
        dst = drone.path[drone.path_index + 1]
```

- `src` — The zone the drone is currently in.
- `dst` — The **next** zone the drone wants to move to.

```python
        if self._is_blocked(dst):
            continue
```

If the destination zone is **blocked**, the drone cannot move → skip.
(This should not happen if the pathfinder is correct, but it is a safety check.)

```python
        edge = (src, dst) if src < dst else (dst, src)
        cap = self._find_link_capacity(src, dst)
        if link_used.get(edge, 0) >= cap:
            continue
```

- Create a **sorted edge key** (alphabetical) so `(a, b)` and `(b, a)` are the same.
- Look up the **connection capacity** (`max_link_capacity`, default 1).
- If this connection has already been used to its maximum this turn → skip. The
  drone must **wait**.

### 4.3 — Moving Toward a Restricted Zone (Lines 60–71)

```python
        dst_type = self.graph.zones[dst].zone_type
        if dst_type == "restricted":
            if self.occupancy[dst] >= self._zone_capacity(dst):
                continue
            self.occupancy[src] -= 1
            self.occupancy[dst] += 1
            link_used[edge] = link_used.get(edge, 0) + 1
            drone.in_transit = True
            drone.transit_src = src
            drone.transit_dst = dst
            moves.append(f"D{drone.drone_id}-{src}-{dst}")
            continue
```

If the destination is a **restricted** zone (costs 2 turns):

| Line(s) | What it does |
|---------|-------------|
| 62–63 | If the restricted zone is already full (at capacity) → skip. Subject says: *"It cannot wait on the connection for an empty space."* So if it is full now, the drone waits at `src`. |
| 64 | Remove the drone from the source zone's occupancy count. |
| 65 | Add the drone to the destination zone's occupancy count. **Important**: occupancy is reserved immediately, even though the drone arrives next turn. This prevents another drone from taking the spot. |
| 66 | Mark this connection as used (increment usage counter). |
| 67–69 | Put the drone **in transit**: set the flag and record source/destination. Next turn, `_resolve_transit_arrivals` will complete the move. |
| 70 | Output format: `D<ID>-<src>-<dst>` — shows the drone is flying between two zones. |
| 71 | `continue` → done with this drone for this turn. |

### 4.4 — Normal Movement (Lines 72–81)

```python
        if self.occupancy[dst] >= self._zone_capacity(dst):
            continue
        self.occupancy[src] -= 1
        self.occupancy[dst] += 1
        link_used[edge] = link_used.get(edge, 0) + 1
        drone.path_index += 1
        moves.append(f"D{drone.drone_id}-{dst}")
        if dst == self.end:
            drone.finished = True
    return moves
```

For normal/priority zones (cost = 1 turn):

| Line(s) | What it does |
|---------|-------------|
| 72–73 | If the destination zone is full → skip. Drone waits. |
| 74 | Remove drone from source zone occupancy. |
| 75 | Add drone to destination zone occupancy. |
| 76 | Mark connection as used. |
| 77 | Advance the drone's path index by 1 — it has arrived at the next zone. |
| 78 | Output format: `D<ID>-<dst>` — simple arrival at the destination. |
| 79–80 | If the destination is the **end zone**, mark the drone as **finished**. |
| 81 | Return all the movement strings for this turn. |

---

## 5 — `run` Method — Full Simulation Loop (Lines 83–95)

```python
def run(self, max_turns: int = 100000) -> List[List[str]]:
    """Run the simulation."""
    history: List[List[str]] = []

    for _ in range(max_turns):
        if all(d.finished for d in self.drones):
            break

        turn_moves = self.step()
        if turn_moves:
            history.append(turn_moves)

    return history
```

| Line(s) | What it does |
|---------|-------------|
| 85 | Create `history` — a list where each element is one turn's list of moves. |
| 87–89 | **Stop condition**: if ALL drones are finished, the simulation is complete → break. |
| 91 | Execute one turn by calling `step()`. |
| 92–93 | If there were any moves this turn, add them to the history. (Turns where no drone moved are not recorded.) |
| 95 | Return the full history. The **length** of this list = number of turns used. |

---

## 6 — `_resolve_transit_arrivals` — Completing Restricted Moves (Lines 97–120)

```python
def _resolve_transit_arrivals(self,
                              moves: List[str],
                              link_used: Dict[Tuple[str, str], int]
                              ) -> None:
    """Finish drones in restricted flight."""
```

This method runs at the **start** of each turn, before processing normal moves.
It handles drones that started flying toward a restricted zone **last turn** and
must now arrive.

```python
    for drone in self.drones:
        if drone.finished or not drone.in_transit:
            continue
```

Only process drones that are **in transit** (started a 2-turn restricted move last turn).

```python
        assert drone.transit_src is not None
        assert drone.transit_dst is not None
        src = drone.transit_src
        dst = drone.transit_dst
```

Safety asserts for `mypy`: if `in_transit` is `True`, these fields must not be `None`.
Store them in local variables for readability.

```python
        edge = (src, dst) if src < dst else (dst, src)
        cap = self._find_link_capacity(src, dst)
        if link_used.get(edge, 0) >= cap:
            continue
```

Check if the connection still has capacity. (Multiple drones might be completing
transit on the same connection this turn.)

```python
        link_used[edge] = link_used.get(edge, 0) + 1
        drone.path_index += 1
        drone.in_transit = False
        drone.transit_src = None
        drone.transit_dst = None
        moves.append(f"D{drone.drone_id}-{dst}")
        if dst == self.end:
            drone.finished = True
```

| Line(s) | What it does |
|---------|-------------|
| 113 | Mark the connection as used. |
| 114 | Advance the drone's path index — it has arrived. |
| 115–117 | Clear the transit state: `in_transit` → `False`, clear source and destination. |
| 118 | Output: `D<ID>-<dst>` — the drone has arrived at the restricted zone. |
| 119–120 | If the destination is the **end zone**, mark finished. |

---

## 7 — `_find_link_capacity` — Get Connection Capacity (Lines 122–127)

```python
def _find_link_capacity(self, a: str, b: str) -> int:
    """Return the link capacity."""
    for nei, conn in self.graph.neighbors(a):
        if nei.name == b:
            return conn.max_link_capacity
    raise ValueError(f"No connection between '{a}' and '{b}'")
```

Looks up the `max_link_capacity` of the connection between zones `a` and `b`.
Searches the adjacency list of zone `a` for zone `b`. If the connection does not
exist, raises an error (should never happen if the pathfinder is correct).

---

## 8 — `_is_blocked` — Check If Zone Is Blocked (Lines 129–133)

```python
def _is_blocked(self, zone_name: str) -> bool:
    """Check if a zone is blocked."""
    if zone_name == self.end:
        return False
    return self.graph.zones[zone_name].zone_type == "blocked"
```

Returns `True` if the zone type is `"blocked"`.
**Exception**: the end zone is **never** considered blocked, even if it technically
has a blocked type (safety check).

---

## 9 — `_zone_capacity` — Get Zone Drone Limit (Lines 135–139)

```python
def _zone_capacity(self, zone_name: str) -> int:
    """Return the zone capacity."""
    if zone_name == self.start or zone_name == self.end:
        return 10**9
    return self.graph.zones[zone_name].max_drones
```

Returns how many drones can be in this zone at the same time.

| Case | Returns |
|------|---------|
| Start zone | `10**9` (unlimited) — all drones start here. |
| End zone | `10**9` (unlimited) — any number of drones can arrive. |
| Any other zone | The zone's `max_drones` value (default 1). |

The subject says: *"The max_drones capacity is ignored on the start_hub and end_hub
zones: these have no capacity limit."*

---

## 10 — `format_turns` — Format Output (Lines 141–144)

```python
@staticmethod
def format_turns(turns: List[List[str]]) -> str:
    """Format turns as terminal-friendly lines."""
    return "\n".join(" ".join(t) for t in turns)
```

Converts the simulation history into the output format required by the subject:

```
D1-roof1 D2-corridorA
D1-roof2 D2-tunnelB
D1-goal D2-goal
```

- Each inner list (one turn) is joined with spaces.
- All turns are joined with newlines.

---

## Summary — How One Turn Works

```
    ┌──────────────────────────────────┐
    │        Start of turn N           │
    └──────────────┬───────────────────┘
                   │
    ┌──────────────▼───────────────────┐
    │  1. Resolve transit arrivals     │ ← Drones that started a 2-turn
    │     (restricted zone arrivals)   │   restricted move last turn
    └──────────────┬───────────────────┘   MUST arrive now.
                   │
    ┌──────────────▼───────────────────┐
    │  2. For each remaining drone:    │
    │     a. Is it finished? → skip    │
    │     b. Is dst blocked? → skip    │
    │     c. Is link at capacity? → skip │
    │     d. Is dst restricted?        │
    │        → start 2-turn transit    │
    │        → output D<ID>-<src>-<dst>│
    │     e. Is dst at capacity? → skip│
    │     f. Normal move:              │
    │        → update occupancy        │
    │        → output D<ID>-<dst>      │
    └──────────────┬───────────────────┘
                   │
    ┌──────────────▼───────────────────┐
    │  3. Return list of all moves     │
    └──────────────────────────────────┘
```

The simulation runs this turn logic repeatedly until **all drones are finished**
(have reached the end zone).
