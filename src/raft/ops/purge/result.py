"""Space reclaimed by one ``raft purge`` run."""

from dataclasses import dataclass
from typing import Any, Dict

from ..status.formatters import StatusFormatters


@dataclass(frozen=True)
class PurgeResult:
    """Space reclaimed by one purge run."""

    reclaimed_bytes: int
    image_bytes: int
    builder_bytes: int

    @property
    def reclaimed_human(self) -> str:
        return StatusFormatters.bytes(self.reclaimed_bytes)

    def as_api(self) -> Dict[str, Any]:
        return {
            "ok": True,
            "action": "purge",
            "reclaimed_bytes": self.reclaimed_bytes,
            "reclaimed_human": self.reclaimed_human,
            "images_bytes": self.image_bytes,
            "builder_bytes": self.builder_bytes,
        }
