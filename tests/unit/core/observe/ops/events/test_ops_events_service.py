"""OpsEventsService query window for CLI / serve."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from raft.core.core.models.state.ops_event import OpsEvent
from raft.core.core.models.state.ops_event_store import OpsEventStore
from raft.core.observe.ops.events import OpsEventsService

from tests.unit.base import RaftTestCase


class TestOpsEventsService(RaftTestCase):
    def test_list_events_newest_first_and_clamps(self) -> None:
        home = self.tmp_path / "raft"
        store = OpsEventStore(home)
        now = datetime.now(timezone.utc)
        early = now - timedelta(hours=2)
        late = now - timedelta(minutes=5)
        store.append(
            OpsEvent(kind="stack.up", ts=early.isoformat(), summary="early", id="a")
        )
        store.append(
            OpsEvent(kind="stack.down", ts=late.isoformat(), summary="late", id="b")
        )
        svc = OpsEventsService(home, store=store)
        payload = svc.list_events(hours=9999, limit=0)
        assert payload["hours"] == 168
        assert payload["count"] == 1
        assert payload["events"][0]["id"] == "b"

    def test_filters_kind_and_service(self) -> None:
        home = self.tmp_path / "raft"
        store = OpsEventStore(home)
        when = datetime.now(timezone.utc)
        self._seed(store, when)
        payload = OpsEventsService(home, store=store).list_events(
            hours=24, service="demo-api", kind="deploy.apply"
        )
        assert [e["id"] for e in payload["events"]] == ["1"]

    @staticmethod
    def _seed(store: OpsEventStore, when: datetime) -> None:
        store.append(
            OpsEvent(
                kind="deploy.apply",
                ts=when.isoformat(),
                summary="Deploy demo-api",
                service="demo-api",
                id="1",
            )
        )
        store.append(
            OpsEvent(
                kind="alert.fired",
                ts=when.isoformat(),
                summary="Alert fired",
                service="other",
                id="2",
            )
        )
