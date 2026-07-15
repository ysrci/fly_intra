import pygame
import sys
from typing import Optional, List, Dict, Tuple
from parser import MapParser as p
from simulator import Simulation


class ViewConfig:
    """Window and animation configuration."""
    wigth: int = 1200
    height: int = 780
    margin: int = 80
    nod_size: int = 22
    drone_size: int = 11
    turn_interval: float = 0.70
    anum_duration: float = 0.55


class Theme:
    """Color palette"""
    BG: tuple = (14, 17, 27, 255)
    GRID: tuple = (40, 46, 66, 70)

    EDGE: tuple = (130, 145, 180, 170)
    EDGE_PATH: tuple = (255, 220, 120, 230)

    NODE_BORDER: tuple = (8, 10, 16, 255)
    START: tuple = (70, 235, 145, 255)
    END: tuple = (210, 105, 255, 255)
    NORMAL: tuple = (78, 131, 255, 255)
    PRIORITY: tuple = (0, 212, 255, 255)
    RESTRICTED: tuple = (255, 176, 79, 255)
    BLOCKED: tuple = (255, 92, 92, 255)


class DroneVisualState:
    """Visual state for one drone"""
    zone: str
    move_from: Optional[str] = None
    move_to: Optional[str] = None
    progress: float = 0.0
    moving: bool = False
    angle: float = 0.0


class SimulationVisualizer:
    """Visual with smooth drone movement over connections"""
    def __init__(self, file: str) -> None:
        """Initialize visualizer and load map"""
        self.mapfile = file
        self.nb_drones, self.start, self.end, self.graph = p.parse_file(file)

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

































def main() -> int:
    """entery point"""
    if len(sys.argv) != 2:
        print("Usage: python3 visualizer.py <mapfile>")
        return 2
    try:
        visual = Visualizer(sys.argv.argv[1])
        return visual.run()
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())