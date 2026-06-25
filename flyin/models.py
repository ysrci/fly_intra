from __future__ import annotations
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Tuple


class ZoneType(Enum):
    """Enumeration type and rules of a zone."""

    NORMAL = "normal"
    RESTRICTED = "restricted"
    PRIORITY = "priority"
    BLOCKED = "blocked"


@dataclass
class Zone:
    """Represents a single zone (hub) in the map."""
    name: str
    x: int
    y: int
    zone_type: ZoneType = ZoneType.NORMAL
    color: str = ""
    max_drones: int = 1
    is_start: bool = False
    is_end: bool = False


@dataclass
class Connection:
    """Represents a bidirectional link between two zones."""
    node_a: str
    node_b: str
    max_link_capacity: int = 1

    @property
    def key(self) -> frozenset[str]:
        return frozenset({self.node_a, self.node_b})

    @property
    def name(self) -> str:
        return f"{self.node_a}-{self.node_b}"


class Graph:
    """Graph structure managing all parsed zones and connections."""

    def __init__(self) -> None:
        self.zones: Dict[str, Zone] = {}
        self.links: Dict[frozenset[str], Connection] = {}
        # adj maps a zone name to a list of (Neighbor Zone, Connection Link)
        self.adj: Dict[str, List[Tuple[Zone, Connection]]] = {}
        self.start: str | None = None
        self.end: str | None = None
        self.nb_drones: int = 0

    @property
    def start_zone(self) -> str:
        if self.start is None:
            raise ValueError("Missing start_hub assignment in the map file.")
        return self.start

    @property
    def end_zone(self) -> str:
        if self.end is None:
            raise ValueError("Missing end_hub assignment in the map file.")
        return self.end

    def add_zone(self, zone: Zone) -> None:
        self.zones[zone.name] = zone
        if zone.name not in self.adj:
            self.adj[zone.name] = []

    def add_link(self, link: Connection) -> None:
        self.links[link.key] = link
        za = self.zones[link.node_a]
        zb = self.zones[link.node_b]
        self.adj[link.node_a].append((zb, link))
        self.adj[link.node_b].append((za, link))

    def neighbors(self, zone_name: str) -> List[Tuple[Zone, Connection]]:
        return self.adj.get(zone_name, [])
