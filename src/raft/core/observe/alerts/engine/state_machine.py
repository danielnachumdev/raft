"""Pending / firing / cool-down / recovery transitions."""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Optional

from ..model.rule import AlertRule
from ..store.runtime_state import AlertInstanceState
from .fingerprint import AlertFingerprint
from .leaf_result import SubjectOutcome


@dataclass(frozen=True)
class Transition:
    instance: Optional[AlertInstanceState]
    notify: Optional[str]  # None | firing | resolved


class AlertStateMachine:
    """Advance one fingerprint through the alert state table."""

    def step(
        self,
        prev: Optional[AlertInstanceState],
        outcome: SubjectOutcome,
        rule: AlertRule,
        *,
        now: datetime,
    ) -> Transition:
        if outcome.matched is None:
            return self._keep(prev, outcome, now)
        if outcome.matched:
            return self._on_true(prev, outcome, rule, now=now)
        return self._on_false(prev, outcome, rule, now=now)

    def _keep(
        self,
        prev: Optional[AlertInstanceState],
        outcome: SubjectOutcome,
        now: datetime,
    ) -> Transition:
        if prev is None:
            return Transition(None, None)
        return Transition(self._touch(prev, outcome, now), None)

    def _on_true(
        self,
        prev: Optional[AlertInstanceState],
        outcome: SubjectOutcome,
        rule: AlertRule,
        *,
        now: datetime,
    ) -> Transition:
        state = prev.state if prev is not None else "ok"
        if prev is None or state == "ok":
            return self._rise_from_ok(prev, outcome, rule, now=now)
        if state == "pending":
            return self._pending_hold(prev, outcome, rule, now=now)
        return self._still_firing(prev, outcome, rule, now=now)

    def _rise_from_ok(
        self,
        prev: Optional[AlertInstanceState],
        outcome: SubjectOutcome,
        rule: AlertRule,
        *,
        now: datetime,
    ) -> Transition:
        cooldown = prev.cooldown_until if prev is not None else None
        if rule.for_seconds > 0:
            return Transition(
                self._new(rule, outcome, now, state="pending"), None
            )
        return self._to_firing(
            self._new(rule, outcome, now, state="firing"),
            rule,
            now=now,
            cooldown_until=cooldown,
        )

    def _pending_hold(
        self,
        prev: AlertInstanceState,
        outcome: SubjectOutcome,
        rule: AlertRule,
        *,
        now: datetime,
    ) -> Transition:
        updated = self._touch(prev, outcome, now)
        since = prev.pending_since or now
        if (now - since).total_seconds() < rule.for_seconds:
            return Transition(updated, None)
        firing = replace(updated, state="firing", firing_since=now, pending_since=None)
        return self._to_firing(
            firing, rule, now=now, cooldown_until=prev.cooldown_until
        )

    def _still_firing(
        self,
        prev: AlertInstanceState,
        outcome: SubjectOutcome,
        rule: AlertRule,
        *,
        now: datetime,
    ) -> Transition:
        updated = self._touch(prev, outcome, now)
        if self._should_repeat(updated, rule, now=now):
            return Transition(replace(updated, last_notified_at=now), "firing")
        return Transition(updated, None)

    def _on_false(
        self,
        prev: Optional[AlertInstanceState],
        outcome: SubjectOutcome,
        rule: AlertRule,
        *,
        now: datetime,
    ) -> Transition:
        if prev is None or prev.state == "ok":
            return Transition(self._keep_cooldown(prev, now), None)
        if prev.state == "pending":
            return Transition(self._keep_cooldown(prev, now), None)
        notify = "resolved" if rule.notify_on_recovery and not prev.suppressed else None
        holder = self._resolve_holder(prev, outcome, rule, now=now)
        return Transition(holder, notify)

    def _to_firing(
        self,
        instance: AlertInstanceState,
        rule: AlertRule,
        *,
        now: datetime,
        cooldown_until: Optional[datetime],
    ) -> Transition:
        if cooldown_until is not None and now < cooldown_until:
            return Transition(
                replace(
                    instance,
                    suppressed=True,
                    cooldown_until=cooldown_until,
                    last_notified_at=None,
                ),
                None,
            )
        return Transition(
            replace(
                instance,
                suppressed=False,
                cooldown_until=None,
                last_notified_at=now,
                firing_since=instance.firing_since or now,
            ),
            "firing",
        )

    def _new(
        self,
        rule: AlertRule,
        outcome: SubjectOutcome,
        now: datetime,
        *,
        state: str,
    ) -> AlertInstanceState:
        return AlertInstanceState(
            rule_id=rule.id,
            subject=outcome.subject,
            rule_hash=AlertFingerprint.rule_hash(rule),
            state=state,
            pending_since=now if state == "pending" else None,
            firing_since=now if state == "firing" else None,
            last_evaluated_at=now,
            last_values=[lv.to_public() for lv in outcome.leaves],
        )

    def _resolve_holder(
        self,
        prev: AlertInstanceState,
        outcome: SubjectOutcome,
        rule: AlertRule,
        *,
        now: datetime,
    ) -> Optional[AlertInstanceState]:
        if rule.cooldown_seconds <= 0:
            return None
        return AlertInstanceState(
            rule_id=prev.rule_id,
            subject=prev.subject,
            rule_hash=prev.rule_hash,
            state="ok",
            last_notified_at=prev.last_notified_at,
            last_resolved_at=now,
            cooldown_until=now + timedelta(seconds=rule.cooldown_seconds),
            last_evaluated_at=now,
            last_values=[lv.to_public() for lv in outcome.leaves],
        )

    @staticmethod
    def _keep_cooldown(
        prev: Optional[AlertInstanceState], now: datetime
    ) -> Optional[AlertInstanceState]:
        if prev is None:
            return None
        if prev.cooldown_until is not None and now < prev.cooldown_until:
            return replace(prev, state="ok", pending_since=None, firing_since=None)
        return None

    @staticmethod
    def _should_repeat(
        instance: AlertInstanceState, rule: AlertRule, *, now: datetime
    ) -> bool:
        if rule.repeat_every_seconds <= 0 or instance.suppressed:
            return False
        if instance.last_notified_at is None:
            return False
        elapsed = (now - instance.last_notified_at).total_seconds()
        return elapsed >= rule.repeat_every_seconds

    @staticmethod
    def _touch(
        prev: AlertInstanceState, outcome: SubjectOutcome, now: datetime
    ) -> AlertInstanceState:
        return replace(
            prev,
            last_evaluated_at=now,
            last_values=[lv.to_public() for lv in outcome.leaves],
        )
