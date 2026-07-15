from __future__ import annotations

import math
import sys
from typing import Dict, List, Optional, Tuple

import pygame

from parser import MapParser
from pathfinder import MultiPathFinder
from simulator import Simulation

# ── colors ──────────────────────────────────────────────────────
BG = (0, 0, 0)
EDGE_COL = (130, 145, 180)
EDGE_PATH_COL = (255, 220, 120)
NODE_BORDER = (0, 0, 0)
COL_START = (70, 235, 145)
COL_END = (210, 105, 255)
COL_NORMAL = (78, 131, 255)
COL_PRIORITY = (0, 212, 255)
COL_RESTRICTED = (255, 176, 79)
COL_BLOCKED = (255, 92, 92)
WHITE = (255, 255, 255)

Color = Tuple[int, int, int]

# ── constants ───────────────────────────────────────────────────
WIDTH, HEIGHT = 1200, 780
MARGIN = 80
NODE_SIZE = 22
TURN_INTERVAL = 0.70
ANIM_DURATION = 0.55

DRONE_PALETTE: List[Color] = [
    (255, 99, 132), (54, 162, 235), (255, 206, 86),
    (75, 192, 192), (153, 102, 255), (255, 159, 64),
    (46, 204, 113), (231, 76, 60),
]


class SimulationVisualizer:
    """Visualizer with smooth drone movement over connections."""

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

    # ── setup ───────────────────────────────────────────────────
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

    # ── geometry ────────────────────────────────────────────────
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

    # ── simulation ──────────────────────────────────────────────
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

    def _finalize_animations(self) -> None:
        """Snap drones that finished animating to destination."""
        for d in self.drones.values():
            if not d[4] or d[1] is None or d[2] is None:
                continue
            if d[3] >= 1.0:  # type: ignore[operator]
                d[0] = d[2]
                d[1] = None
                d[2] = None
                d[3] = 0.0
                d[4] = False

        if self.sim is not None and all(
            dr.finished for dr in self.sim.drones
        ) and not any(d[4] for d in self.drones.values()):
            self.finished = True

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

    # ── drawing ─────────────────────────────────────────────────
    def _zone_color(self, name: str, ztype: str) -> Color:
        """Return zone color by role / type."""
        if name == self.start:
            return COL_START
        if name == self.end:
            return COL_END
        mapping: Dict[str, Color] = {
            "normal": COL_NORMAL,
            "priority": COL_PRIORITY,
            "restricted": COL_RESTRICTED,
            "blocked": COL_BLOCKED,
        }
        return mapping.get(ztype, COL_NORMAL)



    def _draw_edges(self, surf: pygame.Surface) -> None:
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

    def _draw_nodes(self, surf: pygame.Surface) -> None:
        """Draw zones as squares."""
        h = NODE_SIZE // 2
        for name, zone in self.graph.zones.items():
            x, y = self.pos[name]
            col = self._zone_color(name, zone.zone_type)
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

    def _drone_pos(self, did: int) -> Tuple[float, float, float]:
        """Return interpolated drone position and angle."""
        d = self.drones[did]
        if not d[4] or d[1] is None or d[2] is None:
            zx, zy = self.pos[str(d[0])]
            return float(zx), float(zy), 0.0
        x1, y1 = self.pos[str(d[1])]
        x2, y2 = self.pos[str(d[2])]
        t = float(d[3])  # type: ignore[arg-type]
        ang = -math.degrees(math.atan2(y2 - y1, x2 - x1))
        return x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, ang

    def _draw_drones(self, surf: pygame.Surface) -> None:
        """Draw all drones using the loaded texture."""
        buckets: Dict[Tuple[int, int], List[int]] = {}
        raw: Dict[int, Tuple[float, float, float]] = {}
        for did in self.drones:
            raw[did] = self._drone_pos(did)
            key = (int(raw[did][0]), int(raw[did][1]))
            buckets.setdefault(key, []).append(did)

        final: Dict[int, Tuple[float, float, float]] = {}
        for _bkey, ids in buckets.items():
            if len(ids) == 1:
                final[ids[0]] = raw[ids[0]]
            else:
                cx, cy, a = raw[ids[0]]
                for i, d in enumerate(ids):
                    t = 2.0 * math.pi * i / len(ids)
                    ox = math.cos(t) * 12
                    oy = math.sin(t) * 12
                    final[d] = (cx + ox, cy + oy, a)

        font_sm = pygame.font.SysFont(None, 18)
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

    def _draw_ui(self, surf: pygame.Surface) -> None:
        """Draw turn counter and controls text."""
        font = pygame.font.SysFont(None, 28)
        text = f"Turn: {self.current_turn}"
        if self.finished and self.current_turn > 0:
            text += " (Finished)"
        surf.blit(font.render(text, True, (230, 230, 230)), (20, 20))

        font_sm = pygame.font.SysFont(None, 20)
        ctrl = "SPACE: Pause/Play  |  RIGHT: Step"
        surf.blit(font_sm.render(ctrl, True, (150, 150, 150)),
                  (20, HEIGHT - 30))

    def _draw(self, surf: pygame.Surface) -> None:
        """Render one frame."""
        surf.fill(BG)
        self._draw_edges(surf)
        self._draw_nodes(surf)
        self._draw_drones(surf)
        self._draw_ui(surf)

    # ── main loop ───────────────────────────────────────────────
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


if __name__ == "__main__":
    raise SystemExit(main())
