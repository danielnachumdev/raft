"""Persistent per-app ACL policies under ``~/.raft/state/acl/apps/``."""

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

from raft.core.core.models.acl_policy import AclPolicy

ACL_STATE_DIR = Path("state") / "acl" / "apps"


class AppAclStore:
    """Read/write per-app ACL JSON (serve CRUD; render consumes)."""

    def __init__(self, home: Path) -> None:
        self.home = home
        self.root = home / ACL_STATE_DIR
        self._lock = threading.Lock()

    def ensure_dirs(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, name: str) -> Path:
        return self.root / f"{name}.json"

    def load(self, name: str) -> AclPolicy:
        with self._lock:
            return self._load_unlocked(name)

    def save(self, name: str, policy: AclPolicy) -> None:
        with self._lock:
            self.ensure_dirs()
            if not policy.is_active() and policy.mode == "off":
                self._delete_unlocked(name)
                return
            self._write_unlocked(name, policy.to_public())

    def delete(self, name: str) -> None:
        with self._lock:
            self._delete_unlocked(name)

    def list_names(self) -> list[str]:
        self.ensure_dirs()
        return sorted(path.stem for path in self.root.glob("*.json"))

    def _load_unlocked(self, name: str) -> AclPolicy:
        path = self.path_for(name)
        if not path.is_file():
            return AclPolicy()
        raw = self._read_json(path)
        return AclPolicy.from_mapping(raw, path=f"state/acl/apps/{name}.json")

    def _write_unlocked(self, name: str, payload: dict[str, Any]) -> None:
        path = self.path_for(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(data)
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def _delete_unlocked(self, name: str) -> None:
        path = self.path_for(name)
        if path.is_file():
            path.unlink()

    @staticmethod
    def _read_json(path: Path) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
