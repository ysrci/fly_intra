from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from models import Graph, ZoneType


@dataclass
class Drone:
    """Represents one drone during simulation."""

    drone_id: int
    path: List[str]
    path_index: int = 0
    finished: bool = False

    in_transit: bool = False
    transit_src: Optional[str] = None
    transit_dst: Optional[str] = None


class Simulation:
    """Turn-based simulation engine supporting multi-path scheduling.

    Output format:
        - D<ID>-<zone> for normal/priority/end arrivals
        - D<ID>-<src>-<dst> while flying toward a restricted zone
    """

    def __init__(self, graph: Graph, assignments: List[List[str]]) -> None:
        """Initialize simulation with one assigned path per drone.

        Args:
            graph: Map graph.
            assignments: List of paths. Index i corresponds to drone i+1.

        Raises:
            ValueError: If assignments are invalid.
        """
        if not assignments:
            raise ValueError("Assignments list must not be empty")

        self.graph = graph
        self.drones: List[Drone] = []
        self.turn_count: int = 0

        self.start = assignments[0][0]
        self.end = assignments[0][-1]

        for idx, path in enumerate(assignments, start=1):
            if len(path) < 2:
                raise ValueError(f"Drone {idx}: path too short")
            if path[0] != self.start:
                raise ValueError(f"Drone {idx}: path start mismatch")
            if path[-1] != self.end:
                raise ValueError(f"Drone {idx}: path end mismatch")
            self._validate_path_edges(path)
            self.drones.append(Drone(drone_id=idx, path=path))

        # occupancy map
        self.occupancy: Dict[str, int] = {z: 0 for z in self.graph.zones}
        self.occupancy[self.start] = len(self.drones)

    def step(self) -> List[str]:
        """Execute one turn and return movement tokens."""
        self.turn_count += 1
        moves: List[str] = []

        # per-turn edge usage
        link_used: Dict[Tuple[str, str], int] = {}

        # Phase A: mandatory arrivals from restricted transits
        self._resolve_transit_arrivals(moves, link_used)

        # Phase B: schedule new departures
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

            edge = self._norm_edge(src, dst)
            cap = self._find_link_capacity(src, dst)
            if link_used.get(edge, 0) >= cap:
                continue

            dst_type = self.graph.zones[dst].zone_type

            # restricted: begin transit now, arrive next turn
            if dst_type == ZoneType.RESTRICTED:
                if self.occupancy[dst] >= self._zone_capacity(dst):
                    continue

                self.occupancy[src] -= 1
                self.occupancy[dst] += 1  # reserve slot immediately
                link_used[edge] = link_used.get(edge, 0) + 1

                drone.in_transit = True
                drone.transit_src = src
                drone.transit_dst = dst

                moves.append(f"D{drone.drone_id}-{src}-{dst}")
                continue

            # normal/priority/end: instant arrival this turn
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

    def run(self, max_turns: int = 100_000) -> List[List[str]]:
        """Run simulation until all drones delivered or deadlock."""
        history: List[List[str]] = []

        for _ in range(max_turns):
            if all(d.finished for d in self.drones):
                break

            turn_moves = self.step()
            if turn_moves:
                history.append(turn_moves)
            elif not all(d.finished for d in self.drones):
                in_transit = any(
                    d.in_transit for d in self.drones if not d.finished
                )
                if not in_transit:
                    stuck = sum(1 for d in self.drones if not d.finished)
                    raise RuntimeError(
                        f"Deadlock detected: {stuck} drone(s) are stuck"
                    )

        return history

    def _resolve_transit_arrivals(
        self,
        moves: List[str],
        link_used: Dict[Tuple[str, str], int],
    ) -> None:
        """Resolve drones already in restricted transit (must arrive now)."""
        for drone in self.drones:
            if drone.finished or not drone.in_transit:
                continue

            assert drone.transit_src is not None
            assert drone.transit_dst is not None

            src = drone.transit_src
            dst = drone.transit_dst

            edge = self._norm_edge(src, dst)
            cap = self._find_link_capacity(src, dst)

            # Must arrive now; occupancy was reserved on transit start
            # — only check link capacity, do not increment dst again.
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

    def _zone_capacity(self, zone_name: str) -> int:
        """Return effective zone capacity with start/end exceptions."""
        if zone_name == self.start or zone_name == self.end:
            return 10**9
        return self.graph.zones[zone_name].max_drones

    def _is_blocked(self, zone_name: str) -> bool:
        """Check blocked-zone enter rule."""
        if zone_name == self.end:
            return False
        return self.graph.zones[zone_name].zone_type == ZoneType.BLOCKED

    def _find_link_capacity(self, a: str, b: str) -> int:
        """Get link capacity between connected zones."""
        for nei, conn in self.graph.neighbors(a):
            if nei.name == b:
                return conn.max_link_capacity
        raise ValueError(f"No connection between '{a}' and '{b}'")

    def _validate_path_edges(self, path: List[str]) -> None:
        """Ensure each consecutive pair is connected."""
        for i in range(len(path) - 1):
            _ = self._find_link_capacity(path[i], path[i + 1])

    def _norm_edge(self, a: str, b: str) -> Tuple[str, str]:
        """Normalize undirected edge key."""
        return (a, b) if a < b else (b, a)


def format_turns(turns: List[List[str]]) -> str:
    """Format turns as terminal-friendly lines."""
    return "\n".join(" ".join(t) for t in turns)
