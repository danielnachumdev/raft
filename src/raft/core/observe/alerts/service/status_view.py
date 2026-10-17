"""Join rules + runtime + settings for CLI/serve status."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from raft.core.core.config.settings import SettingsLoader

from ..catalogs import AlertCatalogs
from ..store.rules_store import AlertRulesStore
from ..store.runtime_store import AlertRuntimeStore


class AlertStatusView:
    """Build the public alerts status payload."""

    def __init__(self, home: Path) -> None:
        self._home = home

    def build(self) -> Dict[str, Any]:
        settings = SettingsLoader().load(self._home)
        alerts = settings.alerts
        runtime = AlertRuntimeStore(self._home).load()
        rules, document_error = self._load_rules()
        last = runtime.last_evaluation
        stale = self._stale(last, alerts.interval_seconds, bool(rules), alerts.enabled)
        return {
            "enabled": alerts.enabled,
            "intervalSeconds": int(alerts.interval_seconds),
            "notificationsEnabled": settings.notifications.enabled,
            "stale": stale,
            "lastEvaluation": last,
            "documentError": document_error or (last or {}).get("documentError"),
            "rules": self._rule_states(rules, runtime),
            "instances": self._instances(rules, runtime),
        }

    def _load_rules(self):
        try:
            document = AlertRulesStore(
                self._home, registries=AlertCatalogs.default()
            ).load()
            return list(document.rules), None
        except Exception as exc:  # noqa: BLE001
            return [], str(exc).split("\n")[0]

    def _rule_states(self, rules, runtime) -> Dict[str, Any]:
        out = {}
        for rule in rules:
            counts = self._counts(rule.id, runtime)
            out[rule.id] = {
                "state": self._state(rule, counts, runtime),
                "firingCount": counts["firing"],
                "pendingCount": counts["pending"],
                "suppressedCount": counts["suppressed"],
                "error": None,
            }
        return out

    @staticmethod
    def _counts(rule_id: str, runtime) -> Dict[str, int]:
        firing = pending = suppressed = 0
        for inst in runtime.instances.values():
            if inst.rule_id != rule_id:
                continue
            if inst.suppressed:
                suppressed += 1
            if inst.state == "firing" and inst.firing_since is not None:
                firing += 1
            elif inst.state == "pending":
                pending += 1
        return {"firing": firing, "pending": pending, "suppressed": suppressed}

    def _state(self, rule, counts, runtime) -> str:
        if not rule.enabled:
            return "disabled"
        if counts["firing"]:
            return self._firing_label(rule.id, runtime)
        if counts["pending"]:
            return "pending"
        return "ok"

    @staticmethod
    def _firing_label(rule_id: str, runtime) -> str:
        all_suppressed = all(
            i.suppressed
            for i in runtime.instances.values()
            if i.rule_id == rule_id and i.state == "firing"
        )
        return "suppressed" if all_suppressed else "firing"

    def _instances(self, rules, runtime):
        names = {r.id: r for r in rules}
        rows = []
        for fp, inst in runtime.instances.items():
            row = self._instance_row(fp, inst, names)
            if row is not None:
                rows.append(row)
        order = {"critical": 0, "error": 1, "warning": 2, "info": 3}
        rows.sort(
            key=lambda r: (
                0 if r["state"] == "firing" else 1,
                order.get(r["severity"], 9),
            )
        )
        return rows

    @staticmethod
    def _instance_row(fp, inst, names):
        rule = names.get(inst.rule_id)
        if rule is None or inst.state == "ok":
            return None
        since = inst.firing_since or inst.pending_since
        return {
            "fingerprint": fp,
            "ruleId": inst.rule_id,
            "ruleName": rule.name if rule else inst.rule_id,
            "severity": rule.severity.value if rule else "warning",
            "subject": inst.subject,
            "state": inst.state,
            "suppressed": inst.suppressed,
            "since": since.isoformat() if since else None,
            "lastValues": list(inst.last_values),
        }

    @staticmethod
    def _stale(
        last: Optional[dict], interval: float, has_rules: bool, enabled: bool
    ) -> bool:
        if not enabled or not has_rules:
            return False
        if not last or not last.get("finishedAt"):
            return True
        try:
            finished = datetime.fromisoformat(
                str(last["finishedAt"]).replace("Z", "+00:00")
            )
        except ValueError:
            return True
        age = (datetime.now(timezone.utc) - finished).total_seconds()
        return age > 3 * interval
