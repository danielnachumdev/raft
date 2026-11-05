"""Atomic YAML store for ``host/rbac.yaml``."""

import os
import tempfile
import threading
from pathlib import Path
from typing import Any, Optional

import yaml

from raft.core.core.config.paths.host_paths import HostPaths
from raft.core.core.gitops.cached_load import CachedYamlLoad
from raft.core.core.rbac.document import RbacDocument


class RbacStore:
    """Persist RBAC document under the host data home."""

    def __init__(self, home: Path) -> None:
        self.home = home
        self.path = HostPaths(home).rbac()
        self._lock = threading.Lock()
        self._yaml = CachedYamlLoad()

    def exists(self) -> bool:
        return self.path.is_file()

    def load(self) -> Optional[RbacDocument]:
        with self._lock:
            raw = self._yaml.mapping(self.path, label="host/rbac.yaml")
            if raw is None:
                return None
            return RbacDocument.from_mapping(raw, path="host/rbac.yaml")

    def save(self, document: RbacDocument) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            text = yaml.safe_dump(
                document.to_export(),
                sort_keys=False,
                default_flow_style=False,
            )
            self._atomic_write(self.path, text)
            os.chmod(self.path, 0o600)
            self._yaml.clear()

    def _atomic_write(self, path: Path, text: str) -> None:
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(text)
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
