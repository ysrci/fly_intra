from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pyray as rl

from parser import MapParser, FlightMap, ZoneBehavior
from solve import PathFinder, Scheduler, Simulator


@dataclass
class ViewConfig:
    """Window and animation configuration."""
    width: int = 1200
    height: int = 780
    margin: int = 100
    node_size: int = 40
    drone_radius: float = 11.0
    # جعلنا الوقت الإجمالي أطول شوية حيت غيتنقسم على قطعتين
    anim_duration: float = 0.8 


class Theme:
    """Color palette."""
    BG: rl.Color = rl.Color(14, 17, 27, 255)
    GRID: rl.Color = rl.Color(40, 46, 66, 70)
    EDGE: rl.Color = rl.Color(130, 145, 180, 170)
    EDGE_PATH: rl.Color = rl.Color(255, 220, 120, 230)
    NODE_BORDER: rl.Color = rl.Color(255, 255, 255, 255)
    START: rl.Color = rl.Color(70, 235, 145, 255)
    END: rl.Color = rl.Color(210, 105, 255, 255)
    NORMAL: rl.Color = rl.Color(78, 131, 255, 255)
    PRIORITY: rl.Color = rl.Color(0, 212, 255, 255)
    RESTRICTED: rl.Color = rl.Color(255, 176, 79, 255)
    BLOCKED: rl.Color = rl.Color(255, 92, 92, 255)


@dataclass
class DroneVisualState:
    """Visual state for one drone supporting two-phase motion."""
    zone: str
    move_from: Optional[str] = None
    move_to: Optional[str] = None
    progress: float = 0.0
    moving: bool = False
    angle: float = 0.0
    is_leaving_first: bool = False  # الحيلة هنا: واش الدرون كيخوي الزون هو الأول؟


class SimulationVisualizer:
    """Visualizer with perfect sequential phase animations to prevent overlaps."""

    def __init__(self, flight_map: FlightMap) -> None:
        self.graph = flight_map
        self.nb_drones = flight_map.nb_drones
        self.start = flight_map.start_zone
        self.end = flight_map.end_zone

        self.cfg = ViewConfig()
        self.theme = Theme()

        self.assignments: List[int] = []
        self.frames = []

        self.pos: Dict[str, Tuple[int, int]] = {}
        self.path_edges: set[Tuple[str, str]] = set()

        self.finished: bool = False
        self.current_turn: int = 0
        self.anim_elapsed: float = 0.0

        self.drones: Dict[int, DroneVisualState] = {}
        self.drone_texture = None

    def setup(self) -> None:
        self._build_positions()

        finder = PathFinder(self.graph)
        pool = finder.diverse_paths(max_paths=max(2, min(self.nb_drones, len(self.graph.zones))))
        if not pool:
            pool = finder.disjoint_paths(max_paths=1)

        self.paths = pool
        self.assignments = Scheduler(self.paths).assign(self.nb_drones)
        self.frames = Simulator(self.graph).run(self.paths, self.assignments)

        self._build_path_edge_overlay()

        for drone_id in range(1, self.nb_drones + 1):
            self.drones[drone_id] = DroneVisualState(zone=self.start)

    def _compute_bounds(self) -> Tuple[int, int, int, int]:
        xs = [z.x for z in self.graph.zones.values()]
        ys = [z.y for z in self.graph.zones.values()]
        return min(xs or [0]), max(xs or [1]), min(ys or [0]), max(ys or [1])

    def _world_to_screen(self, x: int, y: int, bounds: Tuple[int, int, int, int]) -> Tuple[int, int]:
        min_x, max_x, min_y, max_y = bounds
        sx_span = max(1, max_x - min_x)
        sy_span = max(1, max_y - min_y)

        w_inner = self.cfg.width - 2 * self.cfg.margin
        h_inner = self.cfg.height - 2 * self.cfg.margin
        sx = self.cfg.margin + (x - min_x) * w_inner / sx_span
        sy = self.cfg.margin + (y - min_y) * h_inner / sy_span
        return int(sx), int(sy)

    def _build_positions(self) -> None:
        bounds = self._compute_bounds()
        raw = {name: self._world_to_screen(z.x, z.y, bounds) for name, z in self.graph.zones.items()}

        xs = [p[0] for p in raw.values()]
        ys = [p[1] for p in raw.values()]
        graph_cx = (min(xs or [0]) + max(xs or [1])) // 2
        graph_cy = (min(ys or [0]) + max(ys or [1])) // 2

        dx = self.cfg.width // 2 - graph_cx
        dy = self.cfg.height // 2 - graph_cy

        self.pos = {name: (x + dx, y + dy) for name, (x, y) in raw.items()}

    def _build_path_edge_overlay(self) -> None:
        edges: set[Tuple[str, str]] = set()
        for path_idx in self.assignments:
            path = self.paths[path_idx].zones
            for i in range(len(path) - 1):
                a, b = path[i], path[i + 1]
                edges.add((a, b) if a < b else (b, a))
        self.path_edges = edges

    def _step_forward(self) -> None:
        if self.current_turn >= len(self.frames) or any(v.moving for v in self.drones.values()):
            return

        current_frame = self.frames[self.current_turn]
        moves = current_frame.moves
        self.current_turn += 1

        for v in self.drones.values():
            v.moving = False
            v.move_from = None
            v.move_to = None
            v.progress = 0.0
            self.is_leaving_first = False

        # مصفوفة لمعرفة شكون لي غيخوي الزون وشكون غيدخل ليها
        leaving_zones = set()
        active_moves = []

        for token in moves:
            if "-" not in token:
                continue
            parts = token.split("-")
            drone_id = int(parts[0][1:])
            destination = parts[1]
            active_moves.append((drone_id, destination))
            
            # الدرون لي كيتحرك راه كيخوي الزون الحالية ديالو
            leaving_zones.add(self.drones[drone_id].zone)

        for drone_id, dest in active_moves:
            dv = self.drones[drone_id]
            dv.move_from = dv.zone
            dv.move_to = dest
            dv.moving = True
            
            # إذا كان غادي لشي زون، وهي بيدها كاين شي درون آخر كيخويها دابا:
            # هاد الدرون خاصو يتسنى (يتحرك ف المرحلة الثانية Phase 2)
            if dest in leaving_zones:
                dv.is_leaving_first = False
            else:
                dv.is_leaving_first = True

        self.anim_elapsed = 0.0
        self.finished = False

    def _step_backward(self) -> None:
        if self.current_turn <= 0 or any(v.moving for v in self.drones.values()):
            return

        self.current_turn -= 1
        self.finished = False

        drone_positions: Dict[int, str] = {i: self.start for i in range(1, self.nb_drones + 1)}
        for f in self.frames[:self.current_turn]:
            for move in f.moves:
                if "-" in move:
                    parts = move.split("-")
                    d_id = int(parts[0][1:])
                    drone_positions[d_id] = parts[1]

        for d_id, zone_name in drone_positions.items():
            dv = self.drones[d_id]
            dv.zone = zone_name
            dv.moving = False
            dv.move_from = None
            dv.move_to = None
            dv.progress = 0.0

    def _finalize_finished_animations(self) -> None:
        for dv in self.drones.values():
            if not dv.moving or dv.move_from is None or dv.move_to is None:
                continue
            if dv.progress >= 1.0:
                dv.zone = dv.move_to
                dv.moving = False
                dv.move_from = None
                dv.move_to = None
                dv.progress = 0.0

        if self.current_turn >= len(self.frames) and not any(v.moving for v in self.drones.values()):
            self.finished = True

    def _update(self) -> None:
        if rl.is_key_pressed(rl.KEY_RIGHT):
            self._step_forward()
        if rl.is_key_pressed(rl.KEY_LEFT):
            self._step_backward()

        dt = rl.get_frame_time()
        if any(v.moving for v in self.drones.values()):
            self.anim_elapsed += dt
            # نسبة الوقت الإجمالي للـ Turn الحالي من 0.0 إلى 1.0
            total_ratio = min(1.0, self.anim_elapsed / self.cfg.anim_duration)

            for dv in self.drones.values():
                if not dv.moving:
                    continue
                
                if dv.is_leaving_first:
                    # المرحلة الأولى: كيتحرك من تانية 0 حتى لـ منتصف الوقت (0.5)
                    if total_ratio <= 0.5:
                        dv.progress = total_ratio * 2.0
                    else:
                        dv.progress = 1.0
                else:
                    # المرحلة الثانية: كيبقى جالس فبلاصتو ف النص اللول، وكيتحرك من 0.5 لـ 1.0
                    if total_ratio <= 0.5:
                        dv.progress = 0.0
                    else:
                        dv.progress = (total_ratio - 0.5) * 2.0

            if total_ratio >= 1.0:
                self._finalize_finished_animations()

    def _zone_color(self, name: str, kind: ZoneBehavior) -> rl.Color:
        if name == self.start: return self.theme.START
        if name == self.end: return self.theme.END
        if kind == ZoneBehavior.NORMAL: return self.theme.NORMAL
        if kind == ZoneBehavior.PRIORITY: return self.theme.PRIORITY
        if kind == ZoneBehavior.RESTRICTED: return self.theme.RESTRICTED
        if kind == ZoneBehavior.BLOCKED: return self.theme.BLOCKED
        return self.theme.NORMAL

    def _draw_grid(self) -> None:
        step = 42
        for x in range(0, self.cfg.width + 1, step):
            rl.draw_line(x, 0, x, self.cfg.height, self.theme.GRID)
        for y in range(0, self.cfg.height + 1, step):
            rl.draw_line(0, y, self.cfg.width, y, self.theme.GRID)

    def _draw_edges(self) -> None:
        for edge_key, edge in self.graph.links.items():
            zones_in_edge = list(edge_key)
            if len(zones_in_edge) != 2: continue
            a_name, b_name = zones_in_edge[0], zones_in_edge[1]
            ax, ay = self.pos[a_name]
            bx, by = self.pos[b_name]

            key = (a_name, b_name) if a_name < b_name else (b_name, a_name)
            col = self.theme.EDGE_PATH if key in self.path_edges else self.theme.EDGE
            thick = 3.0
            rl.draw_line_ex(rl.Vector2(float(ax), float(ay)), rl.Vector2(float(bx), float(by)), thick, col)

    def _draw_nodes(self) -> None:
        s = self.cfg.node_size
        h = s // 2

        for name, zone in self.graph.zones.items():
            x, y = self.pos[name]
            color = self._zone_color(name, zone.kind)

            rl.draw_rectangle(x - h, y - h, s, s, color)
            rl.draw_rectangle_lines(x - h, y - h, s, s, self.theme.NODE_BORDER)

            tw = rl.measure_text(name, 14)
            rl.draw_rectangle(x - tw // 2 - 4, y - h - 22, tw + 8, 18, rl.Color(0, 0, 0, 200))
            rl.draw_text(name, x - tw // 2, y - h - 20, 14, rl.RAYWHITE)

    def _draw_drone_texture(self, x: float, y: float, drone_id: int) -> None:
        dv = self.drones[drone_id]
        tex_w = self.drone_texture.width
        tex_h = self.drone_texture.height
        size = 32.0

        source = rl.Rectangle(0.0, 0.0, float(tex_w), float(tex_h))
        dest = rl.Rectangle(float(x), float(y), size, size)
        origin = rl.Vector2(size / 2.0, size / 2.0)

        rl.draw_texture_pro(self.drone_texture, source, rl.Rectangle(float(x + 2.0), float(y + 2.0), size, size), origin, dv.angle, rl.Color(0, 0, 0, 90))
        rl.draw_texture_pro(self.drone_texture, source, dest, origin, dv.angle, rl.WHITE)

        text = str(drone_id)
        tw = rl.measure_text(text, 12)
        rl.draw_rectangle(int(x) - tw // 2 - 2, int(y) - 26, tw + 4, 14, rl.Color(0, 0, 0, 180))
        rl.draw_text(text, int(x) - tw // 2, int(y) - 25, 12, rl.YELLOW)

    def _drone_draw_pos(self, drone_id: int) -> Tuple[float, float]:
        dv = self.drones[drone_id]
        if not dv.moving or dv.move_from is None or dv.move_to is None:
            zx, zy = self.pos[dv.zone]
            return float(zx), float(zy)

        x1, y1 = self.pos[dv.move_from]
        x2, y2 = self.pos[dv.move_to]
        t = dv.progress

        if x2 != x1 or y2 != y1:
            dv.angle = math.degrees(math.atan2(y2 - y1, x2 - x1))

        return float(x1 + (x2 - x1) * t), float(y1 + (y2 - y1) * t)

    def _draw_drones(self) -> None:
        buckets: Dict[Tuple[int, int], List[int]] = {}
        raw_positions: Dict[int, Tuple[float, float]] = {}
        
        for drone_id in self.drones:
            raw_positions[drone_id] = self._drone_draw_pos(drone_id)
            rx, ry = int(raw_positions[drone_id][0]), int(raw_positions[drone_id][1])
            buckets.setdefault((rx, ry), []).append(drone_id)

        final_positions: Dict[int, Tuple[float, float]] = {}
        for key, ids in buckets.items():
            if len(ids) == 1:
                final_positions[ids[0]] = raw_positions[ids[0]]
                continue
            cx, cy = raw_positions[ids[0]]
            radius = 16.0
            for i, d in enumerate(ids):
                ang = (2.0 * math.pi * i) / len(ids)
                final_positions[d] = (cx + math.cos(ang) * radius, cy + math.sin(ang) * radius)

        for drone_id in sorted(self.drones.keys()):
            x, y = final_positions[drone_id]
            self._draw_drone_texture(x, y, drone_id)

    def _draw_ui(self) -> None:
        turn_text = f"Turn: {self.current_turn} / {len(self.frames)}"
        if self.finished: turn_text += " (Finished)"
        rl.draw_text(turn_text, 20, 20, 24, rl.Color(230, 230, 230, 255))
        rl.draw_text("RIGHT ARROW: Next Turn  |  LEFT ARROW: Prev Turn", 20, self.cfg.height - 30, 16, rl.LIGHTGRAY)

        # لوحة مراقبة حية لتأكيد العدد
        zone_occupants: Dict[str, List[int]] = {z: [] for z in self.graph.zones}
        for d_id, dv in self.drones.items():
            # إذا كان باقي ما وصلش للزون الجديدة، منطقيا راه ف القديمة أو الطريق
            current_logical_zone = dv.move_to if (dv.moving and dv.progress >= 0.5) else dv.zone
            if current_logical_zone in zone_occupants:
                zone_occupants[current_logical_zone].append(d_id)

        panel_x = self.cfg.width - 240
        rl.draw_rectangle(panel_x, 20, 220, 320, rl.Color(25, 30, 45, 220))
        rl.draw_rectangle_lines(panel_x, 20, 220, 320, rl.GRAY)
        rl.draw_text("LIVE COUNTER", panel_x + 15, 35, 14, rl.YELLOW)
        rl.draw_line(panel_x + 15, 55, panel_x + 205, 55, rl.GRAY)

        start_y = 70
        for zone_name in sorted(zone_occupants.keys()):
            drones_list = zone_occupants[zone_name]
            count = len(drones_list)
            status_line = f"{zone_name}: {count} (" + ",".join(f"D{d}" for d in drones_list) + ")" if drones_list else f"{zone_name}: 0"
            rl.draw_text(status_line, panel_x + 15, start_y, 13, rl.RAYWHITE)
            start_y += 24

    def _draw(self) -> None:
        rl.clear_background(self.theme.BG)
        self._draw_grid()
        self._draw_edges()
        self._draw_nodes()
        self._draw_drones()
        self._draw_ui()

    def run(self) -> int:
        rl.set_trace_log_level(rl.LOG_WARNING)
        rl.init_window(self.cfg.width, self.cfg.height, "Fly-in Correct Phase Visualizer")
        rl.set_target_fps(60)
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
    if len(sys.argv) != 2: return 2
    try:
        flight_map = MapParser.load_file(sys.argv[1])
        app = SimulationVisualizer(flight_map)
        return app.run()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
