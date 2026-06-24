from __future__ import annotations
import heapq
from typing import Final
from parser import FlightMap, ZoneBehavior


class Path:
    """A sequence of zone names with the total turn cost."""

    def __init__(self, zones: tuple[str, ...], cost: int) -> None:
        self.zones: tuple[str, ...] = zones
        self.cost: int = cost

    def __len__(self) -> int:
        return len(self.zones)


class PathFinder:
    """Dijkstra-based finder for shortest, disjoint, and diverse paths."""

    COST_INCREASE: Final[int] = 40

    def __init__(self, flight_map: FlightMap) -> None:
        self._map: FlightMap = flight_map

    def disjoint_paths(self, max_paths: int) -> list[Path]:
        """Generate strictly node-disjoint paths by blocking used internal zones."""
        paths: list[Path] = []
        blocked: set[str] = set()
        
        for _ in range(max_paths):
            p = self._search_with_blocked(blocked=frozenset(blocked))
            if p is None:
                break
            paths.append(p)
            blocked.update(p.zones[1:-1])
            
        return paths

    def diverse_paths(self, max_paths: int) -> list[Path]:
        """Generate multiple overlapping or disjoint paths using penalization loop."""
        paths: list[Path] = []
        edge_uses: dict[frozenset[str], int] = {}
        seen: set[tuple[str, ...]] = set()

        for _ in range(max_paths):
            p = self._search_with_blocked(edge_penalty=edge_uses)
            if p is None or p.zones in seen:
                break
                
            paths.append(p)
            seen.add(p.zones)
            
            for i in range(len(p.zones) - 1):
                key = frozenset({p.zones[i], p.zones[i + 1]})
                edge_uses[key] = edge_uses.get(key, 0) + 1
                
        return paths

    def _search(self, edge_penalty: dict[frozenset[str], int] | None = None) -> Path | None:
        """Fallback for single path search."""
        return self._search_with_blocked(edge_penalty=edge_penalty)

    def _search_with_blocked(
        self, 
        blocked: frozenset[str] = frozenset(), 
        edge_penalty: dict[frozenset[str], int] | None = None
    ) -> Path | None:
        """Core Dijkstra search supporting both blocked nodes and edge penalties."""
        m = self._map
        ctr: int = 0
        
        heap: list[tuple[int, int, int, str, tuple[str, ...]]] = [
            (0, 0, ctr, m.start_zone, (m.start_zone,))
        ]
        best: dict[str, tuple[int, int]] = {m.start_zone: (0, 0)}

        while heap:
            weight, prio, _, node, path = heapq.heappop(heap)

            if node == m.end_zone:
                actual_cost = 0
                for z in path[1:]:
                    if m.zones[z].kind == ZoneBehavior.RESTRICTED:
                        actual_cost += 2
                    else:
                        actual_cost += 1
                return Path(path, actual_cost)

            if best.get(node, (weight, prio)) < (weight, prio):
                continue

            for nb in m.adj[node]:
                if nb != m.end_zone and (nb in blocked or nb in path):
                    continue
                
                zone = m.zones[nb]
                if zone.kind == ZoneBehavior.BLOCKED:
                    continue

                if zone.kind == ZoneBehavior.RESTRICTED:
                    step_cost = 2
                else:
                    step_cost = 1

                if edge_penalty is not None:
                    edge_key = frozenset({node, nb})
                    step_cost += edge_penalty.get(edge_key, 0) * self.COST_INCREASE

                new_weight = weight + step_cost
                new_prio = prio + (0 if zone.kind == ZoneBehavior.PRIORITY else 1)
                key = (new_weight, new_prio)

                if key < best.get(nb, (10 ** 9, 10 ** 9)):
                    best[nb] = key
                    ctr += 1
                    heapq.heappush(heap, (new_weight, new_prio, ctr, nb, path + (nb,)))
                    
        return None


class Scheduler:
    """Greedily distributes drones across discovered routes to balance timeline loads."""

    def __init__(self, paths: list[Path]) -> None:
        if not paths:
            raise ValueError("No paths available to schedule.")
        self._paths: list[Path] = paths

    def assign(self, n_drones: int) -> list[int]:
        """Map each drone ID to a path index ensuring optimal concurrent arrivals."""
        load = [0] * len(self._paths)
        assignments: list[int] = []
        
        for _ in range(n_drones):
            best_path_idx = min(
                range(len(self._paths)),
                key=lambda i: self._paths[i].cost + load[i]
            )
            assignments.append(best_path_idx)
            load[best_path_idx] += 1
            
        return assignments


class Drone:
    """Maintains flight parameters and transit state counters turn-by-turn."""

    def __init__(self, drone_id: int, path: tuple[str, ...]) -> None:
        self.drone_id: int = drone_id
        self.path: tuple[str, ...] = path
        self.step: int = 0
        self.transit: int = 0
        self.delivered: bool = False

    @property
    def location(self) -> str:
        return self.path[self.step]

    @property
    def next_zone(self) -> str | None:
        if self.step + 1 < len(self.path):
            return self.path[self.step + 1]
        return None


class Frame:
    """Data log capture containing active drone adjustments inside a unique turn."""

    def __init__(self, turn: int) -> None:
        self.turn: int = turn
        self.moves: list[str] = []


class Simulator:
    """Engine responsible for moving drones step-by-step honoring layout constraints."""

    _UNLIMITED: Final[int] = 10 ** 9

    def __init__(self, flight_map: FlightMap) -> None:
        self._map: FlightMap = flight_map

    def run(self, paths: list[Path], assignments: list[int]) -> list[Frame]:
        """Simulate and extract tracking metrics until all drones are delivered."""
        m = self._map
        drones = [
            Drone(drone_id=i + 1, path=paths[a].zones)
            for i, a in enumerate(assignments)
        ]
        
        for d in drones:
            if d.location == m.end_zone:
                d.delivered = True

        occupancy: dict[str, int] = {z: 0 for z in m.zones}
        occupancy[m.start_zone] = sum(1 for d in drones if not d.delivered)

        frames: list[Frame] = []
        turn_counter: int = 0
        
        while not all(d.delivered for d in drones):
            turn_counter += 1
            if turn_counter > 5000:
                raise RuntimeError("Simulation diverged or deadlocked internally.")
            
            frame = Frame(turn=turn_counter)
            landing_ids = {d.drone_id for d in drones if d.transit > 0}

            # Phase 1: Advance in-transit drones to their final landing zones
            for d in drones:
                if d.drone_id not in landing_ids or d.delivered:
                    continue
                d.transit -= 1
                d.step += 1
                dest = d.path[d.step]
                frame.moves.append(f"D{d.drone_id}-{dest}")
                if dest == m.end_zone:
                    d.delivered = True

            # Phase 2: Move waiting/idle drones forward based on layout capacities
            edge_uses: dict[frozenset[str], int] = {}
            any_move_made = False 
            
            for d in sorted(drones, key=lambda x: -x.step):
                if d.delivered or d.drone_id in landing_ids or d.next_zone is None:
                    continue
                
                nxt = d.next_zone
                zone = m.zones[nxt]
                
                edge_key = frozenset({d.location, nxt})
                if edge_key not in m.links:
                    continue
                edge = m.links[edge_key]
                
                if edge_uses.get(edge.key, 0) >= edge.max_capacity:
                    continue
                    
                cap = self._UNLIMITED if (zone.is_start or zone.is_end) else zone.max_drones
                if occupancy[nxt] + 1 > cap:
                    continue

                occupancy[d.location] -= 1
                occupancy[nxt] += 1
                edge_uses[edge.key] = edge_uses.get(edge.key, 0) + 1
                any_move_made = True
                
                if zone.kind == ZoneBehavior.RESTRICTED:
                    d.transit = 1
                    frame.moves.append(f"D{d.drone_id}-{edge.name}")
                else:
                    d.step += 1
                    frame.moves.append(f"D{d.drone_id}-{nxt}")
                    if nxt == m.end_zone:
                        d.delivered = True

            if not any_move_made and not landing_ids:
                raise RuntimeError("Simulation deadlocked: No drones can move.")

            frames.append(frame)
        return frames
