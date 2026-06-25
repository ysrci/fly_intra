from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pyray as rl

from models import ZoneType
from parser import parse_file
from pathfinder import MultiPathFinder
from simulator import Simulation


@dataclass
class ViewConfig:
    """Window and animation configuration."""

    width: int = 1200
    height: int = 780
    margin: int = 80

    node_size: int = 22
    drone_radius: float = 11.0

    # logical turn duration (simulation step)
    turn_interval: float = 0.70
    # visual animation duration for movement between two turns
    anim_duration: float = 0.55


class Theme:
    """Color palette."""

    BG = (14, 17, 27, 255)
    GRID = (40, 46, 66, 70)

    EDGE = (130, 145, 180, 170)
    EDGE_PATH = (255, 220, 120, 230)

    NODE_BORDER = (8, 10, 16, 255)
    START = (70, 235, 145, 255)
    END = (210, 105, 255, 255)
    NORMAL = (78, 131, 255, 255)
    PRIORITY = (0, 212, 255, 255)
    RESTRICTED = (255, 176, 79, 255)
    BLOCKED = (255, 92, 92, 255)


@dataclass
class DroneVisualState:
    """Visual state for one drone."""

    # current anchored node when idle
    zone: str
    # movement endpoints for animation
    move_from: Optional[str] = None
    move_to: Optional[str] = None
    # progress in [0..1]
    progress: float = 0.0
    # if True, drone is currently animating on edge
    moving: bool = False
    # current rotation angle in degrees
    angle: float = 0.0


class SimulationVisualizer:
    """Visualizer with smooth drone movement over connections."""

    def __init__(self, mapfile: str) -> None:
        """Initialize visualizer and load map."""
        self.mapfile = mapfile
        self.nb_drones, self.start, self.end, self.graph = parse_file(mapfile)

        self.cfg = ViewConfig()
        self.theme = Theme()

        self.assignments: List[List[str]] = []
        self.sim: Optional[Simulation] = None

        self.pos: Dict[str, Tuple[int, int]] = {}
        self.path_edges: set[Tuple[str, str]] = set()

        self.playing: bool = True
        self.finished: bool = False
        self.current_turn: int = 0
        self.turn_elapsed: float = 0.0
        self.anim_elapsed: float = 0.0

        self.drones: Dict[int, DroneVisualState] = {}

    # ---------- setup ----------
    def setup(self) -> None:
        """Build graph layout, allocate paths, and initialize states."""
        self._build_positions()

        finder = MultiPathFinder(self.graph)
        alloc = finder.allocate_drones(
            start=self.start,
            end=self.end,
            nb_drones=self.nb_drones,
            max_paths=8,
        )
        if not alloc.assignments:
            raise ValueError("No valid path allocation from start to end")

        self.assignments = alloc.assignments
        self.sim = Simulation(self.graph, self.assignments)

        self._build_path_edge_overlay()

        for drone_id in range(1, self.nb_drones + 1):
            self.drones[drone_id] = DroneVisualState(zone=self.start)

    # ---------- geometry ----------
    def _compute_bounds(self) -> Tuple[int, int, int, int]:
        """Return world coordinate bounds."""
        xs = [z.x for z in self.graph.zones.values()]
        ys = [z.y for z in self.graph.zones.values()]
        return min(xs), max(xs), min(ys), max(ys)

    def _world_to_screen(
        self, x: int, y: int, bounds: Tuple[int, int, int, int]
    ) -> Tuple[int, int]:
        """Convert world coordinates to screen coordinates."""
        min_x, max_x, min_y, max_y = bounds
        sx_span = max(1, max_x - min_x)
        sy_span = max(1, max_y - min_y)

        w_inner = self.cfg.width - 2 * self.cfg.margin
        h_inner = self.cfg.height - 2 * self.cfg.margin
        sx = self.cfg.margin + (x - min_x) * w_inner / sx_span
        sy = self.cfg.margin + (y - min_y) * h_inner / sy_span
        return int(sx), int(sy)

    def _build_positions(self) -> None:
        """Build and center node positions."""
        bounds = self._compute_bounds()
        raw = {
            name: self._world_to_screen(z.x, z.y, bounds)
            for name, z in self.graph.zones.items()
        }

        xs = [p[0] for p in raw.values()]
        ys = [p[1] for p in raw.values()]
        graph_cx = (min(xs) + max(xs)) // 2
        graph_cy = (min(ys) + max(ys)) // 2

        dx = self.cfg.width // 2 - graph_cx
        dy = self.cfg.height // 2 - graph_cy

        self.pos = {name: (x + dx, y + dy) for name, (x, y) in raw.items()}

    def _build_path_edge_overlay(self) -> None:
        """Collect edges used by assigned paths."""
        edges: set[Tuple[str, str]] = set()
        for path in self.assignments:
            for i in range(len(path) - 1):
                a, b = path[i], path[i + 1]
                edges.add((a, b) if a < b else (b, a))
        self.path_edges = edges

    # ---------- simulation integration ----------
    def _begin_turn(self) -> None:
        """Advance simulation by one logical turn and start animations."""
        if self.sim is None or self.finished:
            return

        if any(v.moving for v in self.drones.values()):
            return

        moves = self.sim.step()
        if not moves:
            self.finished = True
            return

        self.current_turn += 1
        print(" ".join(moves))

        # reset previous movement state
        for v in self.drones.values():
            v.moving = False
            v.move_from = None
            v.move_to = None
            v.progress = 0.0

        # parse movement tokens:
        # D<ID>-<zone>
        # D<ID>-<src>-<dst>
        for token in moves:
            body = token[1:]  # remove leading 'D'
            parts = body.split("-")
            drone_id = int(parts[0])
            dv = self.drones[drone_id]

            if len(parts) == 2:
                dst = parts[1]
                src = dv.zone
                dv.move_from = src
                dv.move_to = dst
                dv.progress = 0.0
                dv.moving = True

            elif len(parts) == 3:
                src = parts[1]
                dst = parts[2]
                # restricted first half: move on connection only
                # (do not anchor to dst yet)
                dv.move_from = src
                dv.move_to = dst
                dv.progress = 0.0
                dv.moving = True

            else:
                continue

        self.anim_elapsed = 0.0

        # _finalize_finished_animations() will set self.finished = True
        # once all drones are done and all animations have completed.

    def _finalize_finished_animations(self) -> None:
        """Finalize positions for drones that reached destination."""
        for dv in self.drones.values():
            if (
                not dv.moving
                or dv.move_from is None
                or dv.move_to is None
            ):
                continue
            if dv.progress >= 1.0:
                dv.zone = dv.move_to
                dv.moving = False
                dv.move_from = None
                dv.move_to = None
                dv.progress = 0.0

        all_sim_done = (
            self.sim is not None
            and all(d.finished for d in self.sim.drones)
        )
        no_anim = not any(v.moving for v in self.drones.values())
        if all_sim_done and no_anim:
            self.finished = True

    def _update(self) -> None:
        """Handle controls, run turns, and animate movement."""
        if rl.is_key_pressed(rl.KEY_SPACE):
            self.playing = not self.playing

        if rl.is_key_pressed(rl.KEY_RIGHT):
            self._begin_turn()

        dt = rl.get_frame_time()

        # animate current moving drones
        if any(v.moving for v in self.drones.values()):
            self.anim_elapsed += dt
            p = min(1.0, self.anim_elapsed / self.cfg.anim_duration)
            smooth = p * p * (3.0 - 2.0 * p)  # smoothstep
            for dv in self.drones.values():
                if dv.moving:
                    dv.progress = smooth
            self._finalize_finished_animations()

        if not self.playing or self.finished:
            return

        self.turn_elapsed += dt
        if self.turn_elapsed >= self.cfg.turn_interval:
            self.turn_elapsed = 0.0
            self._begin_turn()

    # ---------- draw ----------
    def _zone_color(self, name: str, ztype: ZoneType) -> tuple:
        """Return zone color by role/type."""
        if name == self.start:
            return self.theme.START
        if name == self.end:
            return self.theme.END
        if ztype == ZoneType.NORMAL:
            return self.theme.NORMAL
        if ztype == ZoneType.PRIORITY:
            return self.theme.PRIORITY
        if ztype == ZoneType.RESTRICTED:
            return self.theme.RESTRICTED
        if ztype == ZoneType.BLOCKED:
            return self.theme.BLOCKED
        return self.theme.NORMAL

    def _draw_grid(self) -> None:
        """Draw subtle background grid."""
        step = 42
        for x in range(0, self.cfg.width + 1, step):
            rl.draw_line(x, 0, x, self.cfg.height, self.theme.GRID)
        for y in range(0, self.cfg.height + 1, step):
            rl.draw_line(0, y, self.cfg.width, y, self.theme.GRID)

    def _draw_edges(self) -> None:
        """Draw graph edges."""
        for a_name, neighbors in self.graph.adj.items():
            ax, ay = self.pos[a_name]
            for b_zone, conn in neighbors:
                b_name = b_zone.name
                if a_name >= b_name:
                    continue

                bx, by = self.pos[b_name]
                key = (
                    (a_name, b_name)
                    if a_name < b_name
                    else (b_name, a_name)
                )
                col = (
                    self.theme.EDGE_PATH
                    if key in self.path_edges
                    else self.theme.EDGE
                )
                thick = 2.0 + max(0, conn.max_link_capacity - 1) * 0.8
                rl.draw_line_ex(
                    rl.Vector2(float(ax), float(ay)),
                    rl.Vector2(float(bx), float(by)),
                    thick,
                    col,
                )

    def _draw_nodes(self) -> None:
        """Draw zones as squares."""
        s = self.cfg.node_size
        h = s // 2

        for name, zone in self.graph.zones.items():
            x, y = self.pos[name]
            color = self._zone_color(name, zone.zone_type)

            rl.draw_rectangle(x - h, y - h, s, s, color)
            rl.draw_rectangle_lines(x - h, y - h, s, s, self.theme.NODE_BORDER)

            if zone.zone_type == ZoneType.BLOCKED:
                rl.draw_line(
                    x - h + 3, y - h + 3,
                    x + h - 3, y + h - 3,
                    rl.RAYWHITE,
                )
                rl.draw_line(
                    x - h + 3, y + h - 3,
                    x + h - 3, y - h + 3,
                    rl.RAYWHITE,
                )

    def _drone_color(self, drone_id: int) -> tuple:
        """Return stable pleasant color per drone id."""
        palette = [
            (255, 99, 132, 255),
            (54, 162, 235, 255),
            (255, 206, 86, 255),
            (75, 192, 192, 255),
            (153, 102, 255, 255),
            (255, 159, 64, 255),
            (46, 204, 113, 255),
            (231, 76, 60, 255),
        ]
        return palette[(drone_id - 1) % len(palette)]

    def _draw_drone_texture(
        self, x: float, y: float, drone_id: int
    ) -> None:
        """Draw one drone using the loaded texture with rotation."""
        dv = self.drones[drone_id]
        tex_w = self.drone_texture.width
        tex_h = self.drone_texture.height

        # Drone size
        size = 36.0

        source = rl.Rectangle(0.0, 0.0, float(tex_w), float(tex_h))
        dest = rl.Rectangle(float(x), float(y), size, size)
        origin = rl.Vector2(size / 2.0, size / 2.0)

        # Shadow
        shadow_dest = rl.Rectangle(float(x + 2.0), float(y + 2.0), size, size)
        rl.draw_texture_pro(
            self.drone_texture, source, shadow_dest, origin, dv.angle, (0, 0, 0, 90)
        )

        # Main texture
        rl.draw_texture_pro(
            self.drone_texture, source, dest, origin, dv.angle, rl.WHITE
        )

        # Identifiable number
        text = str(drone_id)
        tw = rl.measure_text(text, 12)

        # Draw background capsule for text readability
        rl.draw_rectangle(int(x) - tw // 2 - 2, int(y) - 26, tw + 4, 14, (0, 0, 0, 180))
        rl.draw_text(
            text,
            int(x) - tw // 2,
            int(y) - 25,
            12,
            self.theme.END,
        )

    def _drone_draw_pos(self, drone_id: int) -> Tuple[float, float]:
        """Compute interpolated drone position."""
        dv = self.drones[drone_id]

        if not dv.moving or dv.move_from is None or dv.move_to is None:
            zx, zy = self.pos[dv.zone]
            return float(zx), float(zy)

        x1, y1 = self.pos[dv.move_from]
        x2, y2 = self.pos[dv.move_to]
        t = dv.progress

        dv.angle = math.degrees(math.atan2(y2 - y1, x2 - x1))

        # linear interpolation
        x = x1 + (x2 - x1) * t
        y = y1 + (y2 - y1) * t
        return float(x), float(y)

    def _draw_drones(self) -> None:
        """Draw all drones using interpolated edge movement."""
        # if many drones overlap exactly, spread a little by angle
        buckets: Dict[Tuple[int, int], List[int]] = {}

        raw_positions: Dict[int, Tuple[float, float]] = {}
        for drone_id in self.drones:
            raw_positions[drone_id] = self._drone_draw_pos(drone_id)
            rx = int(raw_positions[drone_id][0])
            ry = int(raw_positions[drone_id][1])
            buckets.setdefault((rx, ry), []).append(drone_id)

        final_positions: Dict[int, Tuple[float, float]] = {}
        for key, ids in buckets.items():
            if len(ids) == 1:
                d = ids[0]
                final_positions[d] = raw_positions[d]
                continue

            cx, cy = raw_positions[ids[0]]
            radius = 12.0
            for i, d in enumerate(ids):
                ang = (2.0 * math.pi * i) / len(ids)
                ox = math.cos(ang) * radius
                oy = math.sin(ang) * radius
                final_positions[d] = (cx + ox, cy + oy)

        for drone_id in sorted(self.drones.keys()):
            x, y = final_positions[drone_id]
            self._draw_drone_texture(x, y, drone_id)

    def _draw_ui(self) -> None:
        """Draw UI elements like the turn counter and controls."""
        turn_text = f"Turn: {self.current_turn}"
        if self.finished and self.current_turn > 0:
            turn_text += " (Finished)"

        # Draw turn counter top left
        rl.draw_text(turn_text, 20, 20, 24, (230, 230, 230, 255))

        # Draw controls info bottom left
        controls_text = "SPACE: Pause/Play  |  RIGHT ARROW: Step"
        rl.draw_text(
            controls_text,
            20,
            self.cfg.height - 30,
            16,
            (150, 150, 150, 255),
        )

    def _draw(self) -> None:
        """Render one frame."""
        rl.clear_background(self.theme.BG)
        self._draw_grid()
        self._draw_edges()
        self._draw_nodes()
        self._draw_drones()
        self._draw_ui()

    # ---------- app loop ----------
    def run(self) -> int:
        """Run the raylib main loop."""
        rl.set_trace_log_level(rl.LOG_WARNING)
        rl.init_window(self.cfg.width, self.cfg.height, "Fly-in Visualizer")
        rl.set_target_fps(60)

        # Load drone texture for dynamic usage
        self.drone_texture = rl.load_texture("drone.jpg")

        self.setup()

        while not rl.window_should_close():
            self._update()
            rl.begin_drawing()
            self._draw()
            rl.end_drawing()

        rl.unload_texture(self.drone_texture)
        rl.close_window()
        return 0


def main() -> int:
    """CLI entrypoint."""
    if len(sys.argv) != 2:
        print("Usage: python3 visualizer.py <mapfile>", file=sys.stderr)
        return 2

    try:
        app = SimulationVisualizer(sys.argv[1])
        return app.run()
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
