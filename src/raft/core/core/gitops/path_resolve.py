"""Resolve flat GitOps doc paths under the data home (#317)."""

from pathlib import Path

from raft.core.core.config.paths.host_paths import HostPaths
from raft.core.core.errors.cta import OperatorError

from .doc_kind import GitopsDocKind


class GitopsPathResolve:
    """Map :class:`GitopsDocKind` to the on-disk path for one data home."""

    def __init__(self, home: Path) -> None:
        self._host = HostPaths(home)

    def path(self, kind: GitopsDocKind) -> Path:
        if kind is GitopsDocKind.SETTINGS:
            return self._host.settings()
        if kind is GitopsDocKind.FIREWALL:
            return self._host.firewall()
        if kind is GitopsDocKind.ALERTS:
            return self._host.alerts()
        if kind is GitopsDocKind.NOTIFICATIONS:
            return self._host.notifications()
        if kind is GitopsDocKind.RBAC:
            return self._host.rbac()
        raise OperatorError(
            f"unknown GitOps document kind {kind!r}.\n"
            f"Fix: use one of settings|firewall|alerts|notifications|rbac",
            has_fix=False,
        )
