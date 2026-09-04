from dataclasses import dataclass, field
from enum import Enum

class ZoneType(Enum):
    NORMAL = "normal"
    BLOCKED = "blocked"
    RESTRICTED = "restricted"
    PRIORITY = "priority"

@dataclass
class Connection:
    u: str
    v: str
    max_link_capacity: int = 1

@dataclass
class Hub:
    name: str
    x: int
    y: int
    zone: ZoneType = ZoneType.NORMAL
    color: str | None = None
    max_drones: int = 1
    is_start: bool = False
    is_end: bool = False

@dataclass
class Graph:
    drone_count: int = 0
    hubs: dict[str, Hub] = field(default_factory=dict)
    adj: dict[str, list[Connection]] = field(default_factory=dict)
    start_hub: Hub | None = None
    end_hub: Hub | None = None