"""Shared fakes for AlertEngine tests."""

from datetime import timedelta
from typing import List

from raft.core.observe.alerts.signals.series import SignalPoint, SubjectSeries, ValueType
from raft.core.observe.alerts.signals.signal_source import SignalSource
from raft.core.observe.notify.event import NotificationEvent


class FakeHttp(SignalSource):
    def __init__(self, rate: float) -> None:
        self.rate = rate

    @property
    def type_id(self) -> str:
        return "metrics.http"

    @property
    def value_type(self) -> ValueType:
        return ValueType.NUMERIC

    def validate_select(self, select, *, path):
        return []

    def query(self, select, *, window_seconds, ctx):
        now = ctx.now
        return [
            SubjectSeries(
                "demo-api",
                (SignalPoint(now - timedelta(seconds=30), self.rate),),
                wildcard=False,
            )
        ]

    def describe(self, select):
        return "demo-api error_rate_5xx"


class FakeNotifier:
    def __init__(self) -> None:
        self.events: List[NotificationEvent] = []

    def notify(self, event, *, channel_ids=None) -> None:
        self.events.append(event)
