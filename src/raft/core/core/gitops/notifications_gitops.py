"""Cached notifications.yaml loader (#317)."""

from pathlib import Path

from raft.core.core.gitops.cached_load import CachedYamlLoad
from raft.core.core.gitops.doc_kind import GitopsDocKind
from raft.core.core.gitops.notifications_document import NotificationsDocument
from raft.core.core.gitops.path_resolve import GitopsPathResolve


class NotificationsGitops:
    """Load ``host/notifications.yaml`` via in-process YAML cache."""

    def __init__(self, home: Path) -> None:
        self._path = GitopsPathResolve(home).path(GitopsDocKind.NOTIFICATIONS)
        self._yaml = CachedYamlLoad()

    def load(self) -> NotificationsDocument:
        raw = self._yaml.mapping(self._path, label="host/notifications.yaml")
        if raw is None:
            return NotificationsDocument.empty()
        return NotificationsDocument.from_mapping(
            raw, path="host/notifications.yaml"
        )

    def clear_cache(self) -> None:
        self._yaml.clear()
