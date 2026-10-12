"""Runtime + stats row for one Compose service container."""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class ContainerRuntimeRow:
    """Runtime + stats for one Compose service container."""

    container_id: str
    status: str
    health: str
    started_at: str
    memory_bytes: Optional[int]
    stats: Optional[Dict[str, Any]]
    restart_count: int = 0
    oom_killed: bool = False
    finished_at: str = ""
    exit_code: Optional[int] = None
