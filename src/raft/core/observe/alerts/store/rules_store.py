"""Durable alert rules.yaml store."""

from pathlib import Path
from typing import Any, Optional

import yaml

from raft.core.core.errors.cta import OperatorError

from ..catalogs import AlertCatalogs
from ..constants import ALERTS_STATE_DIR, RULES_NAME
from ..model.document import AlertRulesDocument
from ..registries import AlertRegistries
from .atomic import AtomicText


class AlertRulesStore:
    """Atomic YAML store for desired alert rules."""

    def __init__(
        self, home: Path, *, registries: Optional[AlertRegistries] = None
    ) -> None:
        self.home = home
        self.path = home / ALERTS_STATE_DIR / RULES_NAME
        self._registries = registries or AlertCatalogs.default()

    def exists(self) -> bool:
        return self.path.is_file()

    def load(self) -> AlertRulesDocument:
        if not self.path.is_file():
            return AlertRulesDocument.empty()
        raw = self.load_raw()
        return AlertRulesDocument.from_mapping(
            raw, registries=self._registries, path="host/alerts/rules.yaml"
        )

    def load_raw(self) -> Any:
        try:
            return yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            raise OperatorError(
                f"cannot read host/alerts/rules.yaml: {exc}.\n"
                f"Fix: repair the rules document or delete it"
            ) from exc

    def save(self, document: AlertRulesDocument) -> None:
        text = yaml.safe_dump(
            document.to_export(), sort_keys=False, default_flow_style=False
        )
        AtomicText.write(self.path, text, mode=0o600)
