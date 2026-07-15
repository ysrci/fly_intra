from __future__ import annotations
import heapq
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from models import Graph
from simulator import Simulation


@dataclass(frozen=True)
class PathResult:
    """Store one path."""
    path: List[str]
    cost: int
    property_count: int


@dataclass(frozen=True)
class AllocationResult:
    """Store drone paths."""
    assignments: List[List[str]]
    nb_turns: int


class MultiPathFinder:
    """Find the best paths."""
    def __init__(self, graph: Graph) -> None:
        """Save the graph."""
        self.graph = graph

    def best_single_path(self,
                         start: str, end: str,
                         penalty: Optional[Dict[str, int]] = None
                         ) -> Optional[PathResult]:
        """Find the best path."""
        dist: Dict[str, int] = {z: 10**9 for z in self.graph.zones}
        prio_score: Dict[str, int] = {z: -10**9 for z in self.graph.zones}
        prev: Dict[str, Optional[str]] = {z: None for z in self.graph.zones}

        dist[start] = 0
        prio_score[start] = 0

        heap: List[Tuple[int, int, str]] = [(0, 0, start)]

        while heap:
            cost, neg_priority, zone = heapq.heappop(heap)
            priority = -neg_priority

            if cost > dist[zone]:
                continue
            if cost == dist[zone] and priority < prio_score[zone]:
                continue
            if zone == end:
                break

            for v_zone, _ in self.graph.neighbors(zone):
                name = v_zone.name
                # remove v != end
                if self.graph.zones[name].zone_type == "blocked":
                    continue
                step = self._move_cost(name)
                extra = 0 if penalty is None else penalty.get(name, 0)

                nd = cost + step + extra
                np = priority + (
                    1
                    if self.graph.zones[name].zone_type == "priority"
                    else 0)

                better = False
                if nd < dist[name]:
                    better = True
                elif nd == dist[name] and np > prio_score[name]:
                    better = True

                if better:
                    dist[name] = nd
                    prio_score[name] = np
                    prev[name] = zone
                    heapq.heappush(heap, (nd, -np, name))

        if dist[end] >= 10**9:
            return None

        path = self._reconstruct(prev, start, end)
        if not path:
            return None

        if penalty is None:
            real_cost = dist[end]
        else:
            real_cost = self._path_real_cost(path)

        return PathResult(path, real_cost, prio_score[end])

    def extra_path(self, start: str, end: str, k: int = 6) -> List[PathResult]:
        """Find many paths."""
        base = self.best_single_path(start, end)
        if base is None:
            return []
        candidates: List[PathResult] = [base]
        seen = {tuple(base.path)}
        penalize_nodes: Dict[str, int] = {}

        for _ in range(k - 1):
            for p in candidates[-1].path[1:-1]:
                penalize_nodes[p] = penalize_nodes.get(p, 0) + 1

            alt = self.best_single_path(start, end, penalize_nodes)
            if alt is None:
                break
            key = tuple(alt.path)
            if key in seen:
                break
            seen.add(key)
            candidates.append(alt)
            candidates.sort(
                key=lambda p: (p.cost, -p.property_count, len(p.path))
            )
        return candidates

    def drone_waste(self,
                    start: str, end: str, nb_drones: int,
                    max_paths: int = 24) -> AllocationResult:
        """Choose paths for drones."""
        paths = self.extra_path(start, end, k=max_paths)
        if not paths:
            return AllocationResult(assignments=[], nb_turns=0)
        assignments: List[List[str]] = []
        for _ in range(nb_drones):
            best_i = 0
            best_score = 10**9

            for i, p in enumerate(paths):
                test_assign = assignments + [p.path]
                sim = Simulation(self.graph, test_assign)
                turns = len(sim.run(max_turns=2000))
                if turns < best_score:
                    best_score = turns
                    best_i = i
            assignments.append(paths[best_i].path)
        final_sim = Simulation(self.graph, assignments)
        estimated_turns = len(final_sim.run(max_turns=2000))
        return AllocationResult(assignments, estimated_turns)

    def _path_real_cost(self, path: List[str]) -> int:
        """Get the path cost."""
        cost = 0
        for name in path[1:]:
            cost += self._move_cost(name)
        return cost

    def _move_cost(self, zone: str) -> int:
        """Return move cost."""
        if self.graph.zones[zone].zone_type == "restricted":
            return 2
        return 1

    def _reconstruct(self,
                     prev: Dict[str, Optional[str]], start: str,
                     end: str) -> List[str]:
        """Build the path."""
        path: List[str] = []
        cur: Optional[str] = end
        while cur is not None:
            path.append(cur)
            cur = prev[cur]
        path.reverse()
        if not path or path[0] != start:
            return []
        return path
