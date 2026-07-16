from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from models import Graph


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


class Simulation:
    """simulation supporting multi-path
    Output format:
        - D<ID>-<zone> for normal/priority/end arrivals
        - D<ID>-<src>-<dst> while flying toward a restricted zone"""
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

    def step(self) -> List[str]:
        """Run one simulation turn."""
        self.turn_count += 1
        moves: List[str] = []
        link_used: Dict[Tuple[str, str], int] = {}
        self._resolve_transit_arrivals(moves, link_used)
        for drone in self.drones:
            if drone.finished or drone.in_transit:
                continue
            if drone.path_index >= len(drone.path) - 1:
                drone.finished = True
                continue
            src = drone.path[drone.path_index]
            dst = drone.path[drone.path_index + 1]
            if self._is_blocked(dst):
                continue
            edge = (src, dst) if src < dst else (dst, src)
            cap = self._find_link_capacity(src, dst)
            if link_used.get(edge, 0) >= cap:
                continue
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

    def _resolve_transit_arrivals(self,
                                  moves: List[str],
                                  link_used: Dict[Tuple[str, str], int]
                                  ) -> None:
        """Finish drones in restricted flight."""
        for drone in self.drones:
            if drone.finished or not drone.in_transit:
                continue
            assert drone.transit_src is not None
            assert drone.transit_dst is not None
            src = drone.transit_src
            dst = drone.transit_dst
            edge = (src, dst) if src < dst else (dst, src)
            cap = self._find_link_capacity(src, dst)
            if link_used.get(edge, 0) >= cap:
                continue
            link_used[edge] = link_used.get(edge, 0) + 1
            drone.path_index += 1
            drone.in_transit = False
            drone.transit_src = None
            drone.transit_dst = None
            moves.append(f"D{drone.drone_id}-{dst}")
            if dst == self.end:
                drone.finished = True

    def _find_link_capacity(self, a: str, b: str) -> int:
        """Return the link capacity."""
        for nei, conn in self.graph.neighbors(a):
            if nei.name == b:
                return conn.max_link_capacity
        raise ValueError(f"No connection between '{a}' and '{b}'")

    def _is_blocked(self, zone_name: str) -> bool:
        """Check if a zone is blocked."""
        if zone_name == self.end:
            return False
        return self.graph.zones[zone_name].zone_type == "blocked"

    def _zone_capacity(self, zone_name: str) -> int:
        """Return the zone capacity."""
        if zone_name == self.start or zone_name == self.end:
            return 10**9
        return self.graph.zones[zone_name].max_drones

    @staticmethod
    def format_turns(turns: List[List[str]]) -> str:
        """Format turns as terminal-friendly lines."""
        return "\n".join(" ".join(t) for t in turns)
