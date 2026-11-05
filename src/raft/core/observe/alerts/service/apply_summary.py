"""Summary of an alert-rules document apply."""

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class ApplySummary:
    created: List[str]
    updated: List[str]
    unchanged: List[str]
    deleted: List[str]

    def to_public(self) -> Dict[str, Any]:
        return {
            "created": list(self.created),
            "updated": list(self.updated),
            "unchanged": list(self.unchanged),
            "deleted": list(self.deleted),
        }
