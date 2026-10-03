"""Deploy success records GraphEvents for chart markers."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from raft.models.graph_event_store import KIND_DEPLOYMENT, GraphEventStore

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

    def test_failed_cutover_does_not_record(self) -> None:
        step = MagicMock()
        step.key = "boom"
        step.run.side_effect = RuntimeError("cutover failed")
        with patch(
            "raft.services.deploy.orchestrator_deploy.DEPLOY_CUTOVER", new=(step,)
        ):
            with patch.object(self.orch, "sync"):
                with patch("raft.services.deploy.orchestrator_deploy.CutoverSession"):
                    with pytest.raises(RuntimeError, match="cutover failed"):
                        self.orch.redeploy_app("app")
        assert self._events() == []

    def _redeploy_ok(self) -> None:
        with patch("raft.services.deploy.orchestrator_deploy.CutoverSession"):
            with patch(
                "raft.services.deploy.orchestrator_deploy.DEPLOY_CUTOVER", new=()
            ):
                with patch.object(self.orch, "sync"):
                    self.orch.redeploy_app("app")

    def _events(self):
        return GraphEventStore(self.tmp_path).events_in_window(from_ts=_EPOCH)
