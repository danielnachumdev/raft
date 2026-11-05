"""Cached settings.yaml loader (#317)."""

from pathlib import Path

from raft.core.core.config.settings.loader import SettingsLoader
from raft.core.core.config.settings.types import RaftConfig
from raft.core.core.gitops.notifications_gitops import NotificationsGitops


class SettingsGitops:
    """Load ``host/settings.yaml`` (+ flat notifications) via cached loaders."""

    def __init__(self, home: Path) -> None:
        self._home = home
        self._loader = SettingsLoader()

    def load(self) -> RaftConfig:
        return self._loader.load(self._home)

    def clear_cache(self) -> None:
        self._loader.clear_cache()
        NotificationsGitops(self._home).clear_cache()
