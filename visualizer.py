"""Simple drone simulation visualizer with smooth animation.
Press SPACE to advance one turn. Press ESC or close window to quit.
Usage: python3 visualizer.py <mapfile>
"""
import os
import sys
from typing import Dict, List, Optional, Tuple

import pygame

from models import Graph
from parser import MapParser, ParseError
from pathfinder import MultiPathFinder
from simulator import Drone, Simulation


# ── Color constants ─────────────────────────────────────────────────
# BG: dark background color for the window.
BG = (20, 20, 30)
# LINK_COLOR: color for the lines connecting zones.
LINK_COLOR = (50, 50, 65)
# TEXT_COLOR: color for zone labels and type tags.
TEXT_COLOR = (220, 220, 220)
# DRONE_COLOR: bright yellow for drone labels and capacity text.
DRONE_COLOR = (255, 200, 60)
# DEFAULT_ZONE: fallback zone color if map has no color attribute.
DEFAULT_ZONE = (60, 60, 80)



# ── Layout constants ────────────────────────────────────────────────
# WIDTH, HEIGHT: window size in pixels.
WIDTH, HEIGHT = 1600, 900
# ZONE_RADIUS: radius of each zone circle in pixels.
ZONE_RADIUS = 28
# DRONE_SIZE: width and height of the drone image in pixels.
DRONE_SIZE = 32
# FONT_SIZE: size of the monospace font used for all text.
FONT_SIZE = 14

# ── Animation constants ────────────────────────────────────────────
# ANIM_DURATION: how many seconds the smooth slide takes per turn.
ANIM_DURATION = 0.5
# FPS: frames per second for the game loop (smooth rendering).
FPS = 60


# ── Helper functions ────────────────────────────────────────────────

def get_zone_color(color_name: str) -> Tuple[int, int, int]:
    """Convert a color name to RGB using pygame.Color directly."""
    try:
        c = pygame.Color(color_name)
        return (c.r, c.g, c.b)
    except ValueError:
        return DEFAULT_ZONE


def build_positions(graph: Graph) -> Dict[str, Tuple[int, int]]:
    """Convert each zone's (x, y) from the map into pixel positions.
    We scale them so the graph fits nicely inside the window with
    an 80-pixel padding on every side."""
    xs = [z.x for z in graph.zones.values()]
    ys = [z.y for z in graph.zones.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    pad = 80
    w = WIDTH - 2 * pad
    h = HEIGHT - 2 * pad
    # Avoid division by zero if all zones share one coordinate.
    rx = max_x - min_x if max_x != min_x else 1
    ry = max_y - min_y if max_y != min_y else 1

    pos: Dict[str, Tuple[int, int]] = {}
    for name, z in graph.zones.items():
        px = pad + int((z.x - min_x) / rx * w)
        py = pad + int((z.y - min_y) / ry * h)
        pos[name] = (px, py)
    return pos


def drone_target_xy(
    drone: Drone,
    turn_moves: List[str],
    positions: Dict[str, Tuple[int, int]],
) -> Tuple[int, int]:
    """Return the TARGET pixel position for a drone this turn.
    This is where the drone should END UP after the animation.
    - D1-A-B (3 parts): drone is in transit → target is midpoint.
    - D1-zone (2 parts): drone arrived at zone → target is zone pos.
    - No token: drone did not move → stays at current zone."""
    for token in turn_moves:
        parts = token.split("-")
        # Extract drone ID from token like "D1", "D2", etc.
        drone_id = int(parts[0][1:])
        if drone_id != drone.drone_id:
            continue
        if len(parts) == 3:
            # D1-A-B: flying toward restricted zone, show at midpoint.
            src, dst = parts[1], parts[2]
            sx, sy = positions[src]
            dx, dy = positions[dst]
            return ((sx + dx) // 2, (sy + dy) // 2)
        else:
            # D1-zone: arrived at this zone.
            return positions[parts[1]]

    # No move token found → drone stays where it is.
    current = drone.path[drone.path_index]
    return positions[current]


# ── Main Visualizer class ──────────────────────────────────────────

class Visualizer:
    """Step-by-step drone visualizer with smooth animation.
    Press SPACE to advance one turn. Drones slide smoothly
    from their old position to their new position."""

    def __init__(self, map_path: str) -> None:
        """Parse the map, find paths, and prepare the simulation."""
        # Step 1: Parse the map file into a graph.
        parser = MapParser()
        nb, start, end, self.graph = parser.parse_file(map_path)

        # Step 2: Find shortest paths for all drones.
        finder = MultiPathFinder(self.graph)
        alloc = finder.drone_waste(start, end, nb)
        if not alloc.assignments:
            raise ValueError("No valid path found")

        # Step 3: Pre-run the full simulation to get all turn data.
        self.sim = Simulation(self.graph, alloc.assignments)
        self.all_turns = self.sim.run()

        # Step 4: Reset sim for step-by-step replay with animation.
        self.sim = Simulation(self.graph, alloc.assignments)
        self.turn = 0
        self.current_moves: List[str] = []
        self.positions = build_positions(self.graph)
        self.finished = False

        # Step 5: Drone image placeholder (loaded after pygame.init).
        self.drone_img: Optional[pygame.Surface] = None

        # Step 6: Animation state.
        # prev_drone_pos: where each drone WAS before the current turn.
        # target_drone_pos: where each drone SHOULD BE after the turn.
        # anim_progress: from 0.0 (start) to 1.0 (arrived).
        # animating: True while drones are sliding to new positions.
        self.prev_drone_pos: Dict[int, Tuple[int, int]] = {}
        self.target_drone_pos: Dict[int, Tuple[int, int]] = {}
        self.anim_progress: float = 1.0
        self.animating: bool = False

        # Initialize all drones at the start zone position.
        for drone in self.sim.drones:
            start_pos = self.positions[drone.path[0]]
            self.prev_drone_pos[drone.drone_id] = start_pos
            self.target_drone_pos[drone.drone_id] = start_pos

    def run(self) -> int:
        """Main pygame loop. Returns 0 on clean exit."""
        pygame.init()

        # Load the drone image now that pygame is initialized.
        img_path = os.path.join(os.path.dirname(__file__), "drone.jpg")
        raw = pygame.image.load(img_path)
        self.drone_img = pygame.transform.smoothscale(
            raw, (DRONE_SIZE, DRONE_SIZE)
        )

        # Create the window, font, and clock.
        screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Fly-in • Drone Visualizer")
        font = pygame.font.SysFont("monospace", FONT_SIZE)
        clock = pygame.time.Clock()

        running = True
        while running:
            # dt: time since last frame in seconds (for smooth anim).
            dt = clock.tick(FPS) / 1000.0

            # Handle user input events.
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    # Only allow SPACE when not mid-animation.
                    if event.key == pygame.K_SPACE and not self.animating:
                        self._step()

            # Update animation progress each frame.
            if self.animating:
                self.anim_progress += dt / ANIM_DURATION
                # Clamp to 1.0 when animation finishes.
                if self.anim_progress >= 1.0:
                    self.anim_progress = 1.0
                    self.animating = False

            # Redraw everything every frame.
            self._draw(screen, font)
            pygame.display.flip()

        pygame.quit()
        return 0

    # ── Internal methods ────────────────────────────────────────────

    def _step(self) -> None:
        """Advance one simulation turn and start the slide animation.
        Also prints the turn info to the terminal."""
        if self.finished:
            return

        if self.turn < len(self.all_turns):
            # Save current positions as the animation start points.
            for drone in self.sim.drones:
                self.prev_drone_pos[drone.drone_id] = (
                    self.target_drone_pos[drone.drone_id]
                )

            # Get this turn's move tokens and step the simulation.
            self.current_moves = self.all_turns[self.turn]
            self.sim.step()
            self.turn += 1

            # Compute new target positions from the move tokens.
            for drone in self.sim.drones:
                self.target_drone_pos[drone.drone_id] = drone_target_xy(
                    drone, self.current_moves, self.positions
                )

            # Start the animation: progress goes from 0 → 1.
            self.anim_progress = 0.0
            self.animating = True

            # Print turn info to terminal.
            moves_txt = "  ".join(self.current_moves)
            print(f"Turn {self.turn}/{len(self.all_turns)}: {moves_txt}")
        else:
            self.finished = True
            print(f"Turn {self.turn}/{len(self.all_turns)} — DONE")

    def _lerp(self, drone_id: int) -> Tuple[int, int]:
        """Linear interpolation between prev and target position.
        t=0 → prev position, t=1 → target position.
        This creates the smooth sliding effect."""
        t = self.anim_progress
        px, py = self.prev_drone_pos[drone_id]
        tx, ty = self.target_drone_pos[drone_id]
        # Smooth-step: ease-in-out curve for nicer motion.
        t = t * t * (3 - 2 * t)
        x = int(px + (tx - px) * t)
        y = int(py + (ty - py) * t)
        return (x, y)

    def _draw(self, screen: pygame.Surface, font: pygame.font.Font) -> None:
        """Render the full scene: background, links, zones, drones."""
        # Clear the screen with the dark background.
        screen.fill(BG)

        # ── Draw connections (lines between zones) ──────────────
        for link in self.graph.links.values():
            a = self.positions[link.node_a]
            b = self.positions[link.node_b]
            pygame.draw.line(screen, LINK_COLOR, a, b, 2)

        # ── Draw zones (circles with labels) ────────────────────
        for name, z in self.graph.zones.items():
            pos = self.positions[name]
            # Use the color from the map file for this zone.
            col = get_zone_color(z.color)
            pygame.draw.circle(screen, col, pos, ZONE_RADIUS)

            # Show capacity number above the zone circle.
            # Start and end zones have infinite capacity → show "∞".
            cap_txt = "∞" if z.is_start or z.is_end else str(z.max_drones)
            cap_label = font.render(cap_txt, True, DRONE_COLOR)
            cx = pos[0] - cap_label.get_width() // 2
            cy = pos[1] - ZONE_RADIUS - 34
            screen.blit(cap_label, (cx, cy))

            # Show zone name just above the circle.
            label = font.render(name, True, TEXT_COLOR)
            lx = pos[0] - label.get_width() // 2
            ly = pos[1] - ZONE_RADIUS - 18
            screen.blit(label, (lx, ly))

            # Show zone type tag below the circle (only if not normal).
            if z.zone_type != "normal":
                tag = font.render(z.zone_type, True, TEXT_COLOR)
                tx = pos[0] - tag.get_width() // 2
                ty = pos[1] + ZONE_RADIUS + 4
                screen.blit(tag, (tx, ty))

        # ── Draw drones (image + label) ─────────────────────────
        half = DRONE_SIZE // 2
        for drone in self.sim.drones:
            # Use interpolated position for smooth sliding.
            dx, dy = self._lerp(drone.drone_id)
            # Draw the drone image centered on (dx, dy).
            screen.blit(self.drone_img, (dx - half, dy - half))
            # Draw the drone ID label just below the image.
            d_label = font.render(f"D{drone.drone_id}", True, DRONE_COLOR)
            screen.blit(d_label, (dx - 8, dy + half + 2))

        # ── Turn counter (bottom-left corner) ───────────────────
        turn_txt = f"Turn {self.turn} / {len(self.all_turns)}"
        turn_label = font.render(turn_txt, True, TEXT_COLOR)
        screen.blit(turn_label, (10, HEIGHT - 30))


# ── Entry point ─────────────────────────────────────────────────────

def main() -> int:
    """CLI entrypoint. Reads the map file from argv and runs."""
    if len(sys.argv) != 2:
        print("Usage: python3 visualizer.py <mapfile>", file=sys.stderr)
        return 2
    try:
        app = Visualizer(sys.argv[1])
        return app.run()
    except (ParseError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
