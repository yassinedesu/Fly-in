import re
import sys
import argparse
from enum import Enum
from pathlib import Path
from graph import Hub, Connection, Graph, ZoneType


class ParsingError(Exception):
    def __init__(self, line_n: int, message: str):
        self.line_n = line_n
        self.message = message
        super().__init__(self.message)

    def __str__(self) -> str:
        return f"Error on line {self.line_n}: {self.message}"


class Parser:
    """
    Main parser class responsible for validating
    and extracting drone network data.
    """

    class MetaKeys(Enum):
        ZONE = "zone"
        COLOR = "color"
        MAX_DRONE = "max_drones"
        MAX_LINK = "max_link_capacity"

    _ZONE_KEYS: set[str] = {"zone", "color", "max_drones"}
    _CONNECTION_KEYS: set[str] = {"max_link_capacity"}

    def __init__(self):
        self.graph = Graph()
        self.nb_drones_parsed = False
        self.start_hub_parsed = False
        self.end_hub_parsed = False
        self.defined_zones: set[str] = set()
        self.seen_connections: set[frozenset[str]] = set()
        self.is_first_line = True

    def pre_parse_line(self, line: str, line_n: int) -> None:
        """
        Perform a structural sanity check applied to every non-blank,
        non-comment line.
        """
        for ch in line:
            if ch == "\t" or (ord(ch) < 32):
                raise ParsingError(
                    line_n, f"Forbidden character {ch!r} in line: {line!r}"
                )

        if line.count(":") != 1:
            raise ParsingError(
                line_n,
                f"Line must contain exactly one ':' "
                f"(found {line.count(':')}): {line!r}",
            )

        after_colon = line.split(":", 1)[1].strip()
        if not after_colon:
            raise ParsingError(line_n, f"Empty content after ':': {line!r}")

        has_open = "[" in line
        has_close = "]" in line

        if has_open != has_close:
            raise ParsingError(
                line_n, f"Mismatched brackets in line: {line!r}"
            )

        if has_open:
            if line.count("[") != 1 or line.count("]") != 1:
                raise ParsingError(
                    line_n,
                    f"Only one metadata block allowed per line: {line!r}",
                )

            open_idx = line.index("[")
            close_idx = line.index("]")
            colon_idx = line.index(":")

            if open_idx > close_idx:
                raise ParsingError(
                    line_n,
                    f"Closing ']' appears before opening '[': {line!r}",
                )
            if open_idx <= colon_idx:
                raise ParsingError(
                    line_n,
                    f"Metadata block '[' must appear after ':': {line!r}",
                )

            trailing = line[close_idx + 1:].strip()
            if trailing:
                raise ParsingError(
                    line_n, f"Trailing content after ']': {line!r}"
                )

            inner = line[open_idx + 1:close_idx].strip()
            if not inner:
                raise ParsingError(
                    line_n, f"Empty metadata block '[]': {line!r}"
                )
            if "=" not in inner:
                raise ParsingError(
                    line_n,
                    f"Metadata block must contain 'key=value' pairs: "
                    f"{line!r}",
                )

            for token in inner.split():
                if token.count("=") != 1:
                    raise ParsingError(
                        line_n,
                        f"Invalid metadata token {token!r}: {line!r}",
                    )
                k, v = token.split("=", 1)
                if not k or not v:
                    raise ParsingError(
                        line_n,
                        f"Empty key or value in metadata token "
                        f"{token!r}: {line!r}",
                    )

    def parse_nb_drones(self, line: str, line_n: int) -> None:
        if self.nb_drones_parsed:
            raise ParsingError(line_n, "nb_drones already defined.")

        try:
            key, value = line.split(":", 1)
            if key.strip() != "nb_drones":
                raise ParsingError(
                    line_n, f"Invalid nb_drones format: {line!r}"
                )
            nb = int(value.strip())
            if nb <= 0:
                raise ParsingError(
                    line_n, f"nb_drones must be positive integer, got {nb}"
                )

            self.graph.drone_count = nb
            self.nb_drones_parsed = True
        except ValueError:
            raise ParsingError(
                line_n, f"Invalid nb_drones format: {line!r}"
            )

    def parse_metadata(
        self,
        metadata: str,
        line_n: int,
        connection: bool = False,
        ignore_max_drones: bool = False,
    ) -> dict[str, object]:
        if not metadata:
            return {}

        valid_keys = self._CONNECTION_KEYS if connection else self._ZONE_KEYS
        context = "connections" if connection else "zones"
        metadata_dict: dict[str, object] = {}

        for token in metadata.split():
            key, value = token.split("=", 1)

            if key == self.MetaKeys.MAX_DRONE.value and ignore_max_drones:
                continue
            if key in metadata_dict:
                raise ParsingError(line_n, f"Duplicate metadata key '{key}'")
            if not any(mk.value == key for mk in self.MetaKeys):
                raise ParsingError(line_n, f"Unknown metadata key '{key}'")
            if key not in valid_keys:
                raise ParsingError(
                    line_n,
                    f"Metadata key '{key}' is not valid for {context}",
                )

            if key == self.MetaKeys.ZONE.value:
                try:
                    value = ZoneType(value)
                except ValueError:
                    raise ParsingError(
                        line_n, f"Invalid zone type '{value}'"
                    )

            elif key in (
                self.MetaKeys.MAX_DRONE.value,
                self.MetaKeys.MAX_LINK.value,
            ):
                try:
                    int_val = int(value)
                    if int_val <= 0:
                        raise ValueError
                    value = int_val
                except ValueError:
                    raise ParsingError(
                        line_n,
                        f"Capacity '{key}' must be positive integer, "
                        f"got: {value!r}",
                    )

            elif key == self.MetaKeys.COLOR.value:
                if not value:
                    raise ParsingError(
                        line_n, "Color value cannot be empty"
                    )

        return metadata_dict

    def parse_zone(self, line: str, line_n: int) -> None:
        line_pattern = r"^(.*?)\s*:\s*(.*?)(?:\s*\[(.*?)\])?$"
        value_pattern = r"^(\S+)\s+(-?\d+)\s+(-?\d+)$"

        match = re.match(line_pattern, line)
        if not match:
            raise ParsingError(
                line_n, f"Invalid zone definition format: {line!r}"
            )

        key, value_str, metadata_str = match.groups()
        key = key.strip()
        value_str = value_str.strip()

        vm = re.match(value_pattern, value_str)
        if not vm:
            raise ParsingError(
                line_n,
                f"Invalid zone definition (expected '<name> <x> <y>'): "
                f"{line!r}",
            )

        name, x, y = vm.groups()

        if not name:
            raise ParsingError(line_n, "Zone name cannot be empty")
        if "-" in name:
            raise ParsingError(
                line_n, f"Zone name cannot contain dashes: '{name}'"
            )
        if name in self.defined_zones:
            raise ParsingError(line_n, f"Duplicate zone name '{name}'")

        try:
            x_int, y_int = int(x), int(y)
        except ValueError:
            raise ParsingError(line_n, f"Invalid coordinates in: {line!r}")

        is_start = key == "start_hub"
        is_end = key == "end_hub"

        if is_start:
            if self.start_hub_parsed:
                raise ParsingError(line_n, "start_hub already defined.")
            self.start_hub_parsed = True
        elif is_end:
            if self.end_hub_parsed:
                raise ParsingError(line_n, "end_hub already defined.")
            self.end_hub_parsed = True
        elif key != "hub":
            raise ParsingError(
                line_n, f"Unknown zone prefix '{key}': {line!r}"
            )

        meta = self.parse_metadata(
            metadata_str or "",
            line_n,
            connection=False,
            ignore_max_drones=(is_start or is_end),
        )

        hub = Hub(
            name=name,
            x=x_int,
            y=y_int,
            zone=meta.get(self.MetaKeys.ZONE.value, ZoneType.NORMAL),
            color=meta.get(self.MetaKeys.COLOR.value, None),
            max_drones=meta.get(self.MetaKeys.MAX_DRONE.value, 1),
            is_start=is_start,
            is_end=is_end,
        )

        self.defined_zones.add(name)
        self.graph.hubs[name] = hub
        self.graph.adj[name] = []

        if is_start:
            self.graph.start_hub = hub
        elif is_end:
            self.graph.end_hub = hub

    def parse_connection(self, line: str, line_n: int) -> None:
        line_pattern = (
            r"^connection\s*:\s*([^-\[\s]+)-([^-\[\s]+?)(?:\s*\[(.*?)\])?$"
        )
        match = re.match(line_pattern, line)
        if not match:
            raise ParsingError(
                line_n, f"Invalid connection format: {line!r}"
            )

        zone1, zone2, metadata_str = match.groups()
        zone1 = zone1.strip()
        zone2 = zone2.strip()

        if not zone1 or not zone2:
            raise ParsingError(
                line_n, f"Connection has empty zone name: {line!r}"
            )
        if zone1 == zone2:
            raise ParsingError(
                line_n, f"Connection cannot link zone to itself: {line!r}"
            )
        if (
            zone1 not in self.defined_zones
            or zone2 not in self.defined_zones
        ):
            raise ParsingError(
                line_n,
                f"Connection references undefined zone "
                f"'{zone1}' or '{zone2}'",
            )

        pair = frozenset({zone1, zone2})
        if pair in self.seen_connections:
            raise ParsingError(
                line_n, f"Duplicate connection: '{zone1}-{zone2}'"
            )
        self.seen_connections.add(pair)

        meta = self.parse_metadata(
            metadata_str or "", line_n, connection=True
        )
        capacity = meta.get(self.MetaKeys.MAX_LINK.value, 1)

        self.graph.adj[zone1].append(
            Connection(u=zone1, v=zone2, max_link_capacity=capacity)
        )
        self.graph.adj[zone2].append(
            Connection(u=zone2, v=zone1, max_link_capacity=capacity)
        )

    def parsing_caller(self, line: str, line_n: int) -> None:
        if line.startswith("nb_drones"):
            self.parse_nb_drones(line, line_n)
        elif (
            line.startswith("start_hub")
            or line.startswith("end_hub")
            or line.startswith("hub")
        ):
            self.parse_zone(line, line_n)
        elif line.startswith("connection"):
            self.parse_connection(line, line_n)
        else:
            raise ParsingError(line_n, f"Unknown line prefix in: {line!r}")

    def post_parse_validate(self) -> None:
        if not self.nb_drones_parsed:
            raise ParsingError(0, "Missing required field: 'nb_drones'")
        if not self.start_hub_parsed or not self.graph.start_hub:
            raise ParsingError(0, "Missing required field: 'start_hub'")
        if not self.end_hub_parsed or not self.graph.end_hub:
            raise ParsingError(0, "Missing required field: 'end_hub'")

    def parse_file(self, file_path: str | Path) -> Graph:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line_number, raw_line in enumerate(f, start=1):
                    line = raw_line.split("#", 1)[0].strip()
                    if not line:
                        continue

                    self.pre_parse_line(line, line_number)

                    if self.is_first_line:
                        if not line.startswith("nb_drones:"):
                            raise ParsingError(
                                line_number,
                                f"The first line must define nb_drones, "
                                f"found: {line!r}",
                            )
                        self.is_first_line = False

                    self.parsing_caller(line, line_number)

            self.post_parse_validate()
        except FileNotFoundError:
            print(f"Error: File '{file_path}' not found.")
            sys.exit(1)
        except ParsingError as e:
            print(e)
            sys.exit(1)
        except Exception as e:
            print(f"Unexpected error in '{file_path}': {e}")
            sys.exit(1)

        return self.graph


if __name__ == "__main__":
    cli_parser = argparse.ArgumentParser(
        description="Fly-in Drone Routing Parser"
    )
    cli_parser.add_argument(
        "map_file", type=str, help="Path to the map file"
    )
    cli_parser.add_argument(
        "--capacity-info",
        action="store_true",
        help="Display capacity info per turn",
    )
    args = cli_parser.parse_args()

    parser = Parser()
    graph = parser.parse_file(args.map_file)
    print(f"Loaded {graph.drone_count} drones.")
    print(f"Start: {graph.start_hub.name}, End: {graph.end_hub.name}")
    print(
        f"Hubs: {len(graph.hubs)}, "
        f"Connections: {len(parser.seen_connections)}"
    )
    if args.capacity_info:
        print("Capacity flag enabled.")
