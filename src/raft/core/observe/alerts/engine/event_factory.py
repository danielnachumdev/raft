"""Build NotificationEvents for alert transitions."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from raft.core.observe.notify.event import NotificationEvent
from raft.core.observe.notify.severity import NotificationSeverity

from ..constants import KIND_ALERT_FIRING, KIND_ALERT_RESOLVED, KIND_ALERT_TEST
from ..model.rule import AlertRule
from ..store.runtime_state import AlertInstanceState
from .fingerprint import AlertFingerprint
from .leaf_result import SubjectOutcome


class AlertEventFactory:
    """Map rule transitions onto NotificationEvent."""

    def firing(
        self,
        rule: AlertRule,
        outcome: SubjectOutcome,
        instance: AlertInstanceState,
    ) -> NotificationEvent:
        subject = outcome.subject
        title = self._title("FIRING", rule, subject)
        body = self._firing_body(rule, outcome, instance)
        return NotificationEvent(
            kind=KIND_ALERT_FIRING,
            severity=rule.severity,
            title=title,
            body=body,
            context=self._context(rule, subject, "firing", instance),
        )

    def resolved(
        self,
        rule: AlertRule,
        outcome: SubjectOutcome,
        instance: AlertInstanceState,
        *,
        now: datetime,
    ) -> NotificationEvent:
        subject = outcome.subject
        title = self._title("RESOLVED", rule, subject)
        duration = self._duration(instance.firing_since, now)
        body = f"Recovered after {duration}"
        if outcome.leaves:
            body += "\n" + "\n".join(lv.detail for lv in outcome.leaves)
        return NotificationEvent(
            kind=KIND_ALERT_RESOLVED,
            severity=NotificationSeverity.INFO,
            title=title,
            body=body,
            context=self._context(rule, subject, "resolved", instance, now=now),
        )

    def test(self, rule: AlertRule) -> NotificationEvent:
        return NotificationEvent(
            kind=KIND_ALERT_TEST,
            severity=NotificationSeverity.INFO,
            title=f"[TEST] {rule.name}",
            body=(
                f"Test notification for alert rule {rule.id}; "
                f"no condition was evaluated."
            ),
            context={
                "rule_id": rule.id,
                "rule_name": rule.name,
                "test": True,
                "channel_ids": list(rule.channel_ids),
            },
        )

    def _context(
        self,
        rule: AlertRule,
        subject: str,
        state: str,
        instance: AlertInstanceState,
        *,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        ctx: Dict[str, Any] = {
            "rule_id": rule.id,
            "rule_name": rule.name,
            "fingerprint": AlertFingerprint.of(rule.id, subject),
            "subject": subject,
            "state": state,
            "severity": rule.severity.value,
            "channel_ids": list(rule.channel_ids),
            "values": list(instance.last_values),
        }
        if instance.firing_since is not None:
            ctx["firing_since"] = instance.firing_since.isoformat()
        if state == "resolved" and now is not None:
            ctx["resolved_at"] = now.isoformat()
        return ctx

    @staticmethod
    def _title(tag: str, rule: AlertRule, subject: str) -> str:
        base = f"[{tag}] {rule.name}"
        return f"{base}: {subject}" if subject != "-" else base

    @staticmethod
    def _firing_body(
        rule: AlertRule, outcome: SubjectOutcome, instance: AlertInstanceState
    ) -> str:
        parts: List[str] = []
        if rule.description:
            parts.append(rule.description)
        for leaf in outcome.leaves:
            parts.append(leaf.detail)
        if instance.firing_since is not None:
            parts.append(f"Firing since {instance.firing_since.isoformat()}")
        return "\n".join(parts)

    @staticmethod
    def _duration(start: Optional[datetime], end: datetime) -> str:
        if start is None:
            return "unknown duration"
        seconds = max(0, int((end - start).total_seconds()))
        if seconds < 60:
            return f"{seconds}s"
        if seconds < 3600:
            return f"{seconds // 60}m"
        return f"{seconds // 3600}h"
