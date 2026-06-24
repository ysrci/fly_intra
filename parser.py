from __future__ import annotations
from enum import Enum
import re


class ZoneBehavior(Enum):
    """Enumeration type and rules of a zone."""

    NORMAL = "normal"
    RESTRICTED = "restricted"
    PRIORITY = "priority"
    BLOCKED = "blocked"


class ParseError(ValueError):
    """Custom exception raised for parsing errors with line tracking."""
    def __init__(self, message: str, line_num: int | None = None) -> None:
        if line_num is not None:
            super().__init__(f"[Line {line_num}] {message}")
        else:
            super().__init__(message)


class Zone:
    """Represents a single zone (hub) in the map."""

    def __init__(
        self,
        name: str,
        x: int,
        y: int,
        kind: ZoneBehavior = ZoneBehavior.NORMAL,
        color: str = "",
        max_drones: int = 1,
        is_start: bool = False,
        is_end: bool = False,
    ) -> None:
        self.name: str = name
        self.x: int = x
        self.y: int = y
        self.kind: ZoneBehavior = kind
        self.color: str = color
        self.max_drones: int = max_drones
        self.is_start: bool = is_start
        self.is_end: bool = is_end


class Connection:
    """Represents a bidirectional link between two zones."""

    def __init__(self, zone_a: str, zone_b: str, max_capacity: int = 1) -> None:
        self.node_a: str = zone_a
        self.node_b: str = zone_b
        self.max_capacity: int = max_capacity

    @property
    def key(self) -> frozenset[str]:
        return frozenset({self.node_a, self.node_b})

    @property
    def name(self) -> str:
        return f"{self.node_a}-{self.node_b}"


class FlightMap:
    """Graph structure managing all parsed zones and connections."""

    def __init__(self) -> None:
        self.zones: dict[str, Zone] = {}
        self.links: dict[frozenset[str], Connection] = {}
        self.adj: dict[str, list[str]] = {}
        self.start: str | None = None
        self.end: str | None = None
        self.nb_drones: int = 0

    @property
    def start_zone(self) -> str:
        if self.start is None:
            raise ParseError("Missing start_hub assignment in the map file.")
        return self.start

    @property
    def end_zone(self) -> str:
        if self.end is None:
            raise ParseError("Missing end_hub assignment in the map file.")
        return self.end

    def add_zone(self, zone: Zone, line_num: int) -> None:
        if zone.name in self.zones:
            raise ParseError(f"Duplicate zone definition: {zone.name}", line_num)
        if zone.max_drones <= 0:
            raise ParseError(f"Zone max_drones must be positive: {zone.name}", line_num)
        self.zones[zone.name] = zone
        self.adj[zone.name] = []

    def add_link(self, link: Connection, line_num: int) -> None:
        if link.node_a not in self.zones or link.node_b not in self.zones:
            raise ParseError(f"Connection targets missing zones: {link.name}", line_num)
        if link.key in self.links:
            raise ParseError(f"Duplicate connection detected: {link.name}", line_num)
        if link.max_capacity <= 0:
            raise ParseError(f"Connection capacity must be positive: {link.name}", line_num)

        self.links[link.key] = link
        self.adj[link.node_a].append(link.node_b)
        self.adj[link.node_b].append(link.node_a)


class MapParser:
    """Factory parser to process official map text files with strict properties validation."""

    ZONE_PAT = re.compile(
        r"^(hub|start_hub|end_hub):\s*(\w+)\s+(-?\d+)\s+(-?\d+)(?:\s+\[(.*)\])?$"
    )
    LINK_PAT = re.compile(r"^connection:\s*(\w+)-(\w+)(?:\s+\[(.*)\])?$")
    PROP_KV_PAT = re.compile(r"^(\w+)=(\w+)$")

    @classmethod
    def _parse_properties(cls, props_str: str, line_num: int) -> dict[str, str]:
        result: dict[str, str] = {}
        if not props_str.strip():
            return result

        tokens = props_str.strip().split()
        for token in tokens:
            match = cls.PROP_KV_PAT.match(token)
            if not match:
                raise ParseError(
                    f"Invalid property format '{token}'. Expected 'key=value'.", line_num
                )

            key, value = match.groups()
            result[key] = value
        return result

    @classmethod
    def load_file(cls, file_path: str) -> FlightMap:
        flight_map = FlightMap()
        seen_coordinates: set[tuple[int, int]] = set()

        with open(file_path, "r") as file:
            for line_idx, line in enumerate(file, start=1):
                clean_line = line.split("#")[0].strip()
                if not clean_line:
                    continue

                if clean_line.startswith("nb_drones:"):
                    try:
                        val = int(clean_line.split(":")[1].strip())
                    except ValueError:
                        raise ParseError(f"Invalid integer for nb_drones: {clean_line}", line_idx)

                    if val <= 0:
                        raise ParseError(
                            f"Number of drones must be a positive integer, got: {val}", line_idx
                        )
                    flight_map.nb_drones = val
                    continue

                if (
                    clean_line.startswith("hub:")
                    or clean_line.startswith("start_hub:")
                    or clean_line.startswith("end_hub:")
                ):
                    match = cls.ZONE_PAT.match(clean_line)
                    if not match:
                        raise ParseError(f"Malformed hub line syntax: {clean_line}", line_idx)

                    prefix, name, x_str, y_str, props_str = match.groups()

                    # Here we parse coordinates and validate uniqueness
                    x_val = int(x_str)
                    y_val = int(y_str)
                    coords = (x_val, y_val)

                    if coords in seen_coordinates:
                        raise ParseError(
                            f"Duplicate coordinates found at ({x_val}, {y_val}) "
                            f"for hub '{name}'.",
                            line_idx,
                        )
                    seen_coordinates.add(coords)

                    is_start = (prefix == "start_hub")
                    is_end = (prefix == "end_hub")

                    if is_start:
                        if flight_map.start is not None:
                            raise ParseError(
                                "Duplicate start_hub: only one is allowed.", line_idx
                            )
                        flight_map.start = name
                    if is_end:
                        if flight_map.end is not None:
                            raise ParseError(
                                "Duplicate end_hub: only one is allowed.", line_idx
                            )
                        flight_map.end = name

                    kind = ZoneBehavior.NORMAL
                    max_drones = 1
                    color = ""

                    if props_str:
                        props = cls._parse_properties(props_str, line_idx)

                        if "zone" in props:
                            zone_val = props["zone"]
                            if zone_val == "normal":
                                kind = ZoneBehavior.NORMAL
                            elif zone_val == "restricted":
                                kind = ZoneBehavior.RESTRICTED
                            elif zone_val == "priority":
                                kind = ZoneBehavior.PRIORITY
                            elif zone_val == "blocked":
                                kind = ZoneBehavior.BLOCKED
                            else:
                                raise ParseError(
                                    f"Unknown zone behavior value: {zone_val}", line_idx
                                )

                        if "max_drones" in props:
                            try:
                                max_drones = int(props["max_drones"])
                            except ValueError:
                                raise ParseError(
                                    f"max_drones must be an integer, "
                                    f"got: {props['max_drones']}",
                                    line_idx,
                                )

                        if "color" in props:
                            color = props["color"]

                    new_zone = Zone(
                        name=name,
                        x=x_val,
                        y=y_val,
                        kind=kind,
                        color=color,
                        max_drones=max_drones,
                        is_start=is_start,
                        is_end=is_end,
                    )
                    flight_map.add_zone(new_zone, line_idx)
                    continue

                if clean_line.startswith("connection:"):
                    match = cls.LINK_PAT.match(clean_line)
                    if not match:
                        raise ParseError(
                            f"Malformed connection line syntax: {clean_line}", line_idx
                        )

                    zone_a, zone_b, props_str = match.groups()
                    max_capacity = 1

                    if props_str:
                        props = cls._parse_properties(props_str, line_idx)
                        if "max_link_capacity" in props:
                            try:
                                max_capacity = int(props["max_link_capacity"])
                            except ValueError:
                                raise ParseError(
                                    "max_link_capacity must be an integer", line_idx
                                )

                    new_conn = Connection(
                        zone_a=zone_a, zone_b=zone_b, max_capacity=max_capacity
                    )
                    flight_map.add_link(new_conn, line_idx)
                    continue

                raise ParseError(f"Unknown command instruction: {clean_line}", line_idx)

        if flight_map.start_zone not in flight_map.zones:
            raise ParseError(f"Assigned start_hub '{flight_map.start}' does not exist.")
        if flight_map.end_zone not in flight_map.zones:
            raise ParseError(f"Assigned end_hub '{flight_map.end}' does not exist.")

        return flight_map


if __name__ == "__main__":
    test_file = "test.txt"

    try:
        parsed_map = MapParser.load_file(test_file)
        print("[SUCCESS] Map parsed successfully into RAM structure!")
    except ParseError as err:
        print(f"[PARSE ERROR] {err}")
    except FileNotFoundError:
        print(f"File '{test_file}' not found.")
