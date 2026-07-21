# Line-by-Line Explanation of `parser.py`

> This document explains every single line of `parser.py` in simple, clear English —
> as if talking to the corrector during a peer-evaluation.

---

## 0 — Project Context (What the Subject Asks)

The **Fly-in** project is a drone routing simulation.
We are given a **map file** that describes:

1. **How many drones** we have (`nb_drones`).
2. **Zones** (nodes) — each zone has a name, (x, y) coordinates, an optional type
   (`normal`, `restricted`, `priority`, `blocked`), an optional color, and an optional
   drone capacity (`max_drones`).
3. **Connections** (edges) — bidirectional links between two zones, with an optional
   connection capacity (`max_link_capacity`).

There is exactly **one start zone** (`start_hub`) and **one end zone** (`end_hub`).
The parser must validate **everything strictly** and raise a clear error with the
line number if anything is wrong.

The parser builds a `Graph` object that is later used by the pathfinder and simulator
to move all drones from start to end in the fewest possible turns.

---

## 1 — Imports (Lines 1–3)

```python
from __future__ import annotations        # Line 1
import re                                  # Line 2
from models import Connection, Graph, Zone # Line 3
```

| Line | What it does |
|------|-------------|
| 1 | `from __future__ import annotations` — Lets us use modern type-hint syntax (like `str \| None`) even on Python 3.10. The type hints are stored as strings and only evaluated later. |
| 2 | `import re` — Imports the **regular expression** module. We use regex patterns to match and extract data from each line of the map file. |
| 3 | `from models import Connection, Graph, Zone` — Imports the three data classes from `models.py`: `Zone` (a node), `Connection` (an edge), and `Graph` (the full graph structure that holds zones, connections, and adjacency lists). |

---

## 2 — ParseError Exception (Lines 6–7)

```python
class ParseError(ValueError):
    """Custom exception raised for parsing error with line tracking"""
```

| Line | What it does |
|------|-------------|
| 6 | Creates a **custom exception class** called `ParseError` that extends Python's built-in `ValueError`. This lets us raise a specific error type for all parsing problems. |
| 7 | Simple docstring: explains that this exception tracks the line number where the error occurred. |

**Why?** — The subject says: *"Any parsing error must stop the program and return a clear error message indicating the line and cause."* This class makes that possible.

---

## 3 — MapParser Class Header and `__init__` (Lines 10–42)

```python
class MapParser:
    """Parser for official map text files with strict validation"""
    def __init__(self) -> None:
```

This is the main parser class. All parsing logic lives here.

### 3.1 — Regex Patterns (Lines 14–19)

```python
self.ZONE_PAT = re.compile((
    r"^(hub|start_hub|end_hub):\s*(\w+)\s+(-?\d+)\s+(-?\d+)"
    r"(?:\s+\[(.*)\])?$"))
self.LINK_PAT = re.compile(
    r"^connection:\s*(\w+)-(\w+)(?:\s+\[(.*)\])?$")
self.PROP_KV_PAT = re.compile(r"^(\w+)=(\w+)$")
```

| Pattern | Purpose | Example it matches |
|---------|---------|-------------------|
| `ZONE_PAT` | Matches a zone line. Captures: **(1)** hub type, **(2)** zone name, **(3)** x coordinate, **(4)** y coordinate, **(5)** optional metadata inside `[...]`. | `start_hub: hub 0 0 [color=green]` |
| `LINK_PAT` | Matches a connection line. Captures: **(1)** zone_a, **(2)** zone_b, **(3)** optional metadata. The `-` between zone names is why dashes are forbidden in zone names. | `connection: hub-roof1` |
| `PROP_KV_PAT` | Matches a single `key=value` token inside a metadata block. | `zone=restricted` |

### 3.2 — Allowed Metadata Keys (Lines 20–23)

```python
self.key_metadata: list[str] = ["zone", "color", "max_drones",
                                "max_link_capacity"]
self.type_zone: list[str] = ["normal",
                             "restricted", "priority", "blocked"]
```

- `key_metadata` — The only four metadata keys we accept. Anything else → error.
- `type_zone` — The only four valid zone types from the subject.

### 3.3 — Allowed Colors (Lines 24–42)

```python
self.allow_color = {
    "red", "blue", "green", "gray",
    "yellow", "orange", "cyan", "purple",
    ...
    "wheat", "azure"
}
```

A **set** of all accepted color strings. The subject says: *"Accepted values for
color are any valid single-word strings"*, so this set covers a generous range of
common color names. Using a `set` makes lookup O(1).

---

## 4 — `_parse_metadata` Method (Lines 44–58)

```python
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
```

Step-by-step:

| Line(s) | What happens |
|---------|-------------|
| 46 | Create an empty dictionary to hold the parsed key-value pairs. |
| 47–48 | If the metadata string is empty or only whitespace, return the empty dict immediately. Nothing to parse. |
| 49 | Split the metadata string by whitespace. Each piece should be one `key=value` token. For example `"zone=restricted color=red max_drones=2"` becomes `["zone=restricted", "color=red", "max_drones=2"]`. |
| 50–52 | Try to match each token against the `key=value` regex. If it does not match, call `_err` to raise a `ParseError` with the line number. |
| 53 | `assert match is not None` — Helps the type checker (`mypy`) understand that after the error check, `match` is guaranteed to exist. |
| 54 | Extract the key and value from the regex match groups. |
| 55–56 | If the key is not in our allowed list (`zone`, `color`, `max_drones`, `max_link_capacity`), raise an error. |
| 57 | Store the key-value pair in the result dictionary. |
| 58 | Return the complete dictionary of parsed metadata. |

---

## 5 — `parse_file` Method (Lines 60–210)

This is the **main method** — it reads the entire map file, validates every line,
and builds the `Graph` object.

### 5.1 — Method Signature and Setup (Lines 60–64)

```python
def parse_file(self, file_path: str) -> tuple[int, str, str, Graph]:
    """method load and parse map file"""
    flight_map = Graph()
    list_coords: set[tuple[int, int]] = set()
    existing_connections: set[tuple[str, str]] = set()
```

| Variable | Purpose |
|----------|---------|
| `flight_map` | A new empty `Graph` object. We will fill it with zones and connections as we parse the file. |
| `list_coords` | A set to track all (x, y) coordinates we have seen so far. Used to detect **duplicate coordinates**. |
| `existing_connections` | A set of sorted zone-name pairs. Used to detect **duplicate connections** (a-b and b-a are the same connection). |

The return type is `tuple[int, str, str, Graph]`:
- `int` → number of drones
- `str` → start zone name
- `str` → end zone name
- `Graph` → the full parsed graph

### 5.2 — File Opening and Line Loop (Lines 66–71)

```python
try:
    with open(file_path, "r", encoding="utf-8") as file:
        for ln, line in enumerate(file, start=1):
            cl_line = line.split("#", maxsplit=1)[0].strip()
            if not cl_line:
                continue
```

| Line | What it does |
|------|-------------|
| 66 | `try:` — Wraps the entire file reading in a try block to catch `OSError` (file not found, permission denied, etc.). |
| 67 | Opens the file with UTF-8 encoding using a **context manager** (`with`). This guarantees the file is closed even if an error occurs. |
| 68 | `enumerate(file, start=1)` — Loops over every line in the file. `ln` is the **line number** starting from 1. We need this for error messages. |
| 69 | **Removes comments**: splits the line at the first `#` character and takes only the part before it. Then strips leading/trailing whitespace. Example: `"hub: A 1 2 # a comment"` → `"hub: A 1 2"`. |
| 70–71 | If the cleaned line is empty (blank line or comment-only line), **skip it** and go to the next line. |

### 5.3 — Parsing `nb_drones` (Lines 72–86)

```python
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
```

| Line(s) | What it does |
|---------|-------------|
| 72 | Check if this line starts with `"nb_drones:"`. |
| 73–74 | If `nb_drones` was already set (not 0), raise an error — the subject says this line must appear only once. |
| 75–77 | Split the line at `:`, take the part after it, strip whitespace, and convert to integer. For `"nb_drones: 5"`, `val` = `" 5"`, then `num_dr` = `5`. |
| 78–81 | If the conversion fails (`ValueError`) or the split fails (`IndexError`), raise a parse error with the line number. |
| 82–84 | The number of drones must be **at least 1**. Zero or negative → error. |
| 85 | Store the drone count in the graph object. |
| 86 | `continue` — Move to the next line. |

### 5.4 — Parsing Zone Lines (Lines 88–150)

```python
if cl_line.startswith(("hub:", "start_hub:", "end_hub:")):
```

This handles all three zone types in one block.

#### 5.4.1 — Regex Match (Lines 89–93)

```python
    match = self.ZONE_PAT.match(cl_line)
    if not match:
        self._err(f"Invalid hub line syntax: {cl_line}", ln)
    assert match is not None
    type_hub, name_hub, x, y, metadata = match.groups()
```

- Apply the zone regex. If it does not match, the syntax is wrong → error.
- Extract the five captured groups: hub type, zone name, x, y, and optional metadata string.

#### 5.4.2 — Duplicate Coordinate Check (Lines 95–100)

```python
    coords = (int(x), int(y))
    if coords in list_coords:
        self._err(
            f"Duplicat coordinates {coords} in {name_hub}", ln)
    list_coords.add(coords)
```

- Convert x and y to integers and make a tuple.
- If we have already seen these exact coordinates → error. The subject says *"Each zone must have unique coordinates."*
- Otherwise, add the coordinates to the tracking set.

#### 5.4.3 — Start/End Hub Logic (Lines 102–112)

```python
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
```

- Set boolean flags based on the hub type.
- If we already have a start (or end), and we find another one → error. The subject says exactly **one** start and **one** end.
- Store the zone name in the graph's `start` or `end` field.

#### 5.4.4 — Processing Metadata (Lines 114–141)

```python
    type_zone = "normal"
    max_drones = 1
    color = ""
    if metadata:
        data = self._parse_metadata(metadata, ln)
```

- Set **defaults**: zone type is `"normal"`, max drones is `1`, color is empty.
- If the metadata string exists (the `[...]` part was present), parse it.

**Zone type validation (Lines 119–125):**

```python
        if "zone" in data:
            if data["zone"] in self.type_zone:
                type_zone = data["zone"]
            else:
                self._err(f"Invalid zone type: {data['zone']}", ln)
```

- If a `zone=...` key exists, check that its value is one of the four allowed types.
- If it is valid, use it. If not → error.

**max_drones validation (Lines 126–135):**

```python
        if "max_drones" in data:
            try:
                max_drones = int(data['max_drones'])
                if max_drones <= 0:
                    msg = "max_drone must be positive int"
                    self._err(f"{msg}: {max_drones}", ln)
            except ValueError:
                msg = "max_drones must be an integer"
                self._err(f"{msg}: {data['max_drones']}", ln)
```

- If `max_drones=...` is present, convert it to integer.
- Must be **positive** (> 0). Zero or negative → error.
- If the conversion fails (not a number) → error.

**Color validation (Lines 136–141):**

```python
        if "color" in data:
            if data['color'] not in self.allow_color:
                msg = f"Invalid color {data['color']}"
                self._err(f"{msg} use {self.allow_color}", ln)
            color = data["color"]
```

- If `color=...` is present, check it exists in our allowed color set.
- If valid, use it. If not → error.

#### 5.4.5 — Creating and Adding the Zone (Lines 143–150)

```python
    new_zone = Zone(
        name=name_hub, x=int(x), y=int(y),
        zone_type=type_zone,
        color=color, max_drones=max_drones,
        is_start=is_start, is_end=is_end)
    flight_map.add_zone(new_zone)
    continue
```

- Create a new `Zone` dataclass with all parsed and validated fields.
- `add_zone()` stores it in `flight_map.zones` dict (by name) and creates an empty
  adjacency list entry for it.
- `continue` → next line.

### 5.5 — Parsing Connection Lines (Lines 152–195)

```python
if cl_line.startswith("connection:"):
```

#### 5.5.1 — Regex Match (Lines 153–158)

```python
    match = self.LINK_PAT.match(cl_line)
    if not match:
        msg = "Invalid connection line syntax"
        self._err(f"{msg}: {cl_line}", ln)
    assert match is not None
    zone_a, zone_b, metaconn = match.groups()
    max_cap = 1
```

- Apply the connection regex. If it fails → error.
- Extract zone_a, zone_b, and optional metadata string.
- Default `max_cap` (max link capacity) = 1.

#### 5.5.2 — Connection Metadata (Lines 161–173)

```python
    if metaconn:
        data = self._parse_metadata(metaconn, ln)
        if "max_link_capacity" in data:
            try:
                max_cap = int(data['max_link_capacity'])
                if max_cap <= 0:
                    msg = "max_link_capacity must"
                    self._err(f"{msg} be positive integer", ln)
            except ValueError:
                msg = "max_link_capacity "
                self._err(f"{msg} must be an integer", ln)
```

- If there is metadata, parse it and look for `max_link_capacity`.
- Same validation pattern: must be a positive integer.

#### 5.5.3 — Zone Existence Check (Lines 175–178)

```python
    if zone_a not in flight_map.zones:
        self._err(f"Unknown zone '{zone_a}'", ln)
    if zone_b not in flight_map.zones:
        self._err(f"Unknown zone '{zone_b}'", ln)
```

- The subject says: *"Connections must link only previously defined zones."*
- If either zone name has not been defined yet → error.

#### 5.5.4 — Duplicate Connection Check (Lines 180–187)

```python
    if zone_a < zone_b:
        conn_key = (zone_a, zone_b)
    else:
        conn_key = (zone_b, zone_a)
    if conn_key in existing_connections:
        self._err(f"Duplicate conc: {zone_a} and {zone_b}", ln)
    existing_connections.add(conn_key)
```

- To detect duplicates, we **sort** the two zone names alphabetically and make a tuple.
  This way `("a", "b")` and `("b", "a")` produce the same key.
- The subject says: *"a-b and b-a are considered duplicates."*
- If we have already seen this connection → error.
- Otherwise, add it to the tracking set.

#### 5.5.5 — Creating and Adding the Connection (Lines 189–195)

```python
    new_conn = Connection(
        node_a=zone_a,
        node_b=zone_b,
        max_link_capacity=max_cap
    )
    flight_map.add_link(new_conn)
    continue
```

- Create a `Connection` dataclass with the two zone names and the capacity.
- `add_link()` stores it in the graph's link dictionary and updates **both** zones'
  adjacency lists (because connections are bidirectional).
- `continue` → next line.

### 5.6 — Catch-All Invalid Line (Line 196)

```python
self._err(f"Invalid line: {cl_line}", ln)
```

- If the line did not match `nb_drones:`, any hub type, or `connection:`, it is
  **invalid** → error. This catches typos or unexpected content.

### 5.7 — File Not Found (Lines 197–198)

```python
except OSError:
    self._err(f"File not found {file_path}", -1)
```

- If the `open()` call fails (file missing, permission error, etc.), we catch `OSError`
  and raise our own `ParseError`. The `-1` line number means "not related to any specific
  line in the file".

### 5.8 — Final Validation (Lines 200–203)

```python
if flight_map.start is None:
    self._err("Missing start_hub declaration.", -1)
if flight_map.end is None:
    self._err("Missing end_hub declaration", -1)
```

- After reading the entire file, we **must** have exactly one start and one end.
- If either is missing → error.

### 5.9 — Return the Result (Lines 205–210)

```python
return (
    flight_map.nb_drones,
    flight_map.start_zone,
    flight_map.end_zone,
    flight_map,
)
```

- Returns a tuple of four values:
  1. `nb_drones` — the number of drones.
  2. `start_zone` — the name of the start hub.
  3. `end_zone` — the name of the end hub.
  4. `flight_map` — the complete `Graph` object with all zones, connections, and
     adjacency lists ready for the pathfinder.

---

## 6 — `_err` Static Method (Lines 212–217)

```python
@staticmethod
def _err(msg: str, nl: int) -> None:
    """method raise Parse Error"""
    if nl == -1:
        raise ParseError(f"Error: {msg}")
    raise ParseError(f"Line: {nl}\nError: {msg}")
```

| Line | What it does |
|------|-------------|
| 212 | `@staticmethod` — This method does not use `self`. It is a utility. |
| 213 | Takes an error message and a line number. |
| 215–216 | If the line number is `-1`, this is a **global error** (not linked to any specific line). Print only the error message. |
| 217 | Otherwise, raise `ParseError` with the **line number AND the message**. This is exactly what the subject requires. |

---

## 7 — `__main__` Test Block (Lines 220–226)

```python
if __name__ == "__main__":
    parse = MapParser()
    line = "zone=riority color=green max_drones=2"
    try:
        parse.parse_file("test.txt")
    except ParseError as e:
        print(e)
```

- This block runs only when you call `python parser.py` directly (not when imported).
- It creates a `MapParser`, tries to parse a test file, and prints any parsing errors.
- This is just a **development/debug helper**; it is not part of the main application flow.

---

## Summary

The parser follows a strict, sequential pipeline:

```
Open file → Read line by line → Strip comments → Identify line type →
  ├── nb_drones   → Validate count, store it
  ├── hub/start/end → Regex extract → Validate coordinates, type, color, capacity → Create Zone → Add to Graph
  ├── connection  → Regex extract → Validate zones exist, no duplicates → Create Connection → Add to Graph  
  └── anything else → Raise error
→ Final check: start and end exist → Return (nb_drones, start, end, Graph)
```

Every validation error includes the **line number** and a **clear message**, exactly as
the subject requires.
