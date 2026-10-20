"""Persist dismissed firewall recommendation ids under state/firewall/."""

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

FIREWALL_STATE_DIR = Path("host") / "firewall"
DISMISSALS_NAME = "dismissed-recommendations.json"


class FirewallDismissalStore:
    """JSON set of recommendation ids the operator dismissed."""

    def __init__(self, home: Path) -> None:
        self.root = home / FIREWALL_STATE_DIR
        self.path = self.root / DISMISSALS_NAME
        self._lock = threading.Lock()

    def list_ids(self) -> frozenset[str]:
        with self._lock:
            return self._load()

    def dismiss(self, recommendation_id: str) -> frozenset[str]:
        with self._lock:
            current = set(self._load())
            text_id = recommendation_id.strip()
            if text_id:
                current.add(text_id)
            self.root.mkdir(parents=True, exist_ok=True)
            payload = {"dismissed": sorted(current)}
            self._atomic_write(self.path, json.dumps(payload, indent=2) + "\n")
            os.chmod(self.path, 0o600)
            return frozenset(current)

    def _load(self) -> frozenset[str]:
        if not self.path.is_file():
            return frozenset()
        raw = self._read(self.path)
        if not isinstance(raw, dict):
            return frozenset()
        items = raw.get("dismissed")
        if not isinstance(items, list):
            return frozenset()
        return frozenset(str(item).strip() for item in items if str(item).strip())

    def _atomic_write(self, path: Path, text: str) -> None:
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(text)
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    @staticmethod
    def _read(path: Path) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
