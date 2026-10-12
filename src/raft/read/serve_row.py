"""One presentation row for serve status tables / service detail."""

from dataclasses import dataclass, field
from typing import Tuple


@dataclass(frozen=True)
class ServeRow:
    service: str
    name: str
    role: str
    group: str
    status: str
    cpu: str
    memory: str
    started: str
    uptime: str
    external_urls: Tuple[str, ...] = field(default_factory=tuple)
    depends_on: Tuple[str, ...] = field(default_factory=tuple)
