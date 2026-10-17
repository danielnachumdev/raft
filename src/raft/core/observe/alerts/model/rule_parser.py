"""Parse and validate a single alert rule mapping."""

import re
from typing import Any, List, Mapping, Optional, Sequence

from raft.core.core.errors.cta import OperatorError
from raft.core.observe.notify.severity import NotificationSeverity

from ..constants import (
    MAX_COOLDOWN_SECONDS,
    MAX_DESCRIPTION_LEN,
    MAX_FOR_SECONDS,
    MAX_NAME_LEN,
    RULE_ID_PATTERN,
)
from ..registries import AlertRegistries
from .condition_parser import ConditionParser
from .duration import AlertDuration
from .issues import ValidationReport
from .rule import AlertRule

_NO_DATA = frozenset({"ok", "alerting", "keep"})
_ID_RE = re.compile(RULE_ID_PATTERN)


class AlertRuleParser:
    """Parse one rule with registry-aware leaf validation."""

    def __init__(self, registries: AlertRegistries) -> None:
        self._regs = registries
        self._conditions = ConditionParser()

    def parse(self, raw: Any, path: str = "rule") -> AlertRule:
        report = self.validate(raw, path=path)
        if not report.ok:
            raise OperatorError(self._format(report, path))
        return self._build(raw, path)

    def validate(self, raw: Any, path: str = "rule") -> ValidationReport:
        report = ValidationReport()
        if not isinstance(raw, Mapping):
            report.add_error(path, "rule must be a mapping")
            return report
        self._id(raw, path, report)
        self._basics(raw, path, report)
        self._timing(raw, path, report)
        self._channels(raw, path, report)
        self._condition(raw, path, report)
        return report

    def _build(self, raw: Mapping[str, Any], path: str) -> AlertRule:
        condition = self._conditions.parse(raw["condition"], f"{path}.condition")
        timing = self._timing_fields(raw, path)
        return AlertRule(
            id=str(raw["id"]),
            name=str(raw.get("name") or raw["id"]),
            enabled=bool(raw.get("enabled", True)),
            severity=NotificationSeverity(str(raw.get("severity") or "warning")),
            description=str(raw.get("description") or ""),
            condition=condition,
            channel_ids=tuple(str(x) for x in (raw.get("channelIds") or [])),
            notify_on_recovery=bool(raw.get("notifyOnRecovery", True)),
            no_data=str(raw.get("noData") or "ok"),
            **timing,
        )

    def _timing_fields(self, raw: Mapping[str, Any], path: str) -> dict:
        return {
            "for_seconds": AlertDuration.parse(
                raw.get("for"), path=f"{path}.for", default=0, max_seconds=MAX_FOR_SECONDS
            ),
            "cooldown_seconds": AlertDuration.parse(
                raw.get("cooldown"),
                path=f"{path}.cooldown",
                default=15 * 60,
                max_seconds=MAX_COOLDOWN_SECONDS,
            ),
            "repeat_every_seconds": self._repeat(raw, path),
        }

    def _id(self, raw: Mapping[str, Any], path: str, report: ValidationReport) -> None:
        rule_id = raw.get("id")
        if not isinstance(rule_id, str) or not _ID_RE.match(rule_id):
            report.add_error(
                f"{path}.id",
                "id must match ^[a-z0-9][a-z0-9-]{0,62}$",
            )

    def _basics(self, raw: Mapping[str, Any], path: str, report: ValidationReport) -> None:
        name = raw.get("name", raw.get("id", ""))
        if not isinstance(name, str) or not (1 <= len(name) <= MAX_NAME_LEN):
            report.add_error(f"{path}.name", f"name must be 1–{MAX_NAME_LEN} chars")
        description = raw.get("description") or ""
        if not isinstance(description, str) or len(description) > MAX_DESCRIPTION_LEN:
            report.add_error(
                f"{path}.description",
                f"description must be ≤ {MAX_DESCRIPTION_LEN} chars",
            )
        severity = str(raw.get("severity") or "warning")
        try:
            NotificationSeverity(severity)
        except ValueError:
            report.add_error(f"{path}.severity", f"unknown severity {severity!r}")
        no_data = str(raw.get("noData") or "ok")
        if no_data not in _NO_DATA:
            report.add_error(f"{path}.noData", f"noData must be one of {sorted(_NO_DATA)}")
        if "enabled" in raw and not isinstance(raw["enabled"], bool):
            report.add_error(f"{path}.enabled", "enabled must be a boolean")

    def _timing(self, raw: Mapping[str, Any], path: str, report: ValidationReport) -> None:
        for key, default, max_s in (
            ("for", 0, MAX_FOR_SECONDS),
            ("cooldown", 15 * 60, MAX_COOLDOWN_SECONDS),
        ):
            try:
                AlertDuration.parse(
                    raw.get(key), path=f"{path}.{key}", default=default, max_seconds=max_s
                )
            except OperatorError as exc:
                report.add_error(f"{path}.{key}", str(exc).split("\n")[0])
        try:
            self._repeat(raw, path)
        except OperatorError as exc:
            report.add_error(f"{path}.repeatEvery", str(exc).split("\n")[0])

    def _repeat(self, raw: Mapping[str, Any], path: str) -> int:
        seconds = AlertDuration.parse(
            raw.get("repeatEvery"),
            path=f"{path}.repeatEvery",
            default=0,
            max_seconds=MAX_COOLDOWN_SECONDS,
        )
        if seconds != 0 and seconds < 300:
            raise OperatorError(
                f"{path}.repeatEvery: must be 0 or ≥ 5m.\nFix: use 0 or 5m+"
            )
        return seconds

    def _channels(
        self, raw: Mapping[str, Any], path: str, report: ValidationReport
    ) -> None:
        ids = raw.get("channelIds") or []
        if not isinstance(ids, list) or any(not isinstance(x, str) or not x for x in ids):
            report.add_error(f"{path}.channelIds", "channelIds must be a list of strings")

    def _condition(
        self, raw: Mapping[str, Any], path: str, report: ValidationReport
    ) -> None:
        if "condition" not in raw:
            report.add_error(f"{path}.condition", "condition is required")
            return
        cond_report = self._conditions.validate(raw["condition"], f"{path}.condition")
        report.extend(cond_report)
        if cond_report.ok:
            self._validate_leaves(raw["condition"], f"{path}.condition", report)

    def _validate_leaves(
        self, raw: Any, path: str, report: ValidationReport
    ) -> None:
        if not isinstance(raw, Mapping):
            return
        if "all" in raw or "any" in raw:
            op = "all" if "all" in raw else "any"
            children = raw.get(op) or []
            if isinstance(children, list):
                for i, child in enumerate(children):
                    self._validate_leaves(child, f"{path}.{op}[{i}]", report)
            return
        self._validate_leaf(raw, path, report)

    def _validate_leaf(
        self, raw: Mapping[str, Any], path: str, report: ValidationReport
    ) -> None:
        signal = raw.get("signal")
        kind = raw.get("kind")
        source = self._leaf_signal(signal, path, report)
        if source is None:
            return
        select = raw.get("select") or {}
        if isinstance(select, Mapping):
            self._merge_issues(source.validate_select(select, path=f"{path}.select"), report)
        rule_kind = self._leaf_kind(kind, source, path, report)
        if rule_kind is None:
            return
        params = raw.get("params") or {}
        if isinstance(params, Mapping):
            self._merge_issues(
                rule_kind.validate_params(params, path=f"{path}.params"), report
            )

    def _leaf_signal(self, signal, path, report):
        if not isinstance(signal, str) or not self._regs.signals.has(signal):
            report.add_error(f"{path}.signal", f"unknown signal {signal!r}")
            return None
        return self._regs.signals.get(signal)

    def _leaf_kind(self, kind, source, path, report):
        if not isinstance(kind, str) or not self._regs.kinds.has(kind):
            report.add_error(f"{path}.kind", f"unknown kind {kind!r}")
            return None
        rule_kind = self._regs.kinds.get(kind)
        if source.value_type not in rule_kind.value_types:
            report.add_error(
                f"{path}.kind",
                f"kind {kind!r} does not accept value type {source.value_type.value}",
            )
        return rule_kind

    @staticmethod
    def _merge_issues(issues, report: ValidationReport) -> None:
        for issue in issues:
            if issue.level == "error":
                report.add_error(issue.path, issue.message)
            else:
                report.add_warning(issue.path, issue.message)

    @staticmethod
    def _format(report: ValidationReport, path: str) -> str:
        lines = [f"{i.path}: {i.message}" for i in report.errors]
        joined = "\n".join(f"- {line}" for line in lines)
        return f"invalid alert rule.\n{joined}\nFix: repair the rule at {path}"
