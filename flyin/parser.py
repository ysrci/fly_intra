from __future__ import annotations
import re
from typing import Tuple

from models import Connection, Graph, Zone, ZoneType


class ParseError(ValueError):
    """Custom exception raised for parsing errors with line tracking."""

    def __init__(self, message: str, line_num: int | None = None) -> None:
        if line_num is not None:
            super().__init__(f"[Line {line_num}] {message}")
        else:
            super().__init__(message)


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
    def load_file(cls, file_path: str) -> Tuple[int, str, str, Graph]:
        flight_map = Graph()
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

                    kind = ZoneType.NORMAL
                    max_drones = 1
                    color = ""

                    if props_str:
                        props = cls._parse_properties(props_str, line_idx)

                        if "zone" in props:
                            zone_val = props["zone"]
                            if zone_val == "normal":
                                kind = ZoneType.NORMAL
                            elif zone_val == "restricted":
                                kind = ZoneType.RESTRICTED
                            elif zone_val == "priority":
                                kind = ZoneType.PRIORITY
                            elif zone_val == "blocked":
                                kind = ZoneType.BLOCKED
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
                        zone_type=kind,
                        color=color,
                        max_drones=max_drones,
                        is_start=is_start,
                        is_end=is_end,
                    )
                    flight_map.add_zone(new_zone)
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
                        node_a=zone_a, node_b=zone_b, max_link_capacity=max_capacity
                    )
                    flight_map.add_link(new_conn)
                    continue

                raise ParseError(f"Unknown command instruction: {clean_line}", line_idx)

        if flight_map.start_zone not in flight_map.zones:
            raise ParseError(f"Assigned start_hub '{flight_map.start}' does not exist.")
        if flight_map.end_zone not in flight_map.zones:
            raise ParseError(f"Assigned end_hub '{flight_map.end}' does not exist.")

        return flight_map.nb_drones, flight_map.start_zone, flight_map.end_zone, flight_map


def parse_file(file_path: str) -> Tuple[int, str, str, Graph]:
    return MapParser.load_file(file_path)


if __name__ == "__main__":
    test_file = "test.txt"

    try:
        nb, st, en, parsed_map = MapParser.load_file(test_file)
        print("[SUCCESS] Map parsed successfully into RAM structure!")
    except ParseError as err:
        print(f"[PARSE ERROR] {err}")
    except FileNotFoundError:
        print(f"File '{test_file}' not found.")
