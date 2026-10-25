"""Persist read inbox item ids under ``host/inbox/read-state.json``."""

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any, Iterable

from raft.core.core.config.paths.constants import HOST_INBOX_DIR

READ_STATE_NAME = "read-state.json"


class InboxReadStore:
    """JSON set of inbox item ids the operator has marked read."""

    def __init__(self, home: Path) -> None:
        self.root = home / HOST_INBOX_DIR
        self.path = self.root / READ_STATE_NAME
        self._lock = threading.Lock()

    def list_read_ids(self) -> frozenset[str]:
        with self._lock:
            return self._load()

    def mark_read(self, item_ids: Iterable[str]) -> frozenset[str]:
        with self._lock:
            current = set(self._load())
            for raw in item_ids:
                text = str(raw).strip()
                if text:
                    current.add(text)
            return self._persist(current)

    def mark_unread(self, item_ids: Iterable[str]) -> frozenset[str]:
        with self._lock:
            current = set(self._load())
            for raw in item_ids:
                text = str(raw).strip()
                if text:
                    current.discard(text)
            return self._persist(current)

    def prune_to(self, live_ids: Iterable[str]) -> frozenset[str]:
        """Drop read markers for items no longer in the derived feed."""
        with self._lock:
            live = {str(item).strip() for item in live_ids if str(item).strip()}
            current = {item for item in self._load() if item in live}
            return self._persist(current)

    def _persist(self, current: set[str]) -> frozenset[str]:
        self.root.mkdir(parents=True, exist_ok=True)
        payload = {"read": sorted(current)}
        self._atomic_write(self.path, json.dumps(payload, indent=2) + "\n")
        os.chmod(self.path, 0o600)
        return frozenset(current)

    def _load(self) -> frozenset[str]:
        if not self.path.is_file():
            return frozenset()
        raw = self._read(self.path)
        if not isinstance(raw, dict):
            return frozenset()
        items = raw.get("read")
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
