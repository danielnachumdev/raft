"""Fire component: ``raft alerts …``."""

from pathlib import Path
from typing import Any, Optional

import yaml

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.stack import Stack
from raft.core.observe.alerts import AlertEngine, AlertRulesService, AlertStatusView
from raft.core.observe.alerts.catalogs import AlertCatalogs
from raft.core.observe.alerts.model.document import AlertRulesDocument
from raft.core.observe.alerts.service.tester import AlertTester
from raft.core.observe.notify.delivery_status import DeliveryStatus

from .alerts_output import AlertsCliOutput


class AlertsCLI:
    """Manage alert rules under ``host/alerts/rules.yaml``.

    Primer: each rule has a catalog ``signal`` (e.g. metrics.http),
    ``for`` (sustain before fire), ``cooldown`` (silence before re-notify),
    and ``channelIds`` (omit / empty = every enabled notification channel).
    The controller evaluates rules under ``host/alerts/``; if status is
    stale, run ``raft doctor`` then ``raft up`` (controller needs the mount).
    """

    def __init__(self, stack: Stack) -> None:
        self._stack = stack
        self._out = AlertsCliOutput()
        self._service = AlertRulesService(stack.root)
        self._engine = AlertEngine(stack.root)

    def list(self, json: bool = False) -> None:
        """List alert rules with runtime state."""
        doc = self._service.document()
        status = AlertStatusView(self._stack.root).build()
        rows = []
        for rule in doc.rules:
            state = (status.get("rules") or {}).get(rule.id, {}).get("state", "ok")
            rows.append(
                {
                    "id": rule.id,
                    "enabled": rule.enabled,
                    "severity": rule.severity.value,
                    "state": state,
                    "condition": self._summarize(rule.condition.to_export()),
                }
            )
        if json:
            self._out.say_json({"rules": [r.to_public() for r in doc.rules], "status": status})
            return
        self._out.list_table(rows)

    def show(self, rule_id: str, json: bool = False) -> None:
        """Show one rule and its runtime instances."""
        try:
            rule = self._service.get(rule_id)
        except KeyError as exc:
            raise OperatorError(
                f"unknown alert rule {rule_id!r}.\nFix: raft alerts list"
            ) from exc
        status = AlertStatusView(self._stack.root).build()
        instances = [
            i for i in status.get("instances") or [] if i.get("ruleId") == rule_id
        ]
        payload = {"rule": rule.to_export(), "instances": instances}
        if json:
            self._out.say_json(payload)
            return
        self._out.say_yaml(payload)

    def validate(self, file: Optional[str] = None) -> None:
        """Validate rules.yaml or an external file."""
        raw = self._load_raw(file)
        report = self._service.validate_document(raw)
        public = report.to_public()
        rules = raw.get("rules") if isinstance(raw, dict) else []
        public["ruleCount"] = len(rules) if isinstance(rules, list) else 0
        self._out.print_validation(public)
        if not report.ok:
            raise SystemExit(1)

    def dry_run(
        self,
        rule_id: Optional[str] = None,
        file: Optional[str] = None,
        rule: Optional[str] = None,
        json: bool = False,
    ) -> None:
        """Evaluate now without writing runtime or notifying."""
        rules = self._dry_run_rules(rule_id=rule_id, file=file, rule=rule)
        reports = [self._engine.dry_run(r).to_public() for r in rules]
        if json:
            self._out.say_json(reports if len(reports) > 1 else reports[0])
            return
        for report in reports:
            self._out.print_dry_run(report)

    def test(self, rule_id: str) -> None:
        """Send alert.test through the rule's channel routing."""
        try:
            deliveries = AlertTester(self._stack.root).send(rule_id)
        except KeyError as exc:
            raise OperatorError(
                f"unknown alert rule {rule_id!r}.\nFix: raft alerts list"
            ) from exc
        self._out.print_deliveries(deliveries)
        ok = any(d.result.status == DeliveryStatus.SUCCESS for d in deliveries)
        if not ok:
            raise SystemExit(1)

    def enable(self, rule_id: str) -> None:
        """Enable a rule."""
        self._set_enabled(rule_id, True)

    def disable(self, rule_id: str) -> None:
        """Disable a rule."""
        self._set_enabled(rule_id, False)

    def apply(self, file: str, prune: bool = False) -> None:
        """Upsert rules from a YAML file."""
        raw = self._read_file(file)
        summary = self._service.apply_document(raw, prune=prune)
        self._out.say_json(summary.to_public())

    def delete(self, rule_id: str) -> None:
        """Delete a rule."""
        try:
            self._service.delete(rule_id)
        except KeyError as exc:
            raise OperatorError(
                f"unknown alert rule {rule_id!r}.\nFix: raft alerts list"
            ) from exc
        self._out.say(f"Deleted {rule_id}.")

    def export(self, file: Optional[str] = None) -> None:
        """Export the rules document."""
        payload = self._service.export_document()
        text = yaml.safe_dump(payload, sort_keys=False)
        if file:
            Path(file).write_text(text, encoding="utf-8")
            self._out.say(f"Wrote {file}")
            return
        self._out.say(text.rstrip())

    def status(self, json: bool = False) -> None:
        """Show last evaluation and firing instances."""
        payload = AlertStatusView(self._stack.root).build()
        if payload.get("stale"):
            self._out.say(
                "warning: controller not evaluating — check `raft doctor`"
            )
        if json:
            self._out.say_json(payload)
            return
        last = payload.get("lastEvaluation") or {}
        self._out.say(
            f"enabled={payload.get('enabled')} interval={payload.get('intervalSeconds')}s "
            f"finishedAt={last.get('finishedAt')} errors={len(last.get('errors') or [])}"
        )
        for inst in payload.get("instances") or []:
            self._out.say(
                f"{inst['fingerprint']} {inst['state']} suppressed={inst['suppressed']}"
            )

    def _set_enabled(self, rule_id: str, enabled: bool) -> None:
        try:
            self._service.set_enabled(rule_id, enabled)
        except KeyError as exc:
            raise OperatorError(
                f"unknown alert rule {rule_id!r}.\nFix: raft alerts list"
            ) from exc
        verb = "Enabled" if enabled else "Disabled"
        self._out.say(f"{verb} {rule_id}.")

    def _dry_run_rules(self, *, rule_id, file, rule):
        if file:
            return self._dry_run_from_file(file, rule)
        return self._dry_run_by_id(rule_id)

    def _dry_run_from_file(self, file: str, rule: Optional[str]):
        raw = self._read_file(file)
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

    def _dry_run_by_id(self, rule_id: Optional[str]):
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

    def _load_raw(self, file: Optional[str]) -> Any:
        if file:
            return self._read_file(file)
        path = self._stack.root / "host" / "alerts" / "rules.yaml"
        if not path.is_file():
            return {"version": 1, "rules": []}
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    @staticmethod
    def _read_file(file: str) -> Any:
        path = Path(file)
        try:
            return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise OperatorError(
                f"cannot read {file}: {exc}.\nFix: provide a valid YAML file"
            ) from exc

    @staticmethod
    def _summarize(condition: Any) -> str:
        if not isinstance(condition, dict):
            return "?"
        if "all" in condition:
            return "all(...)"
        if "any" in condition:
            return "any(...)"
        return f"{condition.get('signal')} {condition.get('kind')}"
