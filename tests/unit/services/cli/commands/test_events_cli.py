"""CLI ``raft events`` adapter."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

from raft.core.core.models.state.ops_event import OpsEvent
from raft.core.core.models.state.ops_event_store import OpsEventStore
from raft.core.core.models.stack import Stack
from raft.core.observe.ops.events import OpsEventsService
from raft.services.cli.commands.events import EventsCLI

from tests.unit.base import RaftTestCase


class TestEventsCLI(RaftTestCase):
    def test_json_and_table(self) -> None:
        home = self.tmp_path / "raft"
        stack = MagicMock(spec=Stack)
        stack.root = home
        when = datetime.now(timezone.utc)
        OpsEventStore(home).append(
            OpsEvent(
                kind="stack.purge",
                ts=when.isoformat(),
                summary="Purge reclaimed 0B",
                id="p1",
            )
        )
        cli = EventsCLI(stack, service=OpsEventsService(home))
        cli(hours=24, json=True)
        cli(hours=24, json=False)

