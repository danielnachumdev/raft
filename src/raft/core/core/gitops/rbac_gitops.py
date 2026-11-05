"""Cached rbac.yaml loader (#317)."""

from pathlib import Path

from raft.core.core.gitops.cached_load import CachedYamlLoad
from raft.core.core.gitops.doc_kind import GitopsDocKind
from raft.core.core.gitops.path_resolve import GitopsPathResolve
from raft.core.core.rbac.document import RbacDocument


class RbacGitops:
    """Load ``host/rbac.yaml`` via in-process YAML cache."""

    def __init__(self, home: Path) -> None:
        self._path = GitopsPathResolve(home).path(GitopsDocKind.RBAC)
        self._yaml = CachedYamlLoad()

    def path(self) -> Path:
        return self._path

    def load(self) -> RbacDocument:
        raw = self._yaml.mapping(self._path, label="host/rbac.yaml")
        if raw is None:
            return RbacDocument.empty()
        return RbacDocument.from_mapping(raw, path="host/rbac.yaml")

    def clear_cache(self) -> None:
        self._yaml.clear()

