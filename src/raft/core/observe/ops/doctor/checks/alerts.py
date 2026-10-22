"""Warn when alert rules exist but the controller has not evaluated recently."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

import yaml

from raft.core.core.config.settings import SettingsLoader
from raft.core.core.config.settings.alerts_config import AlertsConfig
from raft.core.observe.alerts.constants import (
    ALERTS_STATE_DIR,
    RULES_NAME,
    RUNTIME_NAME,
)

from ..context import DoctorContext
from ..models import INFRA, CheckResult


class AlertsChecks:
    """Stale / mount signal for ``host/alerts`` evaluation (warn-only)."""

    name = "alerts"

    def run(self, ctx: DoctorContext) -> list[CheckResult]:
        alerts = SettingsLoader().load(ctx.stack.root).alerts
        if not alerts.enabled:
            return []
        result = self._check(ctx.stack.root, alerts)
        return [result] if result is not None else []

    def _check(self, home: Path, alerts: AlertsConfig) -> Optional[CheckResult]:
        count, err = self._rules_info(home / ALERTS_STATE_DIR / RULES_NAME)
        if err:
            return self._document_error(err)
        if count == 0:
            return None
        last = self._last_evaluation(home / ALERTS_STATE_DIR / RUNTIME_NAME)
        if self._is_stale(last, alerts.interval_seconds):
            return self._stale()
        return CheckResult(
            INFRA, "alerts", "ok", "controller evaluating alert rules"
        )

    @staticmethod
    def _rules_info(path: Path) -> tuple[int, Optional[str]]:
        if not path.is_file():
            return 0, None
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            return 0, str(exc).split("\n")[0]
        if raw is None:
            return 0, None
        if not isinstance(raw, Mapping):
            return 0, "rules document must be a mapping"
        rules = raw.get("rules") or []
        if not isinstance(rules, list):
            return 0, "rules must be a list"
        return len(rules), None

    @staticmethod
    def _last_evaluation(path: Path) -> Optional[Mapping[str, Any]]:
        if not path.is_file():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(raw, Mapping):
            return None
        last = raw.get("lastEvaluation")
        return last if isinstance(last, Mapping) else None

    @staticmethod
    def _is_stale(last: Optional[Mapping[str, Any]], interval: float) -> bool:
        if not last or not last.get("finishedAt"):
            return True
        try:
            finished = datetime.fromisoformat(
                str(last["finishedAt"]).replace("Z", "+00:00")
            )
            if finished.tzinfo is None:
                finished = finished.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - finished).total_seconds()
        except (TypeError, ValueError):
            return True
        return age > 3 * interval

    @staticmethod
    def _document_error(detail: str) -> CheckResult:
        return CheckResult(
            INFRA,
            "alerts",
            "warn",
            f"alert rules document error: {detail}",
            fix="fix host/alerts/rules.yaml (raft alerts validate)",
        )

    @staticmethod
    def _stale() -> CheckResult:
        return CheckResult(
            INFRA,
            "alerts",
            "warn",
            "controller has not evaluated alerts recently",
            fix=(
                "raft up (ensure raft-controller is running with "
                "host/alerts mounted), then re-check raft doctor"
            ),
        )
