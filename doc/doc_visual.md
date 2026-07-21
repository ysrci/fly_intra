# Line-by-Line Explanation of `visualizer.py`

> This document explains every single line of `visualizer.py` in simple, clear English —
> as if talking to the corrector during a peer-evaluation.

---

## 0 — Project Context (What the Subject Asks)

The **Fly-in** project is a drone routing simulation.
We are given a **map file** that describes zones (nodes), connections (edges), and
a fleet of drones. The goal is to move **all drones from a start zone to an end zone**
in the fewest possible simulation turns.

The subject requires a **visual representation** of the simulation — either colored
terminal output or a graphical interface. This file implements a **Pygame-based
graphical visualizer** that:

1. Parses the map file and computes drone paths.
2. Draws the zone graph (nodes + edges) on screen.
3. Animates each drone moving smoothly along its assigned path.
4. Lets the user pause, play, or step through the simulation.

---

## 1 — Imports (Lines 1–9)

```python
from __future__ import annotations                    # Line 1
import math                                           # Line 2
import sys                                            # Line 3
from typing import Dict, List, Optional, Tuple        # Line 4
import pygame                                         # Line 5
from parser import MapParser                          # Line 6
from pathfinder import MultiPathFinder                # Line 7
from simulator import Simulation                      # Line 8
from pygame.surface import Surface                    # Line 9
```

| Line | What it does |
|------|-------------|
| 1 | `from __future__ import annotations` — Enables modern type-hint syntax. All annotations are stored as strings and evaluated lazily, so we can use `Tuple[int, int]` freely. |
| 2 | `import math` — We need `math.cos`, `math.sin`, `math.atan2`, `math.degrees`, and `math.pi` for drone rotation angles and for spreading overlapping drones in a circle. |
| 3 | `import sys` — Used in the `main()` function to read command-line arguments (`sys.argv`) and to write error messages to `sys.stderr`. |
| 4 | `from typing import Dict, List, Optional, Tuple` — Imports generic type aliases so we can write typed dictionaries, lists, and tuples. Required by `mypy`. |
| 5 | `import pygame` — The graphics library. We use it to create a window, draw shapes, load images, handle keyboard events, and run a game loop at 60 FPS. |
| 6 | `from parser import MapParser` — Our own parser module. `MapParser` reads a map file and returns: number of drones, start zone name, end zone name, and a `Graph` object. |
| 7 | `from pathfinder import MultiPathFinder` — Our own pathfinding module. `MultiPathFinder` takes the graph and computes optimized path assignments for all drones. |
| 8 | `from simulator import Simulation` — Our own simulation engine. `Simulation` takes the graph and path assignments, then produces turn-by-turn drone movements. |
| 9 | `from pygame.surface import Surface` — Imports the `Surface` type for type hints on drawing functions. A `Surface` is Pygame's representation of an image or screen buffer. |

---

## 2 — Color Constants (Lines 11–24)

```python
# ── colors ──────────────────────────────────────────────────────
BG = (40, 40, 40)                    # Line 12
EDGE_COL = (130, 145, 180)           # Line 13
EDGE_PATH_COL = (255, 220, 120)      # Line 14
NODE_BORDER = (0, 0, 0)              # Line 15
COL_START = (70, 235, 145)           # Line 16
COL_END = (210, 105, 255)            # Line 17
COL_NORMAL = (78, 131, 255)          # Line 18
COL_PRIORITY = (0, 212, 255)         # Line 19
COL_RESTRICTED = (255, 176, 79)      # Line 20
COL_BLOCKED = (255, 92, 92)          # Line 21
WHITE = (255, 255, 255)              # Line 22

Color = Tuple[int, int, int]         # Line 24
```

| Constant | Purpose |
|----------|---------|
| `BG` | Background color — dark gray `(40, 40, 40)`. The entire screen is filled with this every frame. |
| `EDGE_COL` | Default edge color — a muted blue-gray. Used for connections that are **not** on any drone's path. |
| `EDGE_PATH_COL` | Highlighted edge color — warm yellow. Used for connections that **are** on at least one drone's assigned path. This makes it easy to see which routes are being used. |
| `NODE_BORDER` | Black border drawn around each zone square. |
| `COL_START` | Green — for the start zone. |
| `COL_END` | Purple — for the end zone. |
| `COL_NORMAL` | Blue — for normal zones. |
| `COL_PRIORITY` | Cyan — for priority zones. |
| `COL_RESTRICTED` | Orange — for restricted zones (cost = 2 turns). |
| `COL_BLOCKED` | Red — for blocked zones (drones cannot enter). |
| `WHITE` | Used for text labels and the "X" drawn on blocked zones. |
| `Color` | A type alias: `Tuple[int, int, int]`. Every color is an RGB triplet. |

> **Note:** Some of these color constants (`COL_START`, `COL_END`, etc.) are defined
> but the actual node drawing uses the color from the parsed zone data (see `_draw_nodes`).
> These constants serve as fallbacks or references.

---

## 3 — Layout and Timing Constants (Lines 26–37)

```python
# ── constants ───────────────────────────────────────────────────
WIDTH, HEIGHT = 1200, 780             # Line 27
MARGIN = 80                           # Line 28
NODE_SIZE = 22                        # Line 29
TURN_INTERVAL = 0.70                  # Line 30
ANIM_DURATION = 0.55                  # Line 31

DRONE_PALETTE: List[Color] = [        # Lines 33–37
    (255, 99, 132), (54, 162, 235), (255, 206, 86),
    (75, 192, 192), (153, 102, 255), (255, 159, 64),
    (46, 204, 113), (231, 76, 60),
]
```

| Constant | Value | Purpose |
|----------|-------|---------|
| `WIDTH, HEIGHT` | 1200 × 780 | The window size in pixels. |
| `MARGIN` | 80 | Padding around the graph. Nodes will not be placed closer than 80 pixels from the edge. |
| `NODE_SIZE` | 22 | Each zone is drawn as a 22×22 pixel square. |
| `TURN_INTERVAL` | 0.70 | Time in seconds between simulation turns. Every 0.7 seconds, the simulator advances one step. |
| `ANIM_DURATION` | 0.55 | Time in seconds for the drone movement animation. It must be less than `TURN_INTERVAL` so the animation finishes before the next turn starts. |
| `DRONE_PALETTE` | 8 colors | A list of distinct RGB colors for drones. Each drone gets a color based on its ID (not currently used in drawing, but available). |

---

## 4 — `SimulationVisualizer` Class (Line 40)

```python
class SimulationVisualizer:
    """Visualizer with smooth drone movement over connections."""
```

This is the **main class** of the file. It manages everything: parsing, pathfinding,
simulation logic, rendering, and the game loop.

---

## 5 — `__init__` (Lines 43–61)

```python
def __init__(self, mapfile: str) -> None:
    """Initialize visualizer and load map."""
    p = MapParser()
    self.nb_drones, self.start, self.end, self.graph = p.parse_file(
        mapfile
    )
    self.assignments: List[List[str]] = []
    self.sim: Optional[Simulation] = None
    self.pos: Dict[str, Tuple[int, int]] = {}
    self.path_edges: set[Tuple[str, str]] = set()

    self.playing = True
    self.finished = False
    self.current_turn = 0
    self.turn_elapsed = 0.0
    self.anim_elapsed = 0.0

    # drone id -> (zone, move_from, move_to, progress, moving)
    self.drones: Dict[int, List[object]] = {}
```

| Line(s) | What it does |
|---------|-------------|
| 43 | Constructor takes one argument: `mapfile` — the path to the map text file. |
| 45 | Creates a `MapParser` instance. |
| 46–48 | Calls `parse_file(mapfile)`. This returns four values: the number of drones, the start zone name, the end zone name, and the full `Graph` object. We store all four as instance attributes. |
| 49 | `self.assignments` — Will hold the list of paths. Each path is a list of zone names (e.g., `["hub", "roof1", "roof2", "goal"]`). Empty until `setup()` is called. |
| 50 | `self.sim` — The `Simulation` engine. Set to `None` initially; created in `setup()`. |
| 51 | `self.pos` — A dictionary mapping zone names to their (x, y) **screen coordinates** in pixels. Filled by `_build_positions()`. |
| 52 | `self.path_edges` — A set of edge keys `(zone_a, zone_b)` that belong to some drone's path. Used to highlight those edges in yellow. |
| 54 | `self.playing` — Boolean flag. `True` = animation runs automatically. `False` = paused. Toggled with SPACE key. |
| 55 | `self.finished` — `True` when all drones have reached the end zone. |
| 56 | `self.current_turn` — Counter of how many simulation turns have been executed so far. |
| 57 | `self.turn_elapsed` — Accumulates time (in seconds) since the last turn. When it reaches `TURN_INTERVAL`, a new turn starts. |
| 58 | `self.anim_elapsed` — Accumulates time (in seconds) since the current animation began. Used to calculate how far along the movement each drone is. |
| 61 | `self.drones` — A dictionary mapping each drone ID (int) to a 5-element list: `[current_zone, move_from, move_to, progress, is_moving]`. This tracks the animation state of each drone. |

---

## 6 — `setup` Method (Lines 64–86)

```python
def setup(self) -> None:
    """Build layout, allocate paths, init drone states."""
    self._build_positions()

    finder = MultiPathFinder(self.graph)
    alloc = finder.drone_waste(
        start=self.start, end=self.end,
        nb_drones=self.nb_drones, max_paths=8,
    )
    if not alloc.assignments:
        raise ValueError("No valid path allocation")

    self.assignments = alloc.assignments
    self.sim = Simulation(self.graph, self.assignments)

    for path in self.assignments:
        for i in range(len(path) - 1):
            a, b = path[i], path[i + 1]
            self.path_edges.add((a, b) if a < b else (b, a))

    for did in range(1, self.nb_drones + 1):
        # [zone, move_from, move_to, progress, moving]
        self.drones[did] = [self.start, None, None, 0.0, False]
```

| Line(s) | What it does |
|---------|-------------|
| 66 | Call `_build_positions()` to convert the zone world coordinates into screen pixel coordinates. |
| 68 | Create a `MultiPathFinder` with the parsed graph. |
| 69–72 | Call `drone_waste()` — this is the path allocation algorithm. It finds up to 8 distinct paths from start to end and assigns each drone to one. It returns an allocation object with an `assignments` list. |
| 73–74 | If no valid paths were found (e.g., all routes are blocked), raise an error. |
| 76 | Store the assignments list. |
| 77 | Create the `Simulation` engine, passing the graph and the path assignments. The simulation will produce turn-by-turn moves. |
| 79–82 | **Build the highlighted edge set.** For each assigned path, iterate through consecutive zone pairs. Normalize each pair alphabetically so `(a, b)` and `(b, a)` produce the same key. Add the key to `self.path_edges`. These edges will be drawn in yellow. |
| 84–86 | **Initialize all drone states.** For each drone (ID 1 to `nb_drones`), create a 5-element list: the drone starts at the start zone, with no movement in progress (`None, None, 0.0, False`). |

---

## 7 — `_build_positions` Method (Lines 89–111)

```python
def _build_positions(self) -> None:
    """Convert world coords to centered screen coords."""
    zones = self.graph.zones
    xs = [z.x for z in zones.values()]
    ys = [z.y for z in zones.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    sx = max(1, max_x - min_x)
    sy = max(1, max_y - min_y)
    inner_w = WIDTH - 2 * MARGIN
    inner_h = HEIGHT - 2 * MARGIN

    raw: Dict[str, Tuple[int, int]] = {}
    for name, z in zones.items():
        px = MARGIN + (z.x - min_x) * inner_w // sx
        py = MARGIN + (z.y - min_y) * inner_h // sy
        raw[name] = (px, py)

    rxs = [p[0] for p in raw.values()]
    rys = [p[1] for p in raw.values()]
    dx = WIDTH // 2 - (min(rxs) + max(rxs)) // 2
    dy = HEIGHT // 2 - (min(rys) + max(rys)) // 2
    self.pos = {n: (x + dx, y + dy) for n, (x, y) in raw.items()}
```

This method converts the raw world coordinates from the map file into pixel
positions on the screen. It has two steps:

### Step 1 — Scale to fit (Lines 91–105)

| Line(s) | What it does |
|---------|-------------|
| 91 | Get the dictionary of all zones from the graph. |
| 92–93 | Extract all x-coordinates and all y-coordinates into separate lists. |
| 94–95 | Find the min and max of both x and y. This gives us the bounding box of the graph in world space. |
| 96–97 | Calculate the span (range) in each axis. `max(1, ...)` prevents division by zero if all zones have the same coordinate. |
| 98–99 | `inner_w` and `inner_h` are the usable drawing area: the full window minus margins on both sides. For a 1200×780 window with margin 80, this is 1040×620 pixels. |
| 101–105 | **Map each zone's world coordinates to screen coordinates.** The formula `MARGIN + (z.x - min_x) * inner_w // sx` normalizes the coordinate to a 0–1 range (by subtracting min and dividing by span), then scales it to the usable width, and adds the left margin. Same for y. |

### Step 2 — Center on screen (Lines 107–111)

| Line(s) | What it does |
|---------|-------------|
| 107–108 | Collect all raw screen x and y values. |
| 109 | Calculate horizontal offset `dx`: the difference between the screen center and the center of the bounding box of all raw positions. |
| 110 | Same for vertical offset `dy`. |
| 111 | Apply the centering offset to every position. This ensures the graph is centered in the window regardless of the original coordinate range. |

---

## 8 — `_begin_turn` Method (Lines 114–150)

```python
def _begin_turn(self) -> None:
    """Advance one logical turn and start animations."""
    if self.sim is None or self.finished:
        return
    if any(d[4] for d in self.drones.values()):
        return

    moves = self.sim.step()
    if not moves:
        self.finished = True
        return

    self.current_turn += 1
    print(" ".join(moves))

    for d in self.drones.values():
        d[1] = None   # move_from
        d[2] = None   # move_to
        d[3] = 0.0    # progress
        d[4] = False   # moving

    for token in moves:
        parts = token[1:].split("-")
        did = int(parts[0])
        d = self.drones[did]
        if len(parts) == 2:
            d[1] = d[0]      # move_from = current zone
            d[2] = parts[1]  # move_to
            d[3] = 0.0
            d[4] = True
        elif len(parts) == 3:
            d[1] = parts[1]
            d[2] = parts[2]
            d[3] = 0.0
            d[4] = True

    self.anim_elapsed = 0.0
```

This method advances the simulation by **one turn** and sets up the drone
animation data.

| Line(s) | What it does |
|---------|-------------|
| 116–117 | **Guard:** If the simulation is not initialized or already finished, do nothing. |
| 118–119 | **Guard:** If any drone is still animating (`d[4]` is `True` for "moving"), wait — do not advance to the next turn until all animations are done. |
| 121 | Call `self.sim.step()` — this asks the simulation engine to compute the next turn. It returns a list of move strings like `["D1-roof1", "D2-corridorA"]`. |
| 122–124 | If `step()` returns an empty list, there are no more moves — the simulation is finished. |
| 126 | Increment the turn counter. |
| 127 | **Print the moves to the terminal.** This is the required output format from the subject: `D1-roof1 D2-corridorA`. |
| 129–133 | **Reset all drone animation states.** Set `move_from`, `move_to`, `progress`, and `moving` to their idle values. |
| 135 | **Parse each move token.** A move looks like `D1-roof1`. We skip the first character (`D`) with `token[1:]`, then split by `-`. |
| 136 | `parts[0]` is the drone ID as a string (e.g., `"1"`). Convert it to an integer. |
| 137–138 | Get the drone's state list. |
| 139–143 | **Normal move (2 parts).** If the token splits into 2 parts (e.g., `["1", "roof1"]`): set `move_from` to the drone's current zone, `move_to` to the destination, reset progress to 0, and mark the drone as moving. |
| 144–148 | **Connection move (3 parts).** If the token splits into 3 parts (e.g., `["1", "roof1", "roof2"]`), this means the drone is on a connection between two zones (happens with restricted zones that take 2 turns). Set `move_from` and `move_to` to the two zone names. |
| 150 | Reset the animation clock to 0 — the animation for this turn starts now. |

---

## 9 — `_finalize_animations` Method (Lines 152–167)

```python
def _finalize_animations(self) -> None:
    """Snap drones that finished animating to destination."""
    for d in self.drones.values():
        if not d[4] or d[1] is None or d[2] is None:
            continue
        if d[3] >= 1.0:
            d[0] = d[2]
            d[1] = None
            d[2] = None
            d[3] = 0.0
            d[4] = False

    if self.sim is not None and all(
        dr.finished for dr in self.sim.drones
    ) and not any(d[4] for d in self.drones.values()):
        self.finished = True
```

| Line(s) | What it does |
|---------|-------------|
| 154–156 | Loop through every drone. Skip drones that are not moving or have no `move_from`/`move_to` set. |
| 157 | Check if `progress >= 1.0` — meaning the animation has reached 100%. |
| 158 | **Snap to destination:** set the drone's current zone (`d[0]`) to its `move_to` zone. |
| 159–162 | Reset the movement fields. The drone is now idle at its new zone. |
| 164–167 | **Check if the entire simulation is done.** If the simulation engine says all drones are finished AND no drone is still animating, mark the visualizer as finished. |

---

## 10 — `_update` Method (Lines 169–186)

```python
def _update(self, dt: float) -> None:
    """Run turns and animate movement."""
    if any(d[4] for d in self.drones.values()):
        self.anim_elapsed += dt
        p = min(1.0, self.anim_elapsed / ANIM_DURATION)
        smooth = p * p * (3.0 - 2.0 * p)
        for d in self.drones.values():
            if d[4]:
                d[3] = smooth
        self._finalize_animations()

    if not self.playing or self.finished:
        return

    self.turn_elapsed += dt
    if self.turn_elapsed >= TURN_INTERVAL:
        self.turn_elapsed = 0.0
        self._begin_turn()
```

This is the **main update function**, called every frame (60 times per second).

| Line(s) | What it does |
|---------|-------------|
| 171 | **If any drone is currently animating:** |
| 172 | Add `dt` (time since last frame, in seconds) to the animation clock. |
| 173 | Calculate linear progress `p` — a value from 0.0 to 1.0 based on how much of `ANIM_DURATION` has elapsed. `min(1.0, ...)` clamps it so it never exceeds 1.0. |
| 174 | **Smoothstep interpolation:** `p * p * (3 - 2p)` is a well-known easing function. It starts slow, speeds up in the middle, and slows down at the end. This makes drone movement look natural instead of robotic. |
| 175–177 | Apply the smoothed progress to every moving drone. |
| 178 | Call `_finalize_animations()` to snap any drone that reached progress 1.0. |
| 180–181 | If the simulation is paused or finished, skip the turn timer. |
| 183 | Accumulate `dt` into `turn_elapsed`. |
| 184–186 | When enough time has passed (≥ 0.70 seconds), reset the timer and start a new turn. |

---

## 11 — `_draw_edges` Method (Lines 190–204)

```python
def _draw_edges(self, surf: Surface) -> None:
    """Draw graph edges."""
    for a_name, neighbors in self.graph.adj.items():
        ax, ay = self.pos[a_name]
        for b_zone, conn in neighbors:
            b_name = b_zone.name
            if a_name >= b_name:
                continue
            bx, by = self.pos[b_name]
            key = (a_name, b_name) if a_name < b_name else (
                b_name, a_name
            )
            col = EDGE_PATH_COL if key in self.path_edges else EDGE_COL
            thick = max(1, 2 + conn.max_link_capacity - 1)
            pygame.draw.line(surf, col, (ax, ay), (bx, by), thick)
```

| Line(s) | What it does |
|---------|-------------|
| 192 | Loop over the adjacency list. Each entry is `(zone_name, list_of_neighbors)`. |
| 193 | Get the screen position of zone A. |
| 194 | Loop over all neighbors of A. Each neighbor is a tuple `(Zone_object, Connection_object)`. |
| 195 | Get the name of zone B. |
| 196–197 | **Avoid drawing each edge twice.** Since the graph is bidirectional, the edge A→B also appears as B→A. We only draw when `a_name < b_name` (alphabetically). |
| 198 | Get zone B's screen position. |
| 199–201 | Build a normalized key `(smaller_name, larger_name)` for looking up in `path_edges`. |
| 202 | Choose the color: **yellow** if this edge is on a drone path, otherwise **blue-gray**. |
| 203 | Calculate line thickness: base of 2 pixels, plus 1 for each extra unit of link capacity. Higher capacity connections appear thicker. |
| 204 | Draw the line on the surface. |

---

## 12 — `_draw_nodes` Method (Lines 206–229)

```python
def _draw_nodes(self, surf: Surface) -> None:
    """Draw zones as squares."""
    h = NODE_SIZE // 2
    for name, zone in self.graph.zones.items():
        x, y = self.pos[name]
        if zone.color == "rainbow":
            col = pygame.Color(255, 0, 255)
        else:
            try:
                col = pygame.Color(zone.color)
            except ValueError:
                col = pygame.Color("gray")
        rect = pygame.Rect(x - h, y - h, NODE_SIZE, NODE_SIZE)
        pygame.draw.rect(surf, col, rect)
        pygame.draw.rect(surf, NODE_BORDER, rect, 1)
        if zone.zone_type == "blocked":
            pygame.draw.line(
                surf, WHITE,
                (x - h + 3, y - h + 3), (x + h - 3, y + h - 3),
            )
            pygame.draw.line(
                surf, WHITE,
                (x - h + 3, y + h - 3), (x + h - 3, y - h + 3),
            )
```

| Line(s) | What it does |
|---------|-------------|
| 208 | `h` is half the node size (11 pixels). Used to center the square on the zone's position. |
| 209 | Loop over all zones in the graph. |
| 210 | Get the screen position of this zone. |
| 211–212 | **Special case:** if the zone's color string is `"rainbow"`, use magenta `(255, 0, 255)`. Pygame doesn't recognize "rainbow" as a color name. |
| 213–217 | **Normal case:** try to create a `pygame.Color` from the zone's color string (e.g., `"red"`, `"blue"`). If the string is invalid or empty, fall back to gray. |
| 218 | Create a rectangle centered on `(x, y)` with dimensions `NODE_SIZE × NODE_SIZE`. |
| 219 | Draw the filled rectangle with the zone's color. |
| 220 | Draw a 1-pixel black border around the rectangle. |
| 221–229 | **Blocked zone indicator:** if the zone type is `"blocked"`, draw a white **X** across the square. This makes it visually obvious that drones cannot enter this zone. The `+3` and `-3` offsets add padding so the X doesn't touch the edges. |

---

## 13 — `_drone_pos` Method (Lines 231–241)

```python
def _drone_pos(self, did: int) -> Tuple[float, float, float]:
    """Return interpolated drone position and angle."""
    d = self.drones[did]
    if not d[4] or d[1] is None or d[2] is None:
        zx, zy = self.pos[str(d[0])]
        return float(zx), float(zy), 0.0
    x1, y1 = self.pos[str(d[1])]
    x2, y2 = self.pos[str(d[2])]
    t = float(d[3])
    ang = -math.degrees(math.atan2(y2 - y1, x2 - x1))
    return x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, ang
```

This method calculates where a specific drone should be drawn **right now**,
including an angle for rotating the drone image.

| Line(s) | What it does |
|---------|-------------|
| 233 | Get the drone's 5-element state list. |
| 234–236 | **Not moving:** if the drone is idle (not moving, or missing `move_from`/`move_to`), return its current zone's screen position with angle 0. |
| 237–238 | **Moving:** get the screen coordinates of the source zone and the destination zone. |
| 239 | `t` is the animation progress (0.0 to 1.0), already smoothed by the `_update` method. |
| 240 | Calculate the angle of the movement direction using `atan2`. The negative sign flips the angle to match Pygame's coordinate system (y increases downward). |
| 241 | **Linear interpolation (lerp):** `x1 + (x2 - x1) * t` gives a position between source and destination based on progress `t`. When `t=0`, the drone is at the source; when `t=1`, it is at the destination. Returns `(x, y, angle)`. |

---

## 14 — `_draw_drones` Method (Lines 243–279)

```python
def _draw_drones(self, surf: Surface) -> None:
    """Draw all drones using the loaded texture."""
    buckets: Dict[Tuple[int, int], List[int]] = {}
    raw: Dict[int, Tuple[float, float, float]] = {}
    for did in self.drones:
        raw[did] = self._drone_pos(did)
        key = (int(raw[did][0]), int(raw[did][1]))
        buckets.setdefault(key, []).append(did)

    final: Dict[int, Tuple[float, float, float]] = {}
    for _, ids in buckets.items():
        if len(ids) == 1:
            final[ids[0]] = raw[ids[0]]
        else:
            cx, cy, a = raw[ids[0]]
            for i, d in enumerate(ids):
                t = 2.0 * math.pi * i / len(ids)
                ox = math.cos(t) * 12
                oy = math.sin(t) * 12
                final[d] = (cx + ox, cy + oy, a)

    font_sm = pygame.font.SysFont("", 18)
    sz = self.drone_img.get_width()
    for did in sorted(self.drones):
        x, y, angle = final[did]
        rotated = pygame.transform.rotate(self.drone_img, angle)
        rw, rh = rotated.get_size()
        surf.blit(rotated, (x - rw / 2, y - rh / 2))
        label = font_sm.render(str(did), True, WHITE)
        lw, lh = label.get_size()
        tag_x = int(x) - lw // 2 - 2
        tag_y = int(y) - sz // 2 - lh - 2
        pygame.draw.rect(
            surf, (0, 0, 0, 180),
            (tag_x, tag_y, lw + 4, lh + 2),
        )
        surf.blit(label, (tag_x + 2, tag_y + 1))
```

This method draws every drone with its image texture and ID label.

### Step 1 — Calculate positions and group overlapping drones (Lines 245–250)

| Line(s) | What it does |
|---------|-------------|
| 245 | `buckets` — Groups drones by their integer screen position. If two drones are at the same pixel, they end up in the same bucket. |
| 246 | `raw` — Stores each drone's exact floating-point position and angle. |
| 247–249 | For each drone, compute its position, truncate to integer for grouping, and add it to the appropriate bucket. |

### Step 2 — Spread overlapping drones in a circle (Lines 252–262)

| Line(s) | What it does |
|---------|-------------|
| 254 | If a bucket has only 1 drone, use its raw position directly. |
| 256–262 | If multiple drones overlap, **spread them in a circle** with radius 12 pixels. For `n` drones, each is placed at angle `2π × i / n` around the shared center. `math.cos` and `math.sin` compute the x and y offsets. This prevents drones from stacking on top of each other. |

### Step 3 — Draw each drone (Lines 264–279)

| Line(s) | What it does |
|---------|-------------|
| 264 | Create a small font (size 18) for the drone ID label. |
| 265 | Get the width of the drone image (36 pixels — set in `run()`). |
| 266 | Loop over all drones in sorted order (so drone 1 draws before drone 2, etc.). |
| 267 | Get this drone's final screen position and angle. |
| 268 | **Rotate** the drone image to face the direction of movement. Pygame's `rotate` creates a new rotated surface. |
| 269–270 | Center the rotated image on the drone's position by subtracting half its width and height. Blit (draw) it onto the surface. |
| 271 | Render the drone ID number as a text surface. |
| 272–274 | Calculate the position for the ID label tag — centered horizontally, placed above the drone image. |
| 275–278 | Draw a small semi-transparent black rectangle as a background for the ID label. This ensures the text is readable against any background. |
| 279 | Draw the ID text on top of the background rectangle. |

---

## 15 — `_draw_ui` Method (Lines 281–292)

```python
def _draw_ui(self, surf: Surface) -> None:
    """Draw turn counter and controls text."""
    font = pygame.font.SysFont("", 28)
    text = f"Turn: {self.current_turn}"
    if self.finished and self.current_turn > 0:
        text += " (Finished)"
    surf.blit(font.render(text, True, (230, 230, 230)), (20, 20))

    font_sm = pygame.font.SysFont("", 20)
    ctrl = "SPACE: Pause/Play  |  RIGHT: Step"
    surf.blit(font_sm.render(ctrl, True, (150, 150, 150)),
              (20, HEIGHT - 30))
```

| Line(s) | What it does |
|---------|-------------|
| 283 | Create a medium font (size 28) for the turn counter. |
| 284 | Build the text string: `"Turn: 3"`. |
| 285–286 | If the simulation is finished, append `" (Finished)"` to the text. |
| 287 | Render the text in light gray and draw it at the **top-left corner** (20, 20). |
| 289–292 | Create a smaller font (size 20) and render the control instructions at the **bottom-left corner**. This tells the user: press SPACE to pause/play, press RIGHT ARROW to step one turn manually. |

---

## 16 — `_draw` Method (Lines 294–300)

```python
def _draw(self, surf: Surface) -> None:
    """Render one frame."""
    surf.fill(BG)
    self._draw_edges(surf)
    self._draw_nodes(surf)
    self._draw_drones(surf)
    self._draw_ui(surf)
```

This is the **master draw function** called once per frame. It draws all layers in order:

1. **Fill background** — clear the screen with dark gray.
2. **Draw edges** — connection lines (behind everything).
3. **Draw nodes** — zone squares (on top of edges).
4. **Draw drones** — drone images (on top of nodes).
5. **Draw UI** — turn counter and controls (on top of everything).

---

## 17 — `run` Method — The Main Loop (Lines 303–335)

```python
def run(self) -> int:
    """Run the pygame main loop."""
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Fly-in Visualizer")
    clock = pygame.time.Clock()

    raw = pygame.image.load("drone.jpg").convert_alpha()
    self.drone_img = pygame.transform.smoothscale(raw, (36, 36))

    self.setup()

    running = True
    while running:
        dt = clock.tick(60) / 1000.0

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    running = False
                elif ev.key == pygame.K_SPACE:
                    self.playing = not self.playing
                elif ev.key == pygame.K_RIGHT:
                    self._begin_turn()

        self._update(dt)
        self._draw(screen)
        pygame.display.flip()

    pygame.quit()
    return 0
```

| Line(s) | What it does |
|---------|-------------|
| 305 | `pygame.init()` — Initialize all Pygame subsystems (display, audio, fonts, etc.). |
| 306 | Create the main window with size 1200×780 pixels. |
| 307 | Set the window title bar text to `"Fly-in Visualizer"`. |
| 308 | Create a `Clock` object for controlling frame rate. |
| 310 | Load the drone texture image from `drone.jpg` and convert it for fast blitting with alpha (transparency) support. |
| 311 | Scale the drone image to 36×36 pixels using smooth scaling (anti-aliased). |
| 313 | Call `setup()` to build positions, compute paths, and create the simulation engine. |
| 315–316 | **Main game loop.** Runs until `running` becomes `False`. |
| 317 | `clock.tick(60)` — Limits the loop to **60 frames per second** and returns the time elapsed since the last frame in milliseconds. Dividing by 1000 converts to seconds. `dt` is typically around 0.016 seconds. |
| 319–328 | **Event handling.** Poll all Pygame events: |
| 320–321 | `QUIT` event (user clicks the window close button) → stop the loop. |
| 323–324 | `ESCAPE` key → stop the loop. |
| 325–326 | `SPACE` key → toggle `self.playing` (pause/unpause the auto-advancing). |
| 327–328 | `RIGHT ARROW` key → manually trigger one simulation turn (step mode). |
| 330 | Call `_update(dt)` — advance animations and possibly start a new turn. |
| 331 | Call `_draw(screen)` — render the current frame to the screen surface. |
| 332 | `pygame.display.flip()` — swap the back buffer to the screen, making the frame visible. |
| 334 | `pygame.quit()` — clean up all Pygame resources. |
| 335 | Return `0` (success exit code). |

---

## 18 — `main` Function (Lines 338–349)

```python
def main() -> int:
    """CLI entrypoint."""
    if len(sys.argv) != 2:
        print("Usage: python3 visualizer.py <mapfile>", file=sys.stderr)
        return 2

    try:
        app = SimulationVisualizer(sys.argv[1])
        return app.run()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
```

| Line(s) | What it does |
|---------|-------------|
| 340–342 | **Argument check:** the program expects exactly one command-line argument — the map file path. If missing, print usage instructions to stderr and return exit code 2. |
| 344–346 | Create the visualizer with the map file and call `run()`. Return its exit code. |
| 347–349 | If any exception occurs (parsing error, file not found, pathfinding failure, etc.), print the error to stderr and return exit code 1. |

---

## 19 — `__main__` Block (Lines 352–356)

```python
if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nProgram exit\n")
```

| Line(s) | What it does |
|---------|-------------|
| 352 | Standard Python idiom: this block runs only when the file is executed directly (`python3 visualizer.py`), not when imported as a module. |
| 353–354 | Call `main()` and use its return value as the process exit code via `SystemExit`. |
| 355–356 | If the user presses **Ctrl+C**, catch the `KeyboardInterrupt` and print a clean exit message instead of a traceback. |

---

## Summary

The visualizer follows this pipeline:

```
Parse map file → Compute paths (pathfinder) → Build screen layout →
  Create simulation engine → Enter game loop:
  ╭──────────────────────────────────────────────────╮
  │  Every frame (60 FPS):                           │
  │    1. Handle keyboard events (SPACE, RIGHT, ESC) │
  │    2. Update animation progress (smoothstep)     │
  │    3. Advance turn if timer is ready             │
  │    4. Draw: background → edges → nodes → drones  │
  │    5. Display frame                              │
  ╰──────────────────────────────────────────────────╯
  Loop ends when: all drones reach end zone, or user quits.
```

Key design decisions:
- **Smoothstep interpolation** `p²(3 − 2p)` gives natural-looking drone movement.
- **Overlapping drones are spread in a circle** to remain visible.
- **Edges used by drone paths are highlighted in yellow** for clarity.
- **Blocked zones get a white X** so the corrector can immediately see them.
- The output format (`D1-roof1 D2-corridorA`) is printed to terminal alongside
  the graphical display, satisfying the subject's output requirements.
