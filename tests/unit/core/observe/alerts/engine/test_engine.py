"""AlertEngine tick end-to-end with fake source."""

from datetime import datetime, timezone, timedelta
from pathlib import Path

from raft.core.observe.alerts.engine.dispatch import AlertDispatch
from raft.core.observe.alerts.engine.engine import AlertEngine
from raft.core.observe.alerts.kinds.kind_registry import RuleKindRegistry
from raft.core.observe.alerts.kinds.threshold import ThresholdKind
from raft.core.observe.alerts.model.document import AlertRulesDocument
from raft.core.observe.alerts.model.rule_parser import AlertRuleParser
from raft.core.observe.alerts.registries import AlertRegistries
from raft.core.observe.alerts.signals.signal_registry import SignalRegistry
from raft.core.observe.alerts.store.rules_store import AlertRulesStore
from tests.unit.base import RaftTestCase
from tests.unit.core.observe.alerts.engine.test_engine_helpers import FakeHttp, FakeNotifier
from tests.unit.core.observe.alerts.sample_rule import RULE


def _engine(home: Path, fake: FakeHttp) -> AlertEngine:
    signals = SignalRegistry()
    signals.register(fake)
    kinds = RuleKindRegistry()
    kinds.register(ThresholdKind())
    regs = AlertRegistries(signals=signals, kinds=kinds)
    store = AlertRulesStore(home, registries=regs)
    parsed = AlertRuleParser(regs).parse(RULE)
    store.save(AlertRulesDocument(1, (parsed,)))
    return AlertEngine(
        home,
        registries=regs,
        rules_store=store,
        dispatch=AlertDispatch(FakeNotifier()),  # type: ignore[arg-type]
        app_names=lambda: ["demo-api"],
    )


class TestAlertEngine(RaftTestCase):
    def test_fires(self) -> None:
        home = Path(self.tmp_path)
        (home / "host" / "alerts").mkdir(parents=True, exist_ok=True)
        fake = FakeHttp(0.1)
        engine = _engine(home, fake)
        notifier = engine._dispatch._notifier
        now = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
        report = engine.tick(now=now)
        assert report.notifications_sent == 1
        assert notifier.events[0].kind == "alert.firing"

    def test_resolves(self) -> None:
        home = Path(self.tmp_path)
        (home / "host" / "alerts").mkdir(parents=True, exist_ok=True)
        fake = FakeHttp(0.1)
        engine = _engine(home, fake)
        notifier = engine._dispatch._notifier
        now = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
        engine.tick(now=now)
        fake.rate = 0.01
        engine.tick(now=now + timedelta(minutes=1))
        assert any(e.kind == "alert.resolved" for e in notifier.events)
