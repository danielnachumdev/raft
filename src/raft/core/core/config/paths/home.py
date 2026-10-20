"""Resolve the durable operator home under ``~/.raft/``."""

import os
from pathlib import Path
from typing import Optional

from raft.core.core.errors.cta import OperatorError
from .constants import DATA_HOME_ENV, SETTINGS_REL


class RaftHome:
    """Resolve ``RAFT_DATA_HOME`` or ``~/.raft`` and the settings file path."""

    def resolve(self) -> Path:
        override = os.environ.get(DATA_HOME_ENV)
        if override is not None:
            return self._resolve_override(override)
        return (Path.home() / ".raft").resolve()

    def settings_path(self, home: Optional[Path] = None) -> Path:
        return (home or self.resolve()) / SETTINGS_REL

    @staticmethod
    def _resolve_override(override: str) -> Path:
        if not override.strip():
            raise OperatorError(
                f"{DATA_HOME_ENV} is set but empty.\n"
                f"Fix: unset {DATA_HOME_ENV} or set it to an absolute path (e.g. ~/.raft)"
            )
        return Path(override).expanduser().resolve()
