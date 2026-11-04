"""Cached alerts.yaml loader (#317)."""

from pathlib import Path
from typing import Optional

from raft.core.core.gitops.cached_load import CachedYamlLoad
from raft.core.core.gitops.doc_kind import GitopsDocKind
from raft.core.core.gitops.path_resolve import GitopsPathResolve
from raft.core.observe.alerts.catalogs import AlertCatalogs
from raft.core.observe.alerts.model.document import AlertRulesDocument
from raft.core.observe.alerts.registries import AlertRegistries


class AlertsGitops:
    """Load ``host/alerts.yaml`` via in-process YAML cache."""

    def __init__(
        self, home: Path, *, registries: Optional[AlertRegistries] = None
    ) -> None:
        self._path = GitopsPathResolve(home).path(GitopsDocKind.ALERTS)
        self._yaml = CachedYamlLoad()
        self._registries = registries or AlertCatalogs.default()

    def load(self) -> AlertRulesDocument:
        raw = self._yaml.mapping(self._path, label="host/alerts.yaml")
        if raw is None:
            return AlertRulesDocument.empty()
        return AlertRulesDocument.from_mapping(
            raw, registries=self._registries, path="host/alerts.yaml"
        )

    def clear_cache(self) -> None:
        self._yaml.clear()
