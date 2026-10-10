"""Resolve ``spec.envFile`` for Compose and docker CLI under the data home."""

from __future__ import annotations

from pathlib import Path
from typing import Optional


class ComposeEnvFilePath:
    """Map env files under the data home so host CLI and controller agree.

    Compose ``env_file`` and ``docker --env-file`` are read by the local CLI,
    not the Docker daemon. Host-absolute paths under ``~/.raft`` therefore
    fail when wake/heal/cutover run inside ``raft-controller``
    (``RAFT_DATA_HOME=/raft``).
    """

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def for_compose(self, env_file: str) -> str:
        """Project-relative path when under data home; otherwise unchanged."""
        rel = self._relative_to_root(env_file)
        if rel is not None:
            return rel.as_posix()
        remapped = self._remap_host_suffix(Path(env_file))
        if remapped is not None:
            return remapped.as_posix()
        return env_file

    def for_runtime(self, env_file: str) -> str:
        """Filesystem path readable by docker CLI in this process."""
        path = Path(env_file)
        if not path.is_absolute():
            return str(self._root / path)
        rel = self._absolute_under_root(path)
        if rel is not None:
            return str(self._root / rel)
        remapped = self._remap_host_suffix(path)
        if remapped is not None:
            return str(self._root / remapped)
        return env_file

    def _relative_to_root(self, env_file: str) -> Optional[Path]:
        path = Path(env_file)
        if not path.is_absolute():
            return path
        return self._absolute_under_root(path)

    def _absolute_under_root(self, absolute: Path) -> Optional[Path]:
        try:
            return absolute.resolve().relative_to(self._root)
        except ValueError:
            return None

    def _remap_host_suffix(self, absolute: Path) -> Optional[Path]:
        parts = absolute.parts
        for i in range(1, len(parts)):
            rel = Path(*parts[i:])
            if (self._root / rel).is_file():
                return rel
        return None
