"""Persistent ordered firewall document under ``~/.raft/state/firewall/``."""

import os
import tempfile
import threading
from pathlib import Path
from typing import Any, Optional

import yaml

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.firewall import FirewallDocument

FIREWALL_STATE_DIR = Path("host") / "firewall"
FIREWALL_RULES_NAME = "rules.yaml"


class FirewallStore:
    """Atomic YAML store for the ordered firewall table."""

    def __init__(self, home: Path) -> None:
        self.home = home
        self.root = home / FIREWALL_STATE_DIR
        self.path = self.root / FIREWALL_RULES_NAME
        self._lock = threading.Lock()

    def exists(self) -> bool:
        return self.path.is_file()

    def load(self) -> Optional[FirewallDocument]:
        with self._lock:
            if not self.path.is_file():
                return None
            raw = self._read_yaml(self.path)
            return FirewallDocument.from_mapping(
                raw, path="host/firewall/rules.yaml", source="firewall"
            )

    def save(self, document: FirewallDocument) -> None:
        with self._lock:
            self.root.mkdir(parents=True, exist_ok=True)
            payload = document.to_export()
            text = yaml.safe_dump(payload, sort_keys=False, default_flow_style=False)
            self._atomic_write(self.path, text)
            os.chmod(self.path, 0o600)

    def delete(self) -> None:
        with self._lock:
            if self.path.is_file():
                self.path.unlink()

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
    def _read_yaml(path: Path) -> Any:
        try:
            return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise OperatorError(
                f"cannot read host/firewall/rules.yaml: {exc}.\n"
                f"Fix: repair the firewall document or delete it to remigrate",
                has_fix=False,
            ) from exc
