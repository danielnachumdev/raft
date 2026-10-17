"""Shared CRUD service for alert rules (CLI + serve)."""

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from raft.core.core.config.settings import SettingsLoader
from raft.core.core.errors.cta import OperatorError
from raft.core.platform.locking.alerts_lock import AlertsLock

from ..catalogs import AlertCatalogs
from ..model.document import AlertRulesDocument
from ..model.issues import ValidationReport
from ..model.rule import AlertRule
from ..model.rule_parser import AlertRuleParser
from ..registries import AlertRegistries
from ..store.rules_store import AlertRulesStore


@dataclass
class ApplySummary:
    created: List[str]
    updated: List[str]
    unchanged: List[str]
    deleted: List[str]

    def to_public(self) -> Dict[str, Any]:
        return {
            "created": list(self.created),
            "updated": list(self.updated),
            "unchanged": list(self.unchanged),
            "deleted": list(self.deleted),
        }


class RuleConflict(OperatorError):
    """Raised when creating a rule whose id already exists."""


class AlertRulesService:
    """Only writer of rules.yaml; holds alerts.lock on mutative ops."""

    def __init__(
        self, home: Path, *, registries: Optional[AlertRegistries] = None
    ) -> None:
        self._home = home
        self._regs = registries or AlertCatalogs.default()
        self._store = AlertRulesStore(home, registries=self._regs)
        self._parser = AlertRuleParser(self._regs)

    def document(self) -> AlertRulesDocument:
        return self._store.load()

    def get(self, rule_id: str) -> AlertRule:
        rule = self.document().get(rule_id)
        if rule is None:
            raise KeyError(rule_id)
        return rule

    def validate_document(self, raw: Any) -> ValidationReport:
        report = ValidationReport()
        try:
            AlertRulesDocument.from_mapping(raw, registries=self._regs)
        except OperatorError as exc:
            report.add_error("document", str(exc).split("\n")[0])
            return report
        self._channel_warnings(raw, report)
        return report

    def validate_rule(self, raw: Any) -> ValidationReport:
        report = self._parser.validate(raw, path="rule")
        self._warn_channels_on_rule(raw if isinstance(raw, Mapping) else {}, report)
        return report

    def create(self, raw: Mapping[str, Any]) -> AlertRule:
        with AlertsLock(self._home):
            doc = self._store.load()
            rule = self._parser.parse(raw, path="rule")
            self._require_channels(rule)
            if doc.get(rule.id) is not None:
                raise RuleConflict(
                    f"alert rule id {rule.id!r} already exists.\n"
                    f"Fix: choose a new id or PUT /api/alerts/rules/{rule.id}"
                )
            new_doc = AlertRulesDocument(doc.version, doc.rules + (rule,))
            self._store.save(new_doc)
            return rule

    def replace(self, rule_id: str, raw: Mapping[str, Any]) -> AlertRule:
        with AlertsLock(self._home):
            doc = self._store.load()
            if doc.get(rule_id) is None:
                raise KeyError(rule_id)
            body = dict(raw)
            body.setdefault("id", rule_id)
            if body.get("id") != rule_id:
                raise OperatorError(
                    f"body id {body.get('id')!r} does not match path {rule_id!r}.\n"
                    f"Fix: omit id or set it equal to the path"
                )
            rule = self._parser.parse(body, path="rule")
            self._require_channels(rule)
            rules = tuple(rule if r.id == rule_id else r for r in doc.rules)
            self._store.save(AlertRulesDocument(doc.version, rules))
            return rule

    def set_enabled(self, rule_id: str, enabled: bool) -> AlertRule:
        with AlertsLock(self._home):
            doc = self._store.load()
            current = doc.get(rule_id)
            if current is None:
                raise KeyError(rule_id)
            updated = replace(current, enabled=enabled)
            rules = tuple(updated if r.id == rule_id else r for r in doc.rules)
            self._store.save(AlertRulesDocument(doc.version, rules))
            return updated

    def delete(self, rule_id: str) -> None:
        with AlertsLock(self._home):
            doc = self._store.load()
            if doc.get(rule_id) is None:
                raise KeyError(rule_id)
            rules = tuple(r for r in doc.rules if r.id != rule_id)
            self._store.save(AlertRulesDocument(doc.version, rules))

    def apply_document(self, raw: Any, *, prune: bool) -> ApplySummary:
        with AlertsLock(self._home):
            incoming = AlertRulesDocument.from_mapping(raw, registries=self._regs)
            for rule in incoming.rules:
                self._require_channels(rule)
            summary, merged = self._merge(incoming, prune=prune)
            self._store.save(AlertRulesDocument(incoming.version, tuple(merged)))
            return summary

    def _merge(
        self, incoming: AlertRulesDocument, *, prune: bool
    ) -> Tuple[ApplySummary, List[AlertRule]]:
        current = self._store.load()
        by_id = {r.id: r for r in current.rules}
        created, updated, unchanged = [], [], []
        merged: List[AlertRule] = []
        seen = set()
        for rule in incoming.rules:
            seen.add(rule.id)
            self._upsert(rule, by_id, created, updated, unchanged, merged)
        deleted = self._prune_or_keep(current, seen, merged, prune=prune)
        return ApplySummary(created, updated, unchanged, deleted), merged

    @staticmethod
    def _upsert(rule, by_id, created, updated, unchanged, merged) -> None:
        prev = by_id.get(rule.id)
        if prev is None:
            created.append(rule.id)
            merged.append(rule)
        elif prev.to_export() == rule.to_export():
            unchanged.append(rule.id)
            merged.append(prev)
        else:
            updated.append(rule.id)
            merged.append(rule)

    @staticmethod
    def _prune_or_keep(current, seen, merged, *, prune: bool) -> List[str]:
        deleted: List[str] = []
        for rule in current.rules:
            if rule.id in seen:
                continue
            if prune:
                deleted.append(rule.id)
            else:
                merged.append(rule)
        return deleted

    def export_document(self) -> Dict[str, Any]:
        return self._store.load().to_export()

    def _require_channels(self, rule: AlertRule) -> None:
        if not rule.channel_ids:
            return
        config = SettingsLoader().load(self._home).notifications
        known = {c.id for c in config.channels}
        missing = [i for i in rule.channel_ids if i not in known]
        if missing:
            raise OperatorError(
                f"unknown channelIds: {', '.join(missing)}.\n"
                f"Fix: create the channels under notifications: or remove them"
            )

    def _channel_warnings(self, raw: Any, report: ValidationReport) -> None:
        if not isinstance(raw, Mapping):
            return
        for i, item in enumerate(raw.get("rules") or []):
            if isinstance(item, Mapping):
                self._warn_channels_on_rule(item, report, path=f"rules[{i}]")

    def _warn_channels_on_rule(
        self, raw: Mapping[str, Any], report: ValidationReport, path: str = "rule"
    ) -> None:
        ids = raw.get("channelIds") or []
        if not ids:
            return
        config = SettingsLoader().load(self._home).notifications
        if not config.enabled:
            report.add_warning(
                f"{path}.channelIds",
                "notifications.enabled is false; alerts will not deliver",
            )
