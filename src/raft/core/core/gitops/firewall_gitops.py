"""Cached firewall.yaml loader (#317)."""

from pathlib import Path

from raft.core.core.gitops.cached_load import CachedYamlLoad
from raft.core.core.gitops.doc_kind import GitopsDocKind
from raft.core.core.gitops.path_resolve import GitopsPathResolve
from raft.core.core.models.firewall import FirewallDocument


class FirewallGitops:
    """Load ``host/firewall.yaml`` via in-process YAML cache."""

    def __init__(self, home: Path) -> None:
        self._path = GitopsPathResolve(home).path(GitopsDocKind.FIREWALL)
        self._yaml = CachedYamlLoad()

    def load(self) -> FirewallDocument:
        raw = self._yaml.mapping(self._path, label="host/firewall.yaml")
        if raw is None:
            return FirewallDocument()
        return FirewallDocument.from_mapping(
            raw, path="host/firewall.yaml", source="firewall"
        )

    def clear_cache(self) -> None:
        self._yaml.clear()
