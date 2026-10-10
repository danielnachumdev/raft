"""Deploy success records GraphEvents for chart markers."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from raft.models.state.graph_event_kinds import (
    KIND_DEPLOYMENT,
    KIND_UP,
)
from raft.models.state.graph_event_store import GraphEventStore

from .base import OrchestratorTestCase

_EPOCH = datetime(2020, 1, 1, tzinfo=timezone.utc)


class TestDeployGraphEvents(OrchestratorTestCase):
    def test_redeploy_app_records_deployment_event(self) -> None:
        self._redeploy_ok()
        events = self._events()
        assert len(events) == 1
        assert events[0].kind == KIND_DEPLOYMENT
        assert events[0].service == "app"
        assert events[0].metadata["app"] == "app"

    def test_start_on_edge_records_deployment_event(self) -> None:
        self.set_edge_only()
        self.stub_http_ready(self.orch.http)
        with patch.object(self.orch, "sync"):
            self.orch.ensure_app_deployed("app")
        events = self._events()
        assert len(events) == 1
        assert events[0].service == "app"

    def test_cold_ensure_records_stack_up_and_deploy(self) -> None:
        from tests.shared.compose_ids import RunningServices

        self.orch.docker.running_services.side_effect = [
            [],
            [],
            RunningServices.with_apps("app"),
        ]
        self.stub_http_ready(self.orch.http)
        with patch.object(self.orch, "sync"):
            self.orch.ensure_app_deployed("app")
        kinds = [e.kind for e in self._events()]
        assert kinds == [KIND_UP, KIND_DEPLOYMENT]

    def test_failed_cutover_does_not_record(self) -> None:
        self.set_edge_running("app")
        step = MagicMock()
        step.key = "boom"
        step.run.side_effect = RuntimeError("cutover failed")
        with patch(
            "raft.services.deploy.methods.seamless.DEPLOY_CUTOVER", new=(step,)
        ):
            with patch.object(self.orch, "sync"):
                with patch("raft.services.deploy.methods.seamless.CutoverSession"):
                    with pytest.raises(RuntimeError, match="cutover failed"):
                        self.orch.redeploy_app("app")
        assert self._events() == []

    def _redeploy_ok(self) -> None:
        self.set_edge_running("app")
        with patch("raft.services.deploy.methods.seamless.CutoverSession"):
            with patch(
                "raft.services.deploy.methods.seamless.DEPLOY_CUTOVER", new=()
            ):
                with patch.object(self.orch, "sync"):
                    self.orch.redeploy_app("app")

    def _events(self):
        return GraphEventStore(self.tmp_path).events_in_window(from_ts=_EPOCH)
