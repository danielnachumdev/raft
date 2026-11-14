"""Status collect/report treat live cutover as redeploying."""

from __future__ import annotations

from io import StringIO

from raft.core.core.models.state.redeploying_store import RedeployingStore
from raft.core.observe.ops.status import Status
from raft.core.observe.ops.status.models import STATUS_REDEPLOYING
from raft.core.observe.ops.status.report import StatusReportWriter

from tests.unit.base import AppMakers
from tests.unit.core.observe.ops.status.base import StatusTestCase
from . import fixtures as status_fx


class TestStatusRedeploying(StatusTestCase):
    def _status(self, *names: str) -> Status:
        apps = tuple(AppMakers.make_app(n) for n in names) or (
            AppMakers.make_app("app"),
        )
        status = self.make_status(apps=apps)
        status_fx.mock_docker_idle(status)
        return status

    def test_collect_marks_redeploying_when_absent(self) -> None:
        status = self._status("app")
        RedeployingStore(self.tmp_path).mark("app")
        with self.patch_host():
            snap = status.collect()
        app = next(c for c in snap.containers if c.app == "app")
        assert app.status == STATUS_REDEPLOYING

    def test_collect_marks_redeploying_when_container_present(self) -> None:
        status = self.make_status("app")
        gateway = status_fx.mock_containers_idle(status)
        gateway.collect.return_value = {
            "raft-gate": status_fx.runtime_row("gatecid", health="none"),
            "app": status_fx.runtime_row("appcid", health="healthy"),
        }
        RedeployingStore(self.tmp_path).mark("app")
        with self.patch_host():
            snap = status.collect()
        app = next(c for c in snap.containers if c.app == "app")
        assert app.status == STATUS_REDEPLOYING

    def test_report_footnote_for_redeploying(self) -> None:
        snap = status_fx.snapshot(
            status_fx.container(
                "app",
                app="app",
                status=STATUS_REDEPLOYING,
                uptime=None,
                cpu=None,
                mem_used=None,
                mem_limit=None,
                mem_pct=None,
                pids=None,
            )
        )
        out = StringIO()
        assert StatusReportWriter().write(snap, out=out, color=False) == 0
        text = out.getvalue()
        assert STATUS_REDEPLOYING in text
        assert "cutover" in text
