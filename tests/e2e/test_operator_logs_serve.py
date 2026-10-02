"""E2E stories: operator inspects container logs and the serve dashboard."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.e2e.shared.ops_stack import OpsE2EStack

pytestmark = pytest.mark.e2e


class TestOperatorLogsAndServe:
    """Real Docker apps-only stack → ``raft logs`` + ``raft serve`` shell/API.

    Scenario:
      1) App is applied and running (http-echo).
      2) Operator hits the published port, then snapshots ``raft logs``.
      3) Operator opens the localhost serve shell and loads ``/api/status``.
    """

    def test_logs_snapshot_and_serve_dashboard(self, isolated_raft_env: Path) -> None:
        with OpsE2EStack.create(isolated_raft_env) as stack:
            self._assert_logs_show_container_output(stack)
            self._assert_serve_lists_running_app(stack)

    def _assert_logs_show_container_output(self, stack: OpsE2EStack) -> None:
        stack.hit_app()
        text = stack.snapshot_logs(stack.APP, tail=50)
        assert text.strip(), "expected non-empty raft logs snapshot"
        assert stack.APP in text or "Listening" in text or "echo" in text.lower()

    def _assert_serve_lists_running_app(self, stack: OpsE2EStack) -> None:
        client = stack.serve_client()
        shell = client.get("/")
        assert shell.status_code == 200
        assert 'id="root"' in shell.text and "/assets/" in shell.text
        api = client.get("/api/status")
        assert api.status_code == 200
        names = [row["name"] for row in api.json()["apps"]]
        assert stack.APP in names or any(stack.APP in n for n in names)
