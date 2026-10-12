"""Parse ``/activity|wake/<name>`` request paths."""

from typing import Optional, Tuple
from urllib.parse import urlparse


class WakeHttpPath:
    """Parse ``/activity|wake/<name>`` request paths."""

    _ACTIONS = frozenset({"activity", "wake"})

    def parse(self, path: str) -> Tuple[Optional[str], Optional[str]]:
        parts = [p for p in urlparse(path).path.split("/") if p]
        if len(parts) != 2:
            return None, None
        action, name = parts[0], parts[1]
        if action not in self._ACTIONS:
            return None, None
        return action, name
