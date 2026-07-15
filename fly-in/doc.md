# Visualizer.py — Full Line-by-Line Explanation

This document explains every single line of `visualizer.py` in simple, easy-to-understand English.
The file creates a **Pygame window** that shows drones moving across a graph (map) from a start zone to an end zone.

---

## Section 1: Imports (Lines 1–11)

```python
from __future__ import annotations
```
This lets us use modern type hints (like `Dict[str, int]`) even in older Python versions. It tells Python: "treat all annotations as strings first, evaluate them later."

```python
import math
```
We import the `math` module. We need it later for things like `math.cos`, `math.sin`, `math.atan2`, and `math.pi` — all used to calculate drone positions and rotation angles.

```python
import sys
```
We import `sys` to read command-line arguments (`sys.argv`) and to print error messages to `sys.stderr`.

```python
from typing import Dict, List, Optional, Tuple
```
We import type hint helpers:
- `Dict` — a dictionary type, like `Dict[str, int]` means "a dict with string keys and int values."
- `List` — a list type, like `List[str]` means "a list of strings."
- `Optional` — means "this value can be `None`," like `Optional[Simulation]` means "either a `Simulation` or `None`."
- `Tuple` — a fixed-size group of values, like `Tuple[int, int]` means "two integers."

```python
import pygame
```
We import the `pygame` library. This is the graphics engine that opens the window, draws shapes, handles keyboard input, and runs the animation loop.

```python
from parser import MapParser
```
We import `MapParser` from our own `parser.py` file. This class reads a map file and returns the graph structure (zones, connections, start, end, number of drones).

```python
from pathfinder import MultiPathFinder
```
We import `MultiPathFinder` from our `pathfinder.py` file. This class finds the best paths for all drones from start to end.

```python
from simulator import Simulation
```
We import `Simulation` from our `simulator.py` file. This class runs the turn-by-turn simulation — it decides which drone moves where on each turn.

---

## Section 2: Color Constants (Lines 13–24)

```python
BG = (0, 0, 0)
```
`BG` is the **background color**. `(0, 0, 0)` is pure black in RGB (Red=0, Green=0, Blue=0).

```python
EDGE_COL = (130, 145, 180)
```
`EDGE_COL` is the color for **normal edges** (connections between zones that are NOT part of any drone path). It is a soft blue-gray.

```python
EDGE_PATH_COL = (255, 220, 120)
```
`EDGE_PATH_COL` is the color for **path edges** — connections that ARE part of a drone's assigned route. It is a warm yellow-gold so they stand out.

```python
NODE_BORDER = (0, 0, 0)
```
`NODE_BORDER` is the border color drawn around each zone square. Set to black, which blends with the background for a clean look.

```python
COL_START = (70, 235, 145)
```
`COL_START` is the color for the **start zone**. It is a bright green.

```python
COL_END = (210, 105, 255)
```
`COL_END` is the color for the **end zone**. It is a vivid purple.

```python
COL_NORMAL = (78, 131, 255)
```
`COL_NORMAL` is the color for a **normal zone** (no special rules). It is blue.

```python
COL_PRIORITY = (0, 212, 255)
```
`COL_PRIORITY` is the color for a **priority zone** (drone must leave as fast as possible). It is cyan / light blue.

```python
COL_RESTRICTED = (255, 176, 79)
```
`COL_RESTRICTED` is the color for a **restricted zone** (only one drone can be inside at a time). It is orange.

```python
COL_BLOCKED = (255, 92, 92)
```
`COL_BLOCKED` is the color for a **blocked zone** (no drone can enter). It is red.

```python
WHITE = (255, 255, 255)
```
`WHITE` is plain white. Used for text labels and the "X" mark on blocked zones.

---

## Section 3: Type Alias (Line 26)

```python
Color = Tuple[int, int, int]
```
We create a shortcut name: `Color` means "a tuple of 3 integers." This makes type hints more readable — instead of writing `Tuple[int, int, int]` everywhere, we just write `Color`.

---

## Section 4: Layout and Timing Constants (Lines 28–39)

```python
WIDTH, HEIGHT = 1200, 780
```
The window is **1200 pixels wide** and **780 pixels tall**.

```python
MARGIN = 80
```
We leave **80 pixels** of empty space on each side of the window. This prevents zones from being drawn too close to the edges.

```python
NODE_SIZE = 22
```
Each zone is drawn as a **22×22 pixel square**.

```python
TURN_INTERVAL = 0.70
```
The simulation waits **0.70 seconds** (700 milliseconds) between each turn. This controls the overall speed of the simulation.

```python
ANIM_DURATION = 0.55
```
Each drone animation (moving from one zone to the next) takes **0.55 seconds**. This must be less than `TURN_INTERVAL` so the drone finishes moving before the next turn starts.

```python
DRONE_PALETTE: List[Color] = [
    (255, 99, 132), (54, 162, 235), (255, 206, 86),
    (75, 192, 192), (153, 102, 255), (255, 159, 64),
    (46, 204, 113), (231, 76, 60),
]
```
`DRONE_PALETTE` is a list of 8 colors. Each drone could use a different color from this palette. The colors are: pink, blue, yellow, teal, purple, orange, green, and red. (Note: this palette is defined but the current drawing code uses a drone image instead of colored circles.)

---

## Section 5: The `SimulationVisualizer` Class (Line 42)

```python
class SimulationVisualizer:
    """Visualizer with smooth drone movement over connections."""
```
This is the main class. It contains everything: the map data, the simulation logic, the drawing code, and the main loop. The docstring tells us it shows **smooth drone movement** — drones slide from zone to zone instead of teleporting.

---

## Section 6: `__init__` — Constructor (Lines 45–63)

```python
def __init__(self, mapfile: str) -> None:
    """Initialize visualizer and load map."""
```
The constructor takes one argument: `mapfile` — the path to the map file (like `"maps/map1.txt"`). It returns nothing (`None`).

```python
    p = MapParser()
    self.nb_drones, self.start, self.end, self.graph = p.parse_file(
        mapfile
    )
```
We create a `MapParser` and call `parse_file()`. This reads the map file and returns 4 things:
- `nb_drones` — how many drones we have (an integer).
- `start` — the name of the start zone (a string like `"S"`).
- `end` — the name of the end zone (a string like `"E"`).
- `graph` — the full graph object with all zones and connections.

```python
    self.assignments: List[List[str]] = []
```
`assignments` will hold the path for each drone. For example, `[["S", "A", "B", "E"], ["S", "C", "E"]]` means drone 1 goes S→A→B→E and drone 2 goes S→C→E. It starts empty.

```python
    self.sim: Optional[Simulation] = None
```
`sim` will hold the `Simulation` object. It is `None` right now because we haven't set it up yet.

```python
    self.pos: Dict[str, Tuple[int, int]] = {}
```
`pos` will map each zone name to its pixel position on screen. For example: `{"S": (100, 200), "A": (300, 400)}`. Empty for now.

```python
    self.path_edges: set[Tuple[str, str]] = set()
```
`path_edges` will store which edges are part of a drone path. Each edge is stored as a tuple of two zone names sorted alphabetically, like `("A", "B")`. This is a set so lookups are fast.

```python
    self.playing = True
```
`playing` controls whether the simulation auto-advances. When `True`, turns happen automatically. The user can press SPACE to toggle this.

```python
    self.finished = False
```
`finished` becomes `True` when all drones have reached the end zone.

```python
    self.current_turn = 0
```
`current_turn` counts how many turns have passed. Starts at 0.

```python
    self.turn_elapsed = 0.0
```
`turn_elapsed` tracks how many seconds have passed since the last turn. When it reaches `TURN_INTERVAL`, a new turn begins.

```python
    self.anim_elapsed = 0.0
```
`anim_elapsed` tracks how many seconds have passed since the current animation started.

```python
    # drone id -> (zone, move_from, move_to, progress, moving)
    self.drones: Dict[int, List[object]] = {}
```
`drones` is a dictionary that maps each drone's ID (1, 2, 3...) to a list of 5 values:
- `[0]` = `zone` — the zone the drone is currently in (a string).
- `[1]` = `move_from` — where the drone is moving FROM (or `None` if not moving).
- `[2]` = `move_to` — where the drone is moving TO (or `None` if not moving).
- `[3]` = `progress` — a float from 0.0 to 1.0 showing how far the animation is (0 = at start, 1 = at destination).
- `[4]` = `moving` — a boolean. `True` if the drone is currently animating.

---

## Section 7: `setup()` — Prepare Everything (Lines 66–88)

```python
def setup(self) -> None:
    """Build layout, allocate paths, init drone states."""
```
This method does 3 things: calculates positions, finds paths, and initializes drones.

```python
    self._build_positions()
```
Call `_build_positions()` to convert zone world coordinates into screen pixel positions.

```python
    finder = MultiPathFinder(self.graph)
    alloc = finder.drone_waste(
        start=self.start, end=self.end,
        nb_drones=self.nb_drones, max_paths=8,
    )
```
We create a `MultiPathFinder` with our graph, then call `drone_waste()`. This finds up to 8 different paths from start to end and assigns drones to them. The result `alloc` contains the assignments.

```python
    if not alloc.assignments:
        raise ValueError("No valid path allocation")
```
If no paths were found, we raise an error. The simulation cannot run without paths.

```python
    self.assignments = alloc.assignments
    self.sim = Simulation(self.graph, self.assignments)
```
We save the assignments and create the `Simulation` object. The simulation uses the graph and assignments to decide moves each turn.

```python
    for path in self.assignments:
        for i in range(len(path) - 1):
            a, b = path[i], path[i + 1]
            self.path_edges.add((a, b) if a < b else (b, a))
```
For each path, we look at every consecutive pair of zones (e.g., `S→A`, `A→B`, `B→E`). We add each pair to `path_edges`, sorted alphabetically so `("A", "B")` and `("B", "A")` are stored the same way. This lets us draw path edges in a different color later.

```python
    for did in range(1, self.nb_drones + 1):
        # [zone, move_from, move_to, progress, moving]
        self.drones[did] = [self.start, None, None, 0.0, False]
```
We create an entry for each drone. All drones start at the `start` zone, not moving (`None, None, 0.0, False`).

---

## Section 8: `_build_positions()` — Map Coordinates to Screen (Lines 91–113)

```python
def _build_positions(self) -> None:
    """Convert world coords to centered screen coords."""
```
This method converts the zone coordinates from the map file into pixel positions on screen.

```python
    zones = self.graph.zones
```
Get the dictionary of all zones from the graph.

```python
    xs = [z.x for z in zones.values()]
    ys = [z.y for z in zones.values()]
```
Collect all X coordinates into a list and all Y coordinates into another list.

```python
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
```
Find the smallest and largest X and Y values. This tells us the bounding box of the map.

```python
    sx = max(1, max_x - min_x)
    sy = max(1, max_y - min_y)
```
Calculate the span (range) in X and Y. We use `max(1, ...)` to prevent division by zero if all zones have the same X or Y.

```python
    inner_w = WIDTH - 2 * MARGIN
    inner_h = HEIGHT - 2 * MARGIN
```
Calculate the drawable area: the window size minus margins on both sides. For example: `1200 - 2*80 = 1040` pixels wide and `780 - 160 = 620` pixels tall.

```python
    raw: Dict[str, Tuple[int, int]] = {}
    for name, z in zones.items():
        px = MARGIN + (z.x - min_x) * inner_w // sx
        py = MARGIN + (z.y - min_y) * inner_h // sy
        raw[name] = (px, py)
```
For each zone, we map its world coordinate to a screen pixel:
- **Formula**: `MARGIN + (value - min_value) * inner_size // span`
- This scales the zone position proportionally into the drawable area.
- `//` is integer division (we need whole pixel values).

```python
    rxs = [p[0] for p in raw.values()]
    rys = [p[1] for p in raw.values()]
    dx = WIDTH // 2 - (min(rxs) + max(rxs)) // 2
    dy = HEIGHT // 2 - (min(rys) + max(rys)) // 2
```
We center the graph on screen. We find the center of all zone positions and calculate how much to shift (`dx`, `dy`) to move that center to the screen center.

```python
    self.pos = {n: (x + dx, y + dy) for n, (x, y) in raw.items()}
```
Apply the shift to every zone position and save the final result.

---

## Section 9: `_begin_turn()` — Start a New Turn (Lines 116–152)

```python
def _begin_turn(self) -> None:
    """Advance one logical turn and start animations."""
```
This method runs one simulation turn and sets up the drone animations.

```python
    if self.sim is None or self.finished:
        return
```
If there is no simulation or the simulation is already finished, do nothing.

```python
    if any(d[4] for d in self.drones.values()):
        return
```
If any drone is still animating (moving), do NOT start a new turn. Wait for all animations to finish first.

```python
    moves = self.sim.step()
```
Call `step()` on the simulation. This returns a list of move tokens like `["D1-A", "D2-B-C"]`. Each token describes one drone's move.

```python
    if not moves:
        self.finished = True
        return
```
If no moves were returned, the simulation is done. Mark `finished = True`.

```python
    self.current_turn += 1
    print(" ".join(moves))
```
Increment the turn counter and print the moves to the terminal (for debugging and logging).

```python
    for d in self.drones.values():
        d[1] = None   # move_from
        d[2] = None   # move_to
        d[3] = 0.0    # progress
        d[4] = False   # moving
```
Reset all drones to "not moving." This clears the previous turn's animation data.

```python
    for token in moves:
        parts = token[1:].split("-")
        did = int(parts[0])
        d = self.drones[did]
```
For each move token (like `"D1-A"` or `"D2-B-C"`):
- `token[1:]` removes the first character (`"D"`), giving us `"1-A"` or `"2-B-C"`.
- `.split("-")` splits by dashes: `["1", "A"]` or `["2", "B", "C"]`.
- `parts[0]` is the drone ID (as a string), which we convert to an integer.
- We look up the drone's data list.

```python
        if len(parts) == 2:
            d[1] = d[0]      # move_from = current zone
            d[2] = parts[1]  # move_to
            d[3] = 0.0
            d[4] = True
```
If the token has 2 parts (like `["1", "A"]`), the drone moves from its current zone to zone `"A"`:
- `d[1]` = where it is now (move_from).
- `d[2]` = where it is going (move_to).
- `d[3]` = animation progress starts at 0.
- `d[4]` = mark as moving.

```python
        elif len(parts) == 3:
            d[1] = parts[1]
            d[2] = parts[2]
            d[3] = 0.0
            d[4] = True
```
If the token has 3 parts (like `["2", "B", "C"]`), the drone moves from zone `"B"` to zone `"C"`. This format is used when the from-zone is explicitly specified.

```python
    self.anim_elapsed = 0.0
```
Reset the animation timer to 0. The animation starts now.

---

## Section 10: `_finalize_animations()` — Finish Animations (Lines 154–169)

```python
def _finalize_animations(self) -> None:
    """Snap drones that finished animating to destination."""
```
This method checks if any drone's animation is complete and "snaps" it to the destination.

```python
    for d in self.drones.values():
        if not d[4] or d[1] is None or d[2] is None:
            continue
```
Skip drones that are not moving or have no valid from/to zones.

```python
        if d[3] >= 1.0:
            d[0] = d[2]
            d[1] = None
            d[2] = None
            d[3] = 0.0
            d[4] = False
```
If the animation progress reached 1.0 (100% complete):
- Set the drone's current zone to the destination (`d[2]`).
- Clear the movement data.
- Mark it as no longer moving.

```python
    if self.sim is not None and all(
        dr.finished for dr in self.sim.drones
    ) and not any(d[4] for d in self.drones.values()):
        self.finished = True
```
After finalizing, check if ALL drones in the simulation are finished AND no drone is still animating. If both conditions are true, the entire simulation is done.

---

## Section 11: `_update()` — Per-Frame Update (Lines 171–188)

```python
def _update(self, dt: float) -> None:
    """Run turns and animate movement."""
```
This is called every frame. `dt` is the time in seconds since the last frame (e.g., 0.016 for 60 FPS).

```python
    if any(d[4] for d in self.drones.values()):
        self.anim_elapsed += dt
        p = min(1.0, self.anim_elapsed / ANIM_DURATION)
        smooth = p * p * (3.0 - 2.0 * p)
```
If any drone is animating:
- Add `dt` to the animation timer.
- Calculate `p` — the linear progress from 0.0 to 1.0. We cap it at 1.0.
- Calculate `smooth` — this is a **smoothstep function**: `3p² - 2p³`. It makes the animation start slow, speed up in the middle, and slow down at the end. This looks much smoother than linear movement.

```python
        for d in self.drones.values():
            if d[4]:
                d[3] = smooth
        self._finalize_animations()
```
Update every moving drone's progress to the smooth value, then check if any animation is complete.

```python
    if not self.playing or self.finished:
        return
```
If the simulation is paused or finished, do NOT auto-advance turns.

```python
    self.turn_elapsed += dt
    if self.turn_elapsed >= TURN_INTERVAL:
        self.turn_elapsed = 0.0
        self._begin_turn()
```
Accumulate time. When enough time has passed (`TURN_INTERVAL`), start a new turn and reset the timer.

---

## Section 12: `_zone_color()` — Choose Zone Color (Lines 191–203)

```python
def _zone_color(self, name: str, ztype: str) -> Color:
    """Return zone color by role / type."""
```
This method picks the right color for a zone based on its name and type.

```python
    if name == self.start:
        return COL_START
    if name == self.end:
        return COL_END
```
If this zone is the start zone, use green. If it's the end zone, use purple. These override the zone type.

```python
    mapping: Dict[str, Color] = {
        "normal": COL_NORMAL,
        "priority": COL_PRIORITY,
        "restricted": COL_RESTRICTED,
        "blocked": COL_BLOCKED,
    }
    return mapping.get(ztype, COL_NORMAL)
```
For other zones, look up the color in the `mapping` dictionary. If the zone type is not found (unknown), default to `COL_NORMAL` (blue).

---

## Section 13: `_draw_edges()` — Draw Connections (Lines 207–221)

```python
def _draw_edges(self, surf: pygame.Surface) -> None:
    """Draw graph edges."""
```
This method draws lines between connected zones.

```python
    for a_name, neighbors in self.graph.adj.items():
        ax, ay = self.pos[a_name]
```
Loop through every zone and its neighbors in the adjacency list. Get the pixel position of zone `a`.

```python
        for b_zone, conn in neighbors:
            b_name = b_zone.name
            if a_name >= b_name:
                continue
```
For each neighbor: get its name. The `if a_name >= b_name: continue` trick ensures we draw each edge only once (not twice from both sides).

```python
            bx, by = self.pos[b_name]
            key = (a_name, b_name) if a_name < b_name else (
                b_name, a_name
            )
```
Get zone B's position. Create a sorted key to check if this edge is part of a drone path.

```python
            col = EDGE_PATH_COL if key in self.path_edges else EDGE_COL
```
If this edge is in `path_edges`, use the gold color. Otherwise, use the default gray-blue.

```python
            thick = max(1, 2 + conn.max_link_capacity - 1)
```
Calculate line thickness based on the edge's capacity. Higher capacity = thicker line. Minimum thickness is 1.

```python
            pygame.draw.line(surf, col, (ax, ay), (bx, by), thick)
```
Draw the line on the surface from zone A's position to zone B's position.

---

## Section 14: `_draw_nodes()` — Draw Zones (Lines 223–240)

```python
def _draw_nodes(self, surf: pygame.Surface) -> None:
    """Draw zones as squares."""
```
This method draws each zone as a colored square.

```python
    h = NODE_SIZE // 2
```
`h` is half the node size (11 pixels). We use it to center the square on the zone's position.

```python
    for name, zone in self.graph.zones.items():
        x, y = self.pos[name]
        col = self._zone_color(name, zone.zone_type)
        rect = pygame.Rect(x - h, y - h, NODE_SIZE, NODE_SIZE)
```
For each zone: get its screen position, determine its color, and create a rectangle centered on that position.

```python
        pygame.draw.rect(surf, col, rect)
        pygame.draw.rect(surf, NODE_BORDER, rect, 1)
```
Draw the filled rectangle, then draw a 1-pixel border on top.

```python
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
If the zone is blocked, draw a white **"X"** on top of it. The X is drawn with 3 pixels of padding from the edges so it doesn't touch the border.

---

## Section 15: `_drone_pos()` — Calculate Drone Position (Lines 242–252)

```python
def _drone_pos(self, did: int) -> Tuple[float, float, float]:
    """Return interpolated drone position and angle."""
```
This method returns the drone's current screen position `(x, y)` and its rotation angle.

```python
    d = self.drones[did]
    if not d[4] or d[1] is None or d[2] is None:
        zx, zy = self.pos[str(d[0])]
        return float(zx), float(zy), 0.0
```
If the drone is NOT moving, return the position of its current zone with angle 0 (facing right).

```python
    x1, y1 = self.pos[str(d[1])]
    x2, y2 = self.pos[str(d[2])]
    t = float(d[3])
```
If the drone IS moving, get the positions of the from-zone and to-zone, and the animation progress `t` (0.0 to 1.0).

```python
    ang = -math.degrees(math.atan2(y2 - y1, x2 - x1))
```
Calculate the angle the drone should face. `atan2` gives the angle in radians, `degrees()` converts it. The negative sign is because Pygame's Y-axis is flipped (Y increases downward).

```python
    return x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, ang
```
**Linear interpolation (lerp)**: the drone's position is `start + (end - start) * t`. When `t=0`, the drone is at the start. When `t=1`, it's at the end. Values in between give smooth positions along the line.

---

## Section 16: `_draw_drones()` — Draw All Drones (Lines 254–290)

```python
def _draw_drones(self, surf: pygame.Surface) -> None:
    """Draw all drones using the loaded texture."""
```
This method draws every drone on screen.

```python
    buckets: Dict[Tuple[int, int], List[int]] = {}
    raw: Dict[int, Tuple[float, float, float]] = {}
    for did in self.drones:
        raw[did] = self._drone_pos(did)
        key = (int(raw[did][0]), int(raw[did][1]))
        buckets.setdefault(key, []).append(did)
```
First, calculate every drone's position. Then group drones by their pixel position using "buckets." This detects when multiple drones are at the same spot.

```python
    final: Dict[int, Tuple[float, float, float]] = {}
    for _bkey, ids in buckets.items():
        if len(ids) == 1:
            final[ids[0]] = raw[ids[0]]
```
If only one drone is at a position, use its position as-is.

```python
        else:
            cx, cy, a = raw[ids[0]]
            for i, d in enumerate(ids):
                t = 2.0 * math.pi * i / len(ids)
                ox = math.cos(t) * 12
                oy = math.sin(t) * 12
                final[d] = (cx + ox, cy + oy, a)
```
If multiple drones overlap, spread them in a circle (radius 12 pixels) around the center point. Each drone gets an equal angle around the circle. This prevents drones from hiding behind each other.

```python
    font_sm = pygame.font.SysFont(None, 18)
    sz = self.drone_img.get_width()
```
Create a small font (size 18) for the drone ID labels. Get the drone image width.

```python
    for did in sorted(self.drones):
        x, y, angle = final[did]
        rotated = pygame.transform.rotate(self.drone_img, angle)
        rw, rh = rotated.get_size()
        surf.blit(rotated, (x - rw / 2, y - rh / 2))
```
For each drone (sorted by ID for consistent draw order):
- Get its final position and angle.
- Rotate the drone image by that angle.
- Get the rotated image size (rotation changes dimensions).
- Draw the image centered on the drone's position.

```python
        label = font_sm.render(str(did), True, WHITE)
        lw, lh = label.get_size()
        tag_x = int(x) - lw // 2 - 2
        tag_y = int(y) - sz // 2 - lh - 2
```
Render the drone's ID number as white text. Calculate the position for the label: centered horizontally above the drone image.

```python
        pygame.draw.rect(
            surf, (0, 0, 0, 180),
            (tag_x, tag_y, lw + 4, lh + 2),
        )
        surf.blit(label, (tag_x + 2, tag_y + 1))
```
Draw a semi-transparent black rectangle behind the label (for readability), then draw the label text on top.

---

## Section 17: `_draw_ui()` — Draw HUD / Interface (Lines 292–303)

```python
def _draw_ui(self, surf: pygame.Surface) -> None:
    """Draw turn counter and controls text."""
```
This method draws the on-screen user interface elements.

```python
    font = pygame.font.SysFont(None, 28)
    text = f"Turn: {self.current_turn}"
    if self.finished and self.current_turn > 0:
        text += " (Finished)"
    surf.blit(font.render(text, True, (230, 230, 230)), (20, 20))
```
Create a font (size 28). Build the turn text (e.g., `"Turn: 5"`). If the simulation is done, add `" (Finished)"`. Draw it in light gray at the top-left corner (20, 20).

```python
    font_sm = pygame.font.SysFont(None, 20)
    ctrl = "SPACE: Pause/Play  |  RIGHT: Step"
    surf.blit(font_sm.render(ctrl, True, (150, 150, 150)),
              (20, HEIGHT - 30))
```
Draw the controls help text at the bottom-left in medium gray. This tells the user which keys to press.

---

## Section 18: `_draw()` — Full Frame Render (Lines 305–311)

```python
def _draw(self, surf: pygame.Surface) -> None:
    """Render one frame."""
    surf.fill(BG)
    self._draw_edges(surf)
    self._draw_nodes(surf)
    self._draw_drones(surf)
    self._draw_ui(surf)
```
This is the master draw method. It runs every frame and does 5 things in order:
1. **Fill** the screen with the background color (black).
2. **Draw edges** (lines between zones).
3. **Draw nodes** (zone squares) on top of the edges.
4. **Draw drones** on top of everything.
5. **Draw UI** (turn counter and controls) on the very top.

The draw order matters! Later things are drawn on top of earlier things.

---

## Section 19: `run()` — The Main Loop (Lines 314–346)

```python
def run(self) -> int:
    """Run the pygame main loop."""
```
This is where the application runs. It returns 0 on success.

```python
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Fly-in Visualizer")
    clock = pygame.time.Clock()
```
- `pygame.init()` starts the Pygame engine (graphics, sound, etc.).
- `set_mode()` creates the window with the specified size.
- `set_caption()` sets the window title.
- `Clock()` creates a clock to control the frame rate.

```python
    raw = pygame.image.load("drone.jpg").convert_alpha()
    self.drone_img = pygame.transform.smoothscale(raw, (36, 36))
```
Load the drone image from `"drone.jpg"`. `convert_alpha()` enables transparency. Then scale it down to 36×36 pixels using smooth scaling (no pixelation).

```python
    self.setup()
```
Run the full setup: calculate positions, find paths, initialize drones.

```python
    running = True
    while running:
        dt = clock.tick(60) / 1000.0
```
Start the main loop. `clock.tick(60)` limits the loop to 60 frames per second and returns the time since the last frame in milliseconds. We divide by 1000 to get seconds.

```python
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
```
Process all events. If the user clicks the window's X button, stop the loop.

```python
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    running = False
```
If the user presses **Escape**, stop the loop and close the window.

```python
                elif ev.key == pygame.K_SPACE:
                    self.playing = not self.playing
```
If the user presses **Space**, toggle between play and pause.

```python
                elif ev.key == pygame.K_RIGHT:
                    self._begin_turn()
```
If the user presses the **Right arrow**, manually trigger one turn (step-by-step mode).

```python
        self._update(dt)
        self._draw(screen)
        pygame.display.flip()
```
- `_update(dt)` — run the simulation logic and animate drones.
- `_draw(screen)` — draw everything to the screen surface.
- `flip()` — show the drawn frame on the actual monitor. Without this, nothing would be visible.

```python
    pygame.quit()
    return 0
```
After the loop ends, shut down Pygame and return 0 (success).

---

## Section 20: `main()` — CLI Entry Point (Lines 349–360)

```python
def main() -> int:
    """CLI entrypoint."""
    if len(sys.argv) != 2:
        print("Usage: python3 visualizer.py <mapfile>", file=sys.stderr)
        return 2
```
The `main()` function is what runs when you execute the script from the terminal. It checks that exactly one argument was given (the map file path). If not, it prints a usage message to stderr and returns error code 2.

```python
    try:
        app = SimulationVisualizer(sys.argv[1])
        return app.run()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
```
Create the visualizer with the map file, then run it. If anything goes wrong (bad file, no paths, etc.), catch the exception, print the error, and return error code 1.

---

## Section 21: Script Guard (Lines 363–364)

```python
if __name__ == "__main__":
    raise SystemExit(main())
```
This is the standard Python script guard. It says: "If this file is being run directly (not imported), call `main()` and use its return value as the exit code." `raise SystemExit(0)` exits cleanly; `raise SystemExit(1)` or `raise SystemExit(2)` signals an error.

---

## Summary

| Section | Purpose |
|---|---|
| **Imports** | Load libraries: `pygame`, `math`, `sys`, and project modules |
| **Colors** | Define RGB tuples for every visual element |
| **Constants** | Window size, margins, timing, palette |
| **`__init__`** | Parse the map file and initialize all state variables |
| **`setup`** | Calculate positions, find paths, create simulation, init drones |
| **`_build_positions`** | Scale and center zone coordinates to fit the screen |
| **`_begin_turn`** | Run one simulation step and prepare drone animations |
| **`_finalize_animations`** | Snap completed animations and check if simulation is done |
| **`_update`** | Per-frame logic: smoothstep animation + auto-advance turns |
| **`_zone_color`** | Pick the correct color for each zone type |
| **`_draw_edges`** | Draw lines between connected zones |
| **`_draw_nodes`** | Draw zone squares with "X" marks on blocked zones |
| **`_drone_pos`** | Interpolate a drone's current position during animation |
| **`_draw_drones`** | Draw rotated drone images with ID labels |
| **`_draw_ui`** | Draw the turn counter and keyboard controls text |
| **`_draw`** | Master draw: clear screen, then edges → nodes → drones → UI |
| **`run`** | Main loop: events → update → draw → flip at 60 FPS |
| **`main`** | Parse CLI args and handle errors |
