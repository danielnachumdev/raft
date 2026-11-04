"""Cached settings.yaml loader (#317)."""

from pathlib import Path

from raft.core.core.config.settings.loader import SettingsLoader
from raft.core.core.config.settings.types import RaftConfig
from raft.core.core.gitops.cached_load import CachedYamlLoad
from raft.core.core.gitops.doc_kind import GitopsDocKind
from raft.core.core.gitops.path_resolve import GitopsPathResolve


class SettingsGitops:
    """Load ``host/settings.yaml`` via in-process YAML cache."""

    def __init__(self, home: Path) -> None:
        self._home = home
        self._path = GitopsPathResolve(home).path(GitopsDocKind.SETTINGS)
        self._yaml = CachedYamlLoad()
        self._loader = SettingsLoader()

    def load(self) -> RaftConfig:
        raw = self._yaml.mapping(self._path, label="host/settings.yaml")
        return self._loader.from_raw(raw)

    def clear_cache(self) -> None:
        self._yaml.clear()
