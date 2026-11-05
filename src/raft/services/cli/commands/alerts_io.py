"""Load alert rule documents from host path or operator files."""

from pathlib import Path
from typing import Any, List, Optional

import yaml

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.stack import Stack
from raft.core.observe.alerts.catalogs import AlertCatalogs
from raft.core.observe.alerts.model.document import AlertRulesDocument
from raft.core.observe.alerts.model.rule import AlertRule
from raft.core.observe.alerts.service import AlertRulesService


class AlertsCliIo:
    """Read YAML for ``raft alerts`` validate / dry-run / apply / export."""

    def __init__(self, stack: Stack, *, service: AlertRulesService) -> None:
        self._stack = stack
        self._service = service

    def load_raw(self, file: Optional[str]) -> Any:
        if file:
            return self.read_file(file)
        path = self._stack.root / "host" / "alerts.yaml"
        if not path.is_file():
            return {"version": 1, "rules": []}
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    def dry_run_rules(
        self,
        *,
        rule_id: Optional[str],
        file: Optional[str],
        rule: Optional[str],
    ) -> List[AlertRule]:
        if file:
            return self._dry_run_from_file(file, rule)
        return self._dry_run_by_id(rule_id)

    def _dry_run_from_file(
        self, file: str, rule: Optional[str]
    ) -> List[AlertRule]:
        raw = self.read_file(file)
        doc = AlertRulesDocument.from_mapping(
            raw, registries=AlertCatalogs.default()
        )
        if not rule:
            return list(doc.rules)
        found = doc.get(rule)
        if found is None:
            raise OperatorError(
                f"rule {rule!r} not in file.\nFix: check the file ids"
            )
        return [found]

    def _dry_run_by_id(self, rule_id: Optional[str]) -> List[AlertRule]:
        if not rule_id:
            raise OperatorError(
                "rule id or --file is required.\nFix: raft alerts dry-run <id>"
            )
        try:
            return [self._service.get(rule_id)]
        except KeyError as exc:
            raise OperatorError(
                f"unknown alert rule {rule_id!r}.\nFix: raft alerts list"
            ) from exc

    @staticmethod
    def read_file(file: str) -> Any:
        path = Path(file)
        try:
            return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise OperatorError(
                f"cannot read {file}: {exc}.\nFix: provide a valid YAML file"
            ) from exc
