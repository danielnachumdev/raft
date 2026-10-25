"""Persist dismissed recommendation ids under a host state directory."""

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any, Union

DISMISSALS_NAME = "dismissed-recommendations.json"
FIREWALL_STATE_DIR = Path("host") / "firewall"
ALERTS_STATE_DIR = Path("host") / "alerts"


class RecommendationDismissalStore:
    """JSON set of recommendation ids the operator dismissed."""

    def __init__(self, home: Path, state_dir: Union[Path, str]) -> None:
        self.root = home / Path(state_dir)
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


class FirewallDismissalStore(RecommendationDismissalStore):
    """Dismissals under ``host/firewall/dismissed-recommendations.json``."""

    def __init__(self, home: Path) -> None:
        super().__init__(home, FIREWALL_STATE_DIR)


class AlertDismissalStore(RecommendationDismissalStore):
    """Dismissals under ``host/alerts/dismissed-recommendations.json``."""

    def __init__(self, home: Path) -> None:
        super().__init__(home, ALERTS_STATE_DIR)
