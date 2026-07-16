from __future__ import annotations
import re
from models import Connection, Graph, Zone


class ParseError(ValueError):
    """Custom exception raised for parsing error with line tracking"""


class MapParser:
    """Parser for official map text files with strict validation"""
    def __init__(self) -> None:
        """init regex and colors and extra data"""
        self.ZONE_PAT = re.compile((
            r"^(hub|start_hub|end_hub):\s*(\w+)\s+(-?\d+)\s+(-?\d+)"
            r"(?:\s+\[(.*)\])?$"))
        self.LINK_PAT = re.compile(
            r"^connection:\s*(\w+)-(\w+)(?:\s+\[(.*)\])?$")
        self.PROP_KV_PAT = re.compile(r"^(\w+)=(\w+)$")
        self.key_metadata: list[str] = ["zone", "color", "max_drones",
                                        "max_link_capacity"]
        self.type_zone: list[str] = ["normal",
                                     "restricted", "priority", "blocked"]
        self.allow_color = {
            "red", "blue", "green", "gray",
            "yellow", "orange", "cyan", "purple",
            "brown", "lime", "magenta", "gold",
            "black", "maroon", "darkred", "violet",
            "crimson", "rainbow",

            "white", "silver", "navy", "teal",
            "olive", "aqua", "fuchsia", "pink",
            "hotpink", "deeppink", "lightblue",
            "skyblue", "deepskyblue", "darkblue",
            "lightgreen", "darkgreen", "forestgreen",
            "springgreen", "turquoise", "indigo",
            "beige", "tan", "khaki", "coral",
            "salmon", "tomato", "chocolate",
            "sienna", "peru", "plum", "orchid",
            "lavender", "ivory", "snow",
            "wheat", "azure"
        }

    def _parse_metadata(self, props_str: str, ln: int) -> dict[str, str]:
        """method parse metadata"""
        result: dict[str, str] = {}
        if not props_str.strip():
            return result
        for token in props_str.strip().split():
            match = self.PROP_KV_PAT.match(token)
            if not match:
                self._err(f"Invalid metadata '{token}' not 'key=value'", ln)
            assert match is not None
            key, value = match.groups()
            if key not in self.key_metadata:
                self._err(f"Invalid key '{key}'", ln)
            result[key] = value
        return result

    def parse_file(self, file_path: str) -> tuple[int, str, str, Graph]:
        """method load and parse map file"""
        flight_map = Graph()
        list_coords: set[tuple[int, int]] = set()
        existing_connections: set[tuple[str, str]] = set()

        try:
            with open(file_path, "r", encoding="utf-8") as file:
                for ln, line in enumerate(file, start=1):
                    cl_line = line.split("#", maxsplit=1)[0].strip()
                    if not cl_line:
                        continue
                    if cl_line.startswith("nb_drones:"):
                        if flight_map.nb_drones != 0:
                            self._err("Duplicate nb_drones declaration", ln)
                        try:
                            val = cl_line.split(":", maxsplit=1)[1]
                            num_dr = int(val.strip())
                        except (ValueError, IndexError):
                            self._err(
                                f"Invalid integer for nb_drones: {cl_line}",
                                ln)
                        if num_dr <= 0:
                            self._err(
                                "nb_drones must be >= 1", ln)
                        flight_map.nb_drones = num_dr
                        continue

                    if cl_line.startswith(("hub:", "start_hub:", "end_hub:")):
                        match = self.ZONE_PAT.match(cl_line)
                        if not match:
                            self._err(f"Invalid hub line syntax: {cl_line}",
                                      ln)
                        assert match is not None
                        type_hub, name_hub, x, y, metadata = match.groups()
                        coords = (int(x), int(y))
                        if coords in list_coords:
                            self._err(
                                f"Duplicat coordinates {coords} in {name_hub}",
                                ln)
                        list_coords.add(coords)

                        is_start = type_hub == "start_hub"
                        is_end = type_hub == "end_hub"
                        if is_start:
                            if flight_map.start is not None:
                                self._err("Duplicate start_hub", ln)
                            flight_map.start = name_hub

                        if is_end:
                            if flight_map.end is not None:
                                self._err("Duplocate end_hub", ln)
                            flight_map.end = name_hub

                        type_zone = "normal"
                        max_drones = 1
                        color = ""
                        if metadata:
                            data = self._parse_metadata(metadata, ln)
                            if "zone" in data:
                                if data["zone"] in self.type_zone:
                                    type_zone = data["zone"]
                                else:
                                    self._err(
                                        f"Invalid zone type: {data['zone']}",
                                        ln)
                            if "max_drones" in data:
                                try:
                                    max_drones = int(data['max_drones'])
                                    if max_drones <= 0:
                                        msg = "max_drone must be positive int"
                                        self._err(f"{msg}: {max_drones}", ln)
                                except ValueError:
                                    msg = "max_drones must be an integer"
                                    self._err(f"{msg}: {data['max_drones']}",
                                              ln)
                            if "color" in data:
                                if data['color'] not in self.allow_color:
                                    msg = f"Invalid color {data['color']}"
                                    self._err(f"{msg} use {self.allow_color}",
                                              ln)
                                color = data["color"]

                        new_zone = Zone(
                            name=name_hub, x=int(x), y=int(y),
                            zone_type=type_zone,
                            color=color, max_drones=max_drones,
                            is_start=is_start, is_end=is_end)

                        flight_map.add_zone(new_zone)
                        continue

                    if cl_line.startswith("connection:"):
                        match = self.LINK_PAT.match(cl_line)
                        if not match:
                            msg = "Invalid connection line syntax"
                            self._err(f"{msg}: {cl_line}", ln)
                        assert match is not None
                        zone_a, zone_b, metaconn = match.groups()
                        max_cap = 1

                        if metaconn:
                            data = self._parse_metadata(metaconn, ln)

                            if "max_link_capacity" in data:
                                try:
                                    max_cap = int(data['max_link_capacity'])
                                    if max_cap <= 0:
                                        msg = "max_link_capacity must"
                                        self._err(f"{msg} be positive integer",
                                                  ln)
                                except ValueError:
                                    msg = "max_link_capacity "
                                    self._err(f"{msg} must be an integer", ln)

                        if zone_a not in flight_map.zones:
                            self._err(f"Unknown zone '{zone_a}'", ln)
                        if zone_b not in flight_map.zones:
                            self._err(f"Unknown zone '{zone_b}'", ln)
                        # conn_key = tuple(sorted([zone_a, zone_b]))
                        if zone_a < zone_b:
                            conn_key = (zone_a, zone_b)
                        else:
                            conn_key = (zone_b, zone_a)
                        if conn_key in existing_connections:
                            self._err(f"Duplicate conc: {zone_a} and {zone_b}",
                                      ln)
                        existing_connections.add(conn_key)

                        new_conn = Connection(
                            node_a=zone_a,
                            node_b=zone_b,
                            max_link_capacity=max_cap
                        )
                        flight_map.add_link(new_conn)
                        continue
                    self._err(f"Invalid line: {cl_line}", ln)
        except OSError:
            self._err(f"File not found {file_path}", -1)

        if flight_map.start is None:
            self._err("Missing start_hub declaration.", -1)
        if flight_map.end is None:
            self._err("Missing end_hub declaration", -1)

        return (
            flight_map.nb_drones,
            flight_map.start_zone,
            flight_map.end_zone,
            flight_map,
        )

    @staticmethod
    def _err(msg: str, nl: int) -> None:
        """method raise Parse Error"""
        if nl == -1:
            raise ParseError(f"Error: {msg}")
        raise ParseError(f"Line: {nl}\nError: {msg}")


if __name__ == "__main__":
    parse = MapParser()
    line = "zone=riority color=green max_drones=2"
    try:
        parse.parse_file("test.txt")
    except ParseError as e:
        print(e)
