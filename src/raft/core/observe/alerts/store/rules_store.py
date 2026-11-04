"""Durable ``host/alerts.yaml`` store."""

from pathlib import Path
from typing import Any, Optional

import yaml

from raft.core.core.config.paths.host_paths import HostPaths
from raft.core.core.errors.cta import OperatorError
from raft.core.core.gitops.cached_load import CachedYamlLoad

from ..catalogs import AlertCatalogs
from ..model.document import AlertRulesDocument
from ..registries import AlertRegistries
from .atomic import AtomicText


class AlertRulesStore:
    """Atomic YAML store for desired alert rules."""

    def __init__(
        self, home: Path, *, registries: Optional[AlertRegistries] = None
    ) -> None:
        self.home = home
        self.path = HostPaths(home).alerts()
        self._registries = registries or AlertCatalogs.default()
        self._yaml = CachedYamlLoad()

    def exists(self) -> bool:
        return self.path.is_file()

    def load(self) -> AlertRulesDocument:
        raw = self._yaml.mapping(self.path, label="host/alerts.yaml")
        if raw is None:
            return AlertRulesDocument.empty()
        return AlertRulesDocument.from_mapping(
            raw, registries=self._registries, path="host/alerts.yaml"
        )

    def load_raw(self) -> Any:
        raw = self._yaml.mapping(self.path, label="host/alerts.yaml")
        if raw is None:
            raise OperatorError(
                "host/alerts.yaml is missing.\n"
                "Fix: create the alert rules document under ~/.raft/host/alerts.yaml"
            )
        return raw

    def save(self, document: AlertRulesDocument) -> None:
        text = yaml.safe_dump(
            document.to_export(), sort_keys=False, default_flow_style=False
        )
        AtomicText.write(self.path, text, mode=0o600)
        self._yaml.clear()
