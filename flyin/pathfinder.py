from __future__ import annotations

import heapq
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from models import Graph, ZoneType


@dataclass(frozen=True)
class PathResult:
    """Represents one candidate route from start to end."""

    path: List[str]
    cost: int
    priority_count: int


@dataclass(frozen=True)
class AllocationResult:
    """Represents path allocation for all drones."""

    assignments: List[List[str]]  # one path per drone
    estimated_turns: int


class MultiPathFinder:
    """Find and allocate multiple valid paths for drone routing."""

    def __init__(self, graph: Graph) -> None:
        """Initialize with graph reference."""
        self.graph = graph

    def best_single_path(
        self, start: str, end: str
    ) -> Optional[PathResult]:
        """Compute best single path using weighted Dijkstra.

        Tie-break:
            - lower total cost first
            - if equal cost, prefer path with more priority zones
        """
        self._check_zone_exists(start)
        self._check_zone_exists(end)

        dist: Dict[str, int] = {z: 10**18 for z in self.graph.zones}
        prio_score: Dict[str, int] = {
            z: -(10**18) for z in self.graph.zones
        }
        prev: Dict[str, Optional[str]] = {
            z: None for z in self.graph.zones
        }

        dist[start] = 0
        prio_score[start] = 0

        # heap item: (cost, -priority_count, node)
        heap: List[Tuple[int, int, str]] = [(0, 0, start)]

        while heap:
            cur_cost, neg_prio, u = heapq.heappop(heap)
            cur_prio = -neg_prio

            if cur_cost > dist[u]:
                continue
            if cur_cost == dist[u] and cur_prio < prio_score[u]:
                continue

            if u == end:
                break

            for v_zone, _conn in self.graph.neighbors(u):
                v = v_zone.name
                if (
                    self.graph.zones[v].zone_type == ZoneType.BLOCKED
                    and v != end
                ):
                    continue

                step = self._move_cost(v)
                nd = cur_cost + step
                np = cur_prio + (
                    1
                    if self.graph.zones[v].zone_type == ZoneType.PRIORITY
                    else 0
                )

                better = False
                if nd < dist[v]:
                    better = True
                elif nd == dist[v] and np > prio_score[v]:
                    better = True

                if better:
                    dist[v] = nd
                    prio_score[v] = np
                    prev[v] = u
                    heapq.heappush(heap, (nd, -np, v))

        if dist[end] >= 10**18:
            return None

        path = self._reconstruct(prev, start, end)
        if not path:
            return None

        return PathResult(
            path=path,
            cost=dist[end],
            priority_count=prio_score[end],
        )

    def k_candidate_paths(
        self, start: str, end: str, k: int = 6
    ) -> List[PathResult]:
        """Generate up to k candidate simple paths via penalization.

        This is a practical heuristic (not full Yen algorithm), good
        enough for project scale.
        """
        base = self.best_single_path(start, end)
        if base is None:
            return []

        candidates: List[PathResult] = [base]
        seen = {tuple(base.path)}

        # Penalize internal nodes of already-selected paths
        penalized_nodes: Dict[str, int] = {}

        for _ in range(k - 1):
            for p in candidates[-1].path[1:-1]:
                penalized_nodes[p] = penalized_nodes.get(p, 0) + 1

            alt = self._best_path_with_penalty(
                start, end, penalized_nodes
            )
            if alt is None:
                break
            key = tuple(alt.path)
            if key in seen:
                break
            seen.add(key)
            candidates.append(alt)

        # Sort by (cost asc, priority desc, length asc)
        candidates.sort(
            key=lambda p: (p.cost, -p.priority_count, len(p.path))
        )
        return candidates

    def allocate_drones(
        self,
        start: str,
        end: str,
        nb_drones: int,
        max_paths: int = 24,
    ) -> AllocationResult:
        """Allocate drones using greedy earliest-finish heuristic."""
        if nb_drones < 1:
            raise ValueError("nb_drones must be >= 1")

        from simulator import Simulation

        paths = self.k_candidate_paths(start, end, k=max_paths)
        if not paths:
            return AllocationResult(assignments=[], estimated_turns=0)

        assignments: List[List[str]] = []

        for drone_idx in range(nb_drones):
            best_i = 0
            best_score = 10**9

            for i, p in enumerate(paths):
                # Try adding path p
                test_assign = assignments + [p.path]
                # we pad the remaining drones with the best path so far just to pass the constructor
                # or we just simulate with fewer drones
                sim = Simulation(self.graph, test_assign)
                try:
                    turns = len(sim.run(max_turns=2000))
                    if turns < best_score:
                        best_score = turns
                        best_i = i
                except RuntimeError:
                    # ignore deadlock paths
                    pass

            assignments.append(paths[best_i].path)

        # final sim
        try:
            final_sim = Simulation(self.graph, assignments)
            estimated_turns = len(final_sim.run(max_turns=2000))
        except RuntimeError:
            estimated_turns = 10**9

        return AllocationResult(
            assignments=assignments,
            estimated_turns=estimated_turns,
        )

    # ---------- Internal helpers ----------
    def _best_path_with_penalty(
        self,
        start: str,
        end: str,
        penalty: Dict[str, int],
    ) -> Optional[PathResult]:
        """Dijkstra variant with additional node penalties."""
        dist: Dict[str, int] = {z: 10**18 for z in self.graph.zones}
        prio_score: Dict[str, int] = {
            z: -(10**18) for z in self.graph.zones
        }
        prev: Dict[str, Optional[str]] = {
            z: None for z in self.graph.zones
        }

        dist[start] = 0
        prio_score[start] = 0

        heap: List[Tuple[int, int, str]] = [(0, 0, start)]

        while heap:
            cur_cost, neg_prio, u = heapq.heappop(heap)
            cur_prio = -neg_prio

            if cur_cost > dist[u]:
                continue
            if cur_cost == dist[u] and cur_prio < prio_score[u]:
                continue

            if u == end:
                break

            for v_zone, _conn in self.graph.neighbors(u):
                v = v_zone.name
                if (
                    self.graph.zones[v].zone_type == ZoneType.BLOCKED
                    and v != end
                ):
                    continue

                base = self._move_cost(v)
                extra = penalty.get(v, 0)
                nd = cur_cost + base + extra
                np = cur_prio + (
                    1
                    if self.graph.zones[v].zone_type == ZoneType.PRIORITY
                    else 0
                )

                better = False
                if nd < dist[v]:
                    better = True
                elif nd == dist[v] and np > prio_score[v]:
                    better = True

                if better:
                    dist[v] = nd
                    prio_score[v] = np
                    prev[v] = u
                    heapq.heappush(heap, (nd, -np, v))

        if dist[end] >= 10**18:
            return None

        path = self._reconstruct(prev, start, end)
        if not path:
            return None

        real_cost = self._path_real_cost(path)
        prio_count = sum(
            1
            for name in path[1:]
            if self.graph.zones[name].zone_type == ZoneType.PRIORITY
        )

        return PathResult(
            path=path, cost=real_cost, priority_count=prio_count
        )

    def _path_real_cost(self, path: List[str]) -> int:
        """Compute actual weighted path cost from destination types."""
        cost = 0
        for name in path[1:]:
            cost += self._move_cost(name)
        return cost

    def _move_cost(self, dst_zone: str) -> int:
        """Movement cost by destination zone type."""
        zt = self.graph.zones[dst_zone].zone_type
        if zt == ZoneType.RESTRICTED:
            return 2
        return 1  # normal and priority

    def _path_congestion_score(
        self, p: PathResult, current_load: int
    ) -> int:
        """Greedy score for adding one more drone on this path."""
        return p.cost + current_load

    def _check_zone_exists(self, name: str) -> None:
        """Validate that a zone exists in graph."""
        if name not in self.graph.zones:
            raise ValueError(f"Unknown zone '{name}'")

    def _reconstruct(
        self,
        prev: Dict[str, Optional[str]],
        start: str,
        end: str,
    ) -> List[str]:
        """Reconstruct path from predecessor links."""
        path: List[str] = []
        cur: Optional[str] = end
        while cur is not None:
            path.append(cur)
            cur = prev[cur]
        path.reverse()
        if not path or path[0] != start:
            return []
        return path


# Backward compatibility with old code name
DijkstraPathfinder = MultiPathFinder
