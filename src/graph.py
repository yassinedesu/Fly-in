from dataclasses import dataclass
from typing import Optional
from enum import Enum

class   ZoneType(Enum):
    NORMAL = "normal"
    BLOCKED = "blocked"
    RESTRICTED = "restricted"
    PRIORITY = "priority"



@dataclass
class   Connection:
    u: str
    v: str
    max_link_capacity: int = 1

@dataclass
class   Hub:
    name: str
    x: int
    y: int
    zone: str | None = "normal"
    color: str | None
    max_drones: int | None = 1
    is_start: bool
    is_end: bool

@dataclass
class   MapParse:
    nb_drones: int
    hub: object
    connection: object

