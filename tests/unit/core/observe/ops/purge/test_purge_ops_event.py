"""Purge finish records an ops journal row."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from raft.core.core.models.stack import Stack
from raft.core.core.models.state.ops_event_store import OpsEventStore
from raft.core.observe.ops.purge import Purge
from raft.core.observe.ops.purge.result import PurgeResult

from tests.unit.base import RaftTestCase


class TestPurgeOpsEvent(RaftTestCase):
    def test_execute_records_stack_purge(self) -> None:
        home = self.tmp_path / "raft"
        stack = MagicMock(spec=Stack)
        stack.root = home
        prune = MagicMock()
        prune.unused_images.return_value = 100
        prune.build_cache.return_value = 50
        with patch("raft.core.observe.ops.purge.service.StackLock"):
            result = Purge(stack, docker_prune=prune).execute()
        assert isinstance(result, PurgeResult)
        assert result.reclaimed_bytes == 150
        rows = OpsEventStore(home).events_in_window(
            from_ts=datetime(2020, 1, 1, tzinfo=timezone.utc)
        )
        assert len(rows) == 1
        assert rows[0].kind == "stack.purge"
        assert rows[0].metadata["reclaimed_bytes"] == 150
