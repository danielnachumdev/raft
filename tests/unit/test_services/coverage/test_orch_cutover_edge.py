"""Orchestrator / cutover readiness=none coverage edges."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from raft.models.stack import load_stack
from raft.services.cutover import CutoverSession
from raft.services.orchestrator import Orchestrator

from ...base import RaftTestCase, make_app, make_stack, write_applied_app


class TestOrchCutoverEdgeCoverage(RaftTestCase):
    def test_orchestrator_none_readiness(self) -> None:
        write_applied_app(
            self.tmp_path,
            "app",
            extra={"readiness": {"type": "none"}},
        )
        stack = load_stack(self.tmp_path)
        orch = Orchestrator(stack)
        orch.docker = MagicMock()
        orch.nginx = MagicMock()
        orch.http = MagicMock()
        orch.syncer = MagicMock()
        orch.docker.running_services.side_effect = [
            [],
            ["raft-gate", "raft-router", "raft-controller", "app"],
        ]
        with patch.object(orch, "sync"):
            orch.start()
        orch.http.public_host_ok.assert_not_called()

    def test_shift_skips_wait_when_none(self) -> None:
        write_applied_app(self.tmp_path, "app", extra={"readiness": {"type": "none"}})
        session = self._none_session()
        session.previous_image = "img:old"
        session.start_tmp_from_previous()
        session.docker.router_can_fetch.assert_not_called()
        with patch("raft.services.cutover.time.sleep"):
            session.shift_traffic_to_tmp()
            session.rebuild_stable_service()

    def _none_session(self) -> CutoverSession:
        stack = make_stack(
            self.tmp_path, (make_app(),), drain_seconds=0.0, ready_timeout_seconds=1.0
        )
        return CutoverSession(
            stack=stack, app=stack.apps[0],
            docker=MagicMock(), nginx=MagicMock(), http=MagicMock(),
        )
