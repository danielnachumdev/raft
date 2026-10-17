"""Alert engine tick and dry-run."""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional, Sequence

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.stack import Stack
from raft.core.core.models.state.ops_event_store import OpsEventStore
from raft.core.observe.notify.notifier import Notifier

from ..catalogs import AlertCatalogs
from ..model.rule import AlertRule
from ..registries import AlertRegistries
from ..signals.context import SignalContext
from ..store.rules_store import AlertRulesStore
from ..store.runtime_state import AlertRuntime
from ..store.runtime_store import AlertRuntimeStore
from .dispatch import AlertDispatch
from .event_factory import AlertEventFactory
from .fingerprint import AlertFingerprint
from .report import DryRunReport, EvaluationReport
from .rule_evaluator import AlertRuleEvaluator
from .state_machine import AlertStateMachine

logger = logging.getLogger(__name__)


class AlertEngine:
    """Load rules, evaluate signals, persist runtime, then notify."""

    def __init__(
        self,
        home: Path,
        *,
        registries: Optional[AlertRegistries] = None,
        rules_store: Optional[AlertRulesStore] = None,
        runtime_store: Optional[AlertRuntimeStore] = None,
        dispatch: Optional[AlertDispatch] = None,
        app_names: Optional[Callable[[], Sequence[str]]] = None,
    ) -> None:
        self._home = home
        self._regs = registries or AlertCatalogs.default()
        self._rules = rules_store or AlertRulesStore(home, registries=self._regs)
        self._runtime = runtime_store or AlertRuntimeStore(home)
        self._dispatch = dispatch or AlertDispatch(Notifier(home))
        self._app_names = app_names or (lambda: self._load_apps())
        self._evaluator = AlertRuleEvaluator(self._regs)
        self._machine = AlertStateMachine()
        self._events = AlertEventFactory()
        self._unwritable_logged = False

    def tick(self, now: Optional[datetime] = None) -> EvaluationReport:
        now = now or datetime.now(timezone.utc)
        started = now
        runtime = self._runtime.load()
        if not self._writable():
            return self._empty_report(started, now, document_error="runtime not writable")
        try:
            document = self._rules.load()
        except OperatorError as exc:
            report = self._empty_report(started, now, document_error=str(exc).split("\n")[0])
            runtime.last_evaluation = report.to_public()
            self._runtime.save(runtime)
            return report
        return self._run(document.rules, runtime, now=now, started=started)

    def dry_run(
        self, rule: AlertRule, now: Optional[datetime] = None
    ) -> DryRunReport:
        now = now or datetime.now(timezone.utc)
        runtime = self._runtime.load()
        ctx = SignalContext(self._home, now, app_names=self._app_names())
        error, outcomes = self._evaluator.evaluate(rule, ctx)
        subjects = [
            self._dry_run_subject(rule, outcome, runtime, now) for outcome in outcomes
        ]
        return DryRunReport(rule.id, now, error=error, subjects=subjects)

    def _dry_run_subject(self, rule, outcome, runtime, now):
        fp = AlertFingerprint.of(rule.id, outcome.subject)
        prev = runtime.instances.get(fp)
        transition = self._machine.step(prev, outcome, rule, now=now)
        inst = transition.instance
        return {
            "subject": outcome.subject,
            "matched": outcome.matched,
            "currentState": prev.state if prev else "ok",
            "wouldState": inst.state if inst else "ok",
            "wouldNotify": transition.notify,
            "leaves": [lv.to_public() for lv in outcome.leaves],
        }

    def _run(self, rules, runtime: AlertRuntime, *, now, started) -> EvaluationReport:
        ctx = SignalContext(self._home, now, app_names=self._app_names())
        report = EvaluationReport(started, now, rules_total=len(rules))
        enabled = [r for r in rules if r.enabled]
        report.rules_skipped_disabled = len(rules) - len(enabled)
        transitions = self._evaluate_enabled(enabled, ctx, runtime, report, now=now)
        self._apply_transitions(runtime, transitions, report)
        sent = self._notify_all(transitions, now=now)
        report.notifications_sent = sent
        report.finished_at = datetime.now(timezone.utc)
        runtime.last_evaluation = report.to_public()
        self._runtime.save(runtime)
        return report

    def _evaluate_enabled(self, enabled, ctx, runtime, report, *, now):
        active_fps = set()
        rule_by_id = {r.id: r for r in enabled}
        transitions = []
        for rule in enabled:
            report.rules_evaluated += 1
            error, outcomes = self._evaluator.evaluate(rule, ctx)
            if error:
                report.errors.append({"ruleId": rule.id, "message": error})
                continue
            for outcome in outcomes:
                fp = AlertFingerprint.of(rule.id, outcome.subject)
                active_fps.add(fp)
                prev = runtime.instances.get(fp)
                prev = self._maybe_reset_instance(prev, rule, fp)
                step = self._machine.step(prev, outcome, rule, now=now)
                transitions.append((rule, outcome, step, fp, prev))
        self._prune(runtime, rule_by_id, active_fps)
        return transitions

    def _maybe_reset_instance(self, prev, rule, fp):
        if prev and prev.rule_hash != AlertFingerprint.rule_hash(rule):
            logger.info("alert ruleHash changed; resetting %s", fp)
            return None
        return prev

    def _apply_transitions(self, runtime, transitions, report) -> None:
        for _rule, _outcome, step, fp, _prev in transitions:
            if step.instance is None:
                runtime.instances.pop(fp, None)
            else:
                runtime.instances[fp] = step.instance

    def _notify_all(self, transitions, *, now: datetime) -> int:
        sent = 0
        for rule, outcome, step, _fp, prev in transitions:
            if not step.notify:
                continue
            instance = step.instance or prev
            if instance is None:
                continue
            if step.notify == "firing":
                event = self._events.firing(rule, outcome, instance)
            else:
                event = self._events.resolved(rule, outcome, instance, now=now)
            self._record_ops_alert(rule, outcome, step.notify)
            self._dispatch.send(rule, event)
            sent += 1
        return sent

    def _record_ops_alert(self, rule, outcome, notify: str) -> None:
        store = OpsEventStore(self._home)
        kwargs = {
            "rule_id": rule.id,
            "subject": outcome.subject,
            "channel_ids": list(rule.channel_ids),
        }
        if notify == "firing":
            store.record_alert_fired(**kwargs)
        else:
            store.record_alert_resolved(**kwargs)

    def _prune(self, runtime, rule_by_id, active_fps) -> None:
        drop = []
        for fp, inst in runtime.instances.items():
            if inst.rule_id not in rule_by_id:
                drop.append(fp)
                continue
            if fp not in active_fps and inst.state in ("pending", "firing"):
                drop.append(fp)
        for fp in drop:
            logger.info("pruning alert instance %s", fp)
            runtime.instances.pop(fp, None)

    def _writable(self) -> bool:
        try:
            self._runtime.ensure_writable()
            return True
        except OSError:
            if not self._unwritable_logged:
                logger.error(
                    "alerts runtime not writable; skipping notifications. "
                    "Fix: raft up to recreate the controller with state/alerts mount"
                )
                self._unwritable_logged = True
            return False

    def _empty_report(self, started, finished, *, document_error=None) -> EvaluationReport:
        return EvaluationReport(
            started, finished, document_error=document_error
        )

    def _load_apps(self) -> Sequence[str]:
        try:
            return [a.name for a in Stack.load_apps(self._home).apps]
        except Exception:  # noqa: BLE001
            return []
