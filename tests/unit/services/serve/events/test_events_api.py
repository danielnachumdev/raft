"""Serve ``GET /api/events`` adapter."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

from raft.core.core.models.state.ops_event import OpsEvent
from raft.core.core.models.state.ops_event_store import OpsEventStore
from raft.core.core.models.stack import Stack
from raft.core.observe.ops.events import OpsEventsService
from raft.services.serve.events import ServeEventsApi

from tests.unit.base import RaftTestCase


class TestServeEventsApi(RaftTestCase):
    def test_api_list(self) -> None:
        home = self.tmp_path / "raft"
        stack = MagicMock(spec=Stack)
        stack.root = home
        when = datetime.now(timezone.utc)
        OpsEventStore(home).append(
            OpsEvent(
                kind="deploy.apply",
                ts=when.isoformat(),
                summary="Deploy demo-api",
                service="demo-api",
                id="d1",
            )
        )
        api = ServeEventsApi(stack, service=OpsEventsService(home))
        payload = api.api_list(hours=24, service="demo-api")
        assert payload["count"] == 1
        assert payload["events"][0]["kind"] == "deploy.apply"

    def test_register_binds_route(self) -> None:
        stack = MagicMock(spec=Stack)
        stack.root = self.tmp_path / "raft"
        app = MagicMock()
        ServeEventsApi(stack).register(app)
        app.get.assert_called_once()
